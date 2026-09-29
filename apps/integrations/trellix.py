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
    e.g. epo.device.r for Devices and epo.evt.r for Events), then bearer-token
    calls to api.manage.trellix.com carrying the tenant's x-api-key. The ePO
    v2 routes (/epo/v2/devices, /epo/v2/events - both confirmed against a
    real tenant) return JSON:API-style {"data": [...]} payloads, which
    _unwrap_jsonapi_list() flattens. The two routes paginate differently:
    Devices uses offset pagination (page[limit]/page[offset] + a
    meta.totalResourceCount), Events uses cursor pagination (a links.next
    URL that already embeds the next page[cursor]) - handled by
    _paginate_offset() and _paginate_cursor() respectively. If either
    confirmed route ever fails outright (a non-auth error), list_devices()
    falls back to a set of unconfirmed candidate paths, the same resilience
    approach used for SureMDM's installed_apps() above.
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
        # a plain application/json Content-Type gets rejected. That sample
        # call only sends these three headers (no tenant header), and this
        # is a strict JSON:API server, so we don't add anything undocumented.
        return {
            'Authorization': f'Bearer {self._access_token()}',
            'x-api-key': self.api_key,
            'Content-Type': 'application/vnd.api+json',
            'Accept': 'application/vnd.api+json',
        }

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

    def _paginate_offset(self, path, limit=None, page_size=200):
        """
        Follow Devices-style offset pagination: page[limit]/page[offset],
        stopping once meta.totalResourceCount is reached, a short page
        signals the last one, or the caller's `limit` is satisfied.
        """
        results = []
        offset = 0
        total = None
        while limit is None or len(results) < limit:
            request_size = page_size if limit is None else min(page_size, limit - len(results))
            _, data = self.get(path, {'page[limit]': request_size, 'page[offset]': offset})
            page_items = self._unwrap_jsonapi_list(data)
            if page_items is None:
                return self._first_list(data, *self.LIST_KEYS)
            results.extend(page_items)
            if isinstance(data, dict) and isinstance(data.get('meta'), dict):
                total = data['meta'].get('totalResourceCount', total)
            offset += request_size
            if len(page_items) < request_size:
                break
            if total is not None and len(results) >= total:
                break
        return results[:limit] if limit is not None else results

    def _paginate_cursor(self, path, limit=None, page_size=100, extra_params=None):
        """
        Follow Events-style cursor pagination: the first request sets
        page[limit] (plus any extra filter params), and each response's
        links.next is a ready-made URL (path + query, cursor embedded) to
        request as-is for the next page.
        """
        results = []
        next_path = path
        next_params = {'page[limit]': page_size, **(extra_params or {})}
        while next_path and (limit is None or len(results) < limit):
            _, data = self.get(next_path, next_params)
            page_items = self._unwrap_jsonapi_list(data)
            if page_items is None:
                return self._first_list(data, *self.LIST_KEYS)
            results.extend(page_items)
            next_path = data.get('links', {}).get('next') if isinstance(data, dict) else None
            next_params = None
        return results[:limit] if limit is not None else results

    def list_devices(self, limit=1000):
        try:
            return self._paginate_offset('epo/v2/devices', limit=limit)
        except TrellixError as exc:
            if exc.stage == 'auth':
                raise

        fallback_params = {'tenantId': self.tenant_id, 'limit': limit} if self.tenant_id else {'limit': limit}
        attempts = [
            ('epo/v2/systemtree/systems', fallback_params),
            ('epo/v2/systems', fallback_params),
            ('mvision/v2/devices', fallback_params),
        ]
        return self._try_list_routes(attempts, 'endpoint-inventory')

    def list_threat_events(self, limit=200, from_date=None, to_date=None):
        # Date-range filtering isn't wired up: the Events API's filter query
        # syntax (filter[...] JSON:API operators, presumably) isn't confirmed
        # against a real response yet, and guessing at param names is what
        # caused the Devices 400s earlier. from_date/to_date are accepted for
        # a stable call signature but currently ignored - every event up to
        # `limit` is returned, newest first per the API's own ordering.
        return self._paginate_cursor('epo/v2/events', limit=limit)
