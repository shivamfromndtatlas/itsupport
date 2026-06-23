import base64
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import ProxyHandler, Request, build_opener


class SureMDMError(RuntimeError):
    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


class SureMDMClient:
    def __init__(self, base_url, username, password, api_key, timeout=20):
        self.base_url = base_url.rstrip('/') + '/'
        self.username = username
        self.password = password
        self.api_key = api_key
        self.timeout = timeout

    def _headers(self):
        token = base64.b64encode(f'{self.username}:{self.password}'.encode()).decode()
        return {
            'Authorization': f'Basic {token}',
            'ApiKey': self.api_key,
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

    def post(self, path, payload):
        url = urljoin(self.base_url, path.lstrip('/'))
        data = json.dumps(payload).encode('utf-8')
        request = Request(url, data=data, headers=self._headers(), method='POST')
        opener = build_opener(ProxyHandler({}))

        try:
            with opener.open(request, timeout=self.timeout) as response:
                raw = response.read().decode('utf-8')
                return response.status, json.loads(raw) if raw else {}
        except HTTPError as exc:
            raw = exc.read().decode('utf-8')
            if exc.code == 401:
                message = (
                    'SureMDM rejected the connection. Re-enter and save the SureMDM '
                    'username, account password, and API key, then test again.'
                )
            else:
                message = raw or exc.reason or 'SureMDM request failed.'
                message = f'SureMDM returned HTTP {exc.code}: {message}'
            raise SureMDMError(message, status_code=exc.code) from exc
        except URLError as exc:
            raise SureMDMError(f'Could not reach SureMDM: {exc.reason}') from exc

    def get(self, path, params=None):
        url = urljoin(self.base_url, path.lstrip('/'))
        if params:
            url = f'{url}?{urlencode(params)}'
        request = Request(url, headers=self._headers(), method='GET')
        opener = build_opener(ProxyHandler({}))

        try:
            with opener.open(request, timeout=self.timeout) as response:
                raw = response.read().decode('utf-8')
                return response.status, json.loads(raw) if raw else {}
        except HTTPError as exc:
            raw = exc.read().decode('utf-8')
            if exc.code == 401:
                message = (
                    'SureMDM rejected the connection. Re-enter and save the SureMDM '
                    'username, account password, and API key, then test again.'
                )
            else:
                message = raw or exc.reason or 'SureMDM request failed.'
                message = f'SureMDM returned HTTP {exc.code}: {message}'
            raise SureMDMError(message, status_code=exc.code) from exc
        except URLError as exc:
            raise SureMDMError(f'Could not reach SureMDM: {exc.reason}') from exc

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

    def list_devices(self, limit=50, group_id='AllDevices'):
        payload = {
            'ID': group_id,
            'IsSearch': False,
            'Limit': limit,
            'SortColumn': 'LastTimeStamp',
            'SortOrder': 'desc',
        }
        _, data = self.post('device', payload)
        if isinstance(data, dict):
            return data.get('rows') or data.get('Rows') or data.get('data') or []
        if isinstance(data, list):
            return data
        return []

    def installed_apps(self, device_id):
        """
        Fetch installed applications for a device.

        SureMDM tenants/API versions vary in the exact route used for this
        report, so we try the known report-style paths and normalize the first
        list-shaped response.
        """
        if not device_id:
            return []

        list_keys = (
            'rows',
            'Rows',
            'data',
            'Data',
            'results',
            'Results',
            'apps',
            'Apps',
            'Applications',
            'ApplicationDetails',
            'DeviceApplistDetails',
            'InstalledApplications',
            'installed_applications',
        )
        get_attempts = [
            ('device/installedapps', {'DeviceID': device_id}),
            ('device/installedapps', {'ID': device_id}),
            ('device/installedapps', {'deviceId': device_id}),
            ('device/installedapplications', {'DeviceID': device_id}),
            ('device/applications', {'DeviceID': device_id}),
            ('device/applicationlist', {'DeviceID': device_id}),
        ]

        for path, params in get_attempts:
            try:
                _, data = self.get(path, params)
            except SureMDMError:
                continue

            apps = self._first_list(data, *list_keys)
            # A successful empty app report is still authoritative. Do not fall
            # through to POST guesses that older tenants may reject with 400.
            return apps

        post_attempts = [
            ('device/installedapps', {'DeviceID': device_id}),
            ('device/installedapplications', {'DeviceID': device_id}),
            ('device/applications', {'DeviceID': device_id}),
            ('device/applicationlist', {'DeviceID': device_id}),
        ]
        for path, payload in post_attempts:
            try:
                _, data = self.post(path, payload)
            except SureMDMError:
                continue

            return self._first_list(data, *list_keys)
        return []
