import base64
import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import ProxyHandler, Request, build_opener


class TrellixError(RuntimeError):
    def __init__(self, message, status_code=None, stage='request'):
        super().__init__(message)
        self.status_code = status_code
        # 'auth' means the OAuth2 token request itself failed, so every
        # candidate route would fail identically - callers should stop
        # trying further paths and surface this error immediately instead
        # of masking it behind a generic "none of the routes worked".
        self.stage = stage


class TrellixClient:
    """
    Client for the Trellix (formerly McAfee MVISION/ePO SaaS) management API.

    Auth is OAuth2 client-credentials against Trellix's IAM token endpoint
    (scoped per the Trellix Developer Portal's "API Access Requirements",
    e.g. epo.device.r for the Devices API), then bearer-token calls to
    api.manage.trellix.com carrying the tenant's x-api-key. The documented
    ePO v2 routes (/epo/v2/...) return JSON:API-style {"data": [...]}
    payloads, which _unwrap_jsonapi_list() flattens. Threat/event reporting
    isn't covered by that same API family, so list_threat_events() also
    tries a set of candidate paths and normalizes whichever responds first,
    the same fallback approach used for SureMDM's installed_apps() above.
    """

    def __init__(self, base_url, auth_url, client_id, client_secret, api_key, tenant_id='', scope='', timeout=20):
        self.base_url = base_url.rstrip('/') + '/'
        self.auth_url = auth_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.api_key = api_key
        self.tenant_id = tenant_id
        self.scope = scope
        self.timeout = timeout
        self._token = None
        self._token_expires_at = 0

    def _opener(self):
        return build_opener(ProxyHandler({}))

    def _fetch_token(self):
        # Per Trellix's "Understanding Trellix Authorization model" docs, the
        # client credentials are sent as HTTP Basic auth (base64 client_id:
        # client_secret), not as body fields - only grant_type and scope go
        # in the form body.
        form = {'grant_type': 'client_credentials'}
        if self.scope:
            form['scope'] = self.scope
        data = urlencode(form).encode('utf-8')
        basic_auth = base64.b64encode(f'{self.client_id}:{self.client_secret}'.encode()).decode()
        request = Request(
            self.auth_url,
            data=data,
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json',
                'Authorization': f'Basic {basic_auth}',
            },
            method='POST',
        )
        try:
            with self._opener().open(request, timeout=self.timeout) as response:
                raw = response.read().decode('utf-8')
                payload = json.loads(raw) if raw else {}
        except HTTPError as exc:
            raw = exc.read().decode('utf-8')
            if exc.code == 401:
                message = (
                    'Trellix rejected the connection. Re-enter and save the Trellix '
                    'Client ID and Client Secret, then test again.'
                )
            else:
                message = raw or exc.reason or 'Trellix token request failed.'
                message = f'Trellix token endpoint returned HTTP {exc.code}: {message}'
            raise TrellixError(message, status_code=exc.code, stage='auth') from exc
        except URLError as exc:
            raise TrellixError(f'Could not reach Trellix: {exc.reason}', stage='auth') from exc

        token = payload.get('access_token')
        if not token:
            raise TrellixError('Trellix token response did not include an access_token.', stage='auth')
        self._token = token
        self._token_expires_at = time.time() + int(payload.get('expires_in', 3600)) - 30
        return token

    def _access_token(self):
        if self._token and time.time() < self._token_expires_at:
            return self._token
        return self._fetch_token()

    def _headers(self):
        # Per the Developer Portal's "API Access Information" sample call,
        # Trellix's ePO v2 API (JSON:API) requires this exact media type -
        # a plain application/json Content-Type gets rejected.
        headers = {
            'Authorization': f'Bearer {self._access_token()}',
            'x-api-key': self.api_key,
            'Content-Type': 'application/vnd.api+json',
            'Accept': 'application/vnd.api+json',
        }
        if self.tenant_id:
            headers['x-tenant-id'] = self.tenant_id
        return headers

    def _request(self, method, path, params=None, payload=None):
        url = urljoin(self.base_url, path.lstrip('/'))
        if params:
            url = f'{url}?{urlencode(params)}'
        data = json.dumps(payload).encode('utf-8') if payload is not None else None
        request = Request(url, data=data, headers=self._headers(), method=method)

        try:
            with self._opener().open(request, timeout=self.timeout) as response:
                raw = response.read().decode('utf-8')
                return response.status, json.loads(raw) if raw else {}
        except HTTPError as exc:
            raw = exc.read().decode('utf-8')
            if exc.code == 401:
                message = (
                    'Trellix rejected the request. Re-enter and save the Client ID, '
                    'Client Secret, and API key, then test again.'
                )
            else:
                message = raw or exc.reason or 'Trellix request failed.'
                message = f'Trellix returned HTTP {exc.code}: {message}'
            raise TrellixError(message, status_code=exc.code) from exc
        except URLError as exc:
            raise TrellixError(f'Could not reach Trellix: {exc.reason}') from exc

    def get(self, path, params=None):
        return self._request('GET', path, params=params)

    def post(self, path, payload):
        return self._request('POST', path, payload=payload)

    def _first_list(self, data, *keys):
        if isinstance(data, list):
            return data
        if not isinstance(data, dict):
            return []
        for key in keys:
            value = data.get(key)
            if isinstance(value, list):
                return value
        for value in data.values():
            if isinstance(value, dict):
                nested = self._first_list(value, *keys)
                if nested:
                    return nested
        return []

    LIST_KEYS = ('rows', 'Rows', 'data', 'Data', 'results', 'Results', 'items', 'Items')

    def _unwrap_jsonapi_list(self, data):
        """
        Trellix's ePO v2 API (/epo/v2/...) follows the JSON:API spec: a list
        response is {"data": [{"id": ..., "type": ..., "attributes": {...}}]}.
        Flatten each resource object's id + attributes into one dict so the
        rest of the normalization code can treat it like any other payload.
        """
        if not isinstance(data, dict):
            return None
        items = data.get('data')
        if not isinstance(items, list):
            return None
        flattened = []
        for item in items:
            if not isinstance(item, dict):
                continue
            attributes = item.get('attributes')
            entry = dict(attributes) if isinstance(attributes, dict) else {}
            if item.get('id') is not None:
                entry.setdefault('id', item['id'])
            flattened.append(entry)
        return flattened

    def _try_list_routes(self, attempts, kind):
        errors = []
        for path, query in attempts:
            try:
                _, data = self.get(path, query)
            except TrellixError as exc:
                if exc.stage == 'auth':
                    raise
                errors.append(f'{path} -> {exc}')
                continue
            jsonapi_list = self._unwrap_jsonapi_list(data)
            if jsonapi_list is not None:
                return jsonapi_list
            return self._first_list(data, *self.LIST_KEYS)

        detail = '; '.join(errors) if errors else 'no routes were attempted'
        raise TrellixError(f'None of the known Trellix {kind} routes responded successfully: {detail}')

    def list_devices(self, limit=50):
        params = {'tenantId': self.tenant_id, 'limit': limit} if self.tenant_id else {'limit': limit}
        attempts = [
            ('epo/v2/devices', params),
            ('epo/v2/systemtree/systems', params),
            ('epo/v2/systems', params),
            ('mvision/v2/devices', params),
        ]
        return self._try_list_routes(attempts, 'endpoint-inventory')

    def list_threat_events(self, limit=50, from_date=None, to_date=None):
        params = {'limit': limit}
        if self.tenant_id:
            params['tenantId'] = self.tenant_id
        if from_date:
            params['fromDate'] = from_date
        if to_date:
            params['toDate'] = to_date

        attempts = [
            ('epo/v2/threat-events', params),
            ('mvision/v2/deviceThreatEvents', params),
            ('siem/v1/threat-events', params),
        ]
        return self._try_list_routes(attempts, 'threat-event')
