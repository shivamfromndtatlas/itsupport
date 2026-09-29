"""
Client for the Dell TechDirect / Dell APIs warranty + asset-configuration
endpoints.

Auth is OAuth2 client-credentials: POST client_id/client_secret to
``/auth/oauth/v2/token`` for a ~1h bearer token, then call:

  GET /PROD/sbil/v5/asset-entitlements?servicetags=<tag[,tag...]>   (warranty)
  GET /PROD/sbil/eapi/v5/asset-components?servicetag=<tag>          (original config)

The asset-components endpoint needs a separate entitlement on the TechDirect
account; callers treat a 403/404 there as "no config available" rather than a
hard error.
"""
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import ProxyHandler, Request, build_opener

TOKEN_PATH = '/auth/oauth/v2/token'
ENTITLEMENTS_PATH = '/PROD/sbil/eapi/v5/asset-entitlements'
COMPONENTS_PATH = '/PROD/sbil/eapi/v5/asset-components'


class DellError(RuntimeError):
    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


class DellComponentsUnavailable(DellError):
    """asset-components is not entitled on this account - non-fatal."""


class DellClient:
    def __init__(self, base_url, client_id, client_secret, timeout=20, access_token=None):
        self.base_url = (base_url or 'https://apigtwb2c.us.dell.com').rstrip('/')
        self.client_id = client_id
        self.client_secret = client_secret
        self.timeout = timeout
        self._access_token = access_token or None

    def _opener(self):
        return build_opener(ProxyHandler({}))

    def fetch_token(self):
        body = urlencode({
            'grant_type': 'client_credentials',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
        }).encode('utf-8')
        request = Request(
            self.base_url + TOKEN_PATH,
            data=body,
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json',
            },
            method='POST',
        )
        try:
            with self._opener().open(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode('utf-8') or '{}')
        except HTTPError as exc:
            detail = exc.read().decode('utf-8', 'replace')
            if exc.code in (400, 401):
                message = 'Dell rejected the client credentials. Re-check the client ID and secret from TechDirect.'
            else:
                message = f'Dell token request failed (HTTP {exc.code}): {detail[:200]}'
            raise DellError(message, status_code=exc.code) from exc
        except (URLError, TimeoutError) as exc:
            raise DellError(f'Could not reach Dell to authenticate: {getattr(exc, "reason", exc)}') from exc

        token = payload.get('access_token')
        if not token:
            raise DellError('Dell did not return an access token.')
        self._access_token = token
        # expires_in is seconds; caller persists with a safety margin.
        return token, int(payload.get('expires_in') or 3600)

    def _token(self):
        if self._access_token:
            return self._access_token
        token, _ = self.fetch_token()
        return token

    def _get(self, path, params, *, retry_on_401=True):
        url = f'{self.base_url}{path}?{urlencode(params)}'
        request = Request(
            url,
            headers={'Authorization': f'Bearer {self._token()}', 'Accept': 'application/json'},
            method='GET',
        )
        try:
            with self._opener().open(request, timeout=self.timeout) as response:
                raw = response.read().decode('utf-8')
                return json.loads(raw) if raw else {}
        except HTTPError as exc:
            if exc.code == 401 and retry_on_401:
                self._access_token = None
                self.fetch_token()
                return self._get(path, params, retry_on_401=False)
            detail = exc.read().decode('utf-8', 'replace')
            if exc.code in (403, 404) and path == COMPONENTS_PATH:
                raise DellComponentsUnavailable(
                    'This Dell TechDirect account is not entitled to the asset-components (original '
                    'configuration) API. Warranty data is still available.',
                    status_code=exc.code,
                ) from exc
            raise DellError(f'Dell API returned HTTP {exc.code}: {detail[:200]}', status_code=exc.code) from exc
        except (URLError, TimeoutError) as exc:
            raise DellError(f'Could not reach the Dell API: {getattr(exc, "reason", exc)}') from exc

    def asset_entitlements(self, service_tags):
        tags = ','.join(t.strip() for t in service_tags if t and t.strip())
        data = self._get(ENTITLEMENTS_PATH, {'servicetags': tags})
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get('assetEntitlementList') or data.get('AssetEntitlementData') or [data]
        return []

    def asset_components(self, service_tag):
        data = self._get(COMPONENTS_PATH, {'servicetag': service_tag.strip()})
        if isinstance(data, list):
            return data[0] if data else {}
        return data if isinstance(data, dict) else {}
