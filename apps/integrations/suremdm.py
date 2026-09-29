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

    def device_log(self, device_id, from_date, to_date, log_type='1'):
        """
        Fetch a device's activity log (online/offline transitions, device
        info updates, etc.) for the given UTC window.

        from_date / to_date must be strings in the format the console's own
        "Device Activity" tab sends, e.g. '2026-07-10T08:59:00.000Z'.
        """
        if not device_id:
            return []

        payload = {
            'FromDate': from_date,
            'ToDate': to_date,
            'DeviceId': device_id,
            'LogType': log_type,
        }
        _, data = self.post('devicelog/', payload)
        return data if isinstance(data, list) else []

    def trigger_apps_refresh(self, device_id):
        """
        Ask a device to report its installed-application list back to
        SureMDM (documented as the "GET_DEVICE_APPS" dynamic job in
        SureMDM's REST API sample code). This is fire-and-forget: the
        device must be online to receive the job and it reports back on
        its own schedule, so the refreshed app list only becomes visible
        via the device list/detail endpoints sometime after this call
        returns, not synchronously.
        """
        if not device_id:
            return False

        payload = {'JobType': 'GET_DEVICE_APPS', 'DeviceID': str(device_id)}
        self.post('dynamicjob', payload)
        return True

    def _location_points(self, data):
        """
        Flatten SureMDM's location responses into a flat list of point dicts.

        SureMDM has shipped a few shapes for this across API versions:
        - {"status": true, "data": [{"DeviceId": "..", "Location": [{...}]}]}
        - {"DeviceId": "..", "Location": [{...}]}
        - [{"DeviceId": "..", "Location": [{...}]}]
        - a bare [{"Latitude": .., "Longitude": .., "Time": ".."}] list

        Every returned point carries a "DeviceId" so callers can group points
        back onto the device they came from.
        """
        if isinstance(data, dict):
            if isinstance(data.get('data'), list):
                entries = data['data']
            elif isinstance(data.get('Location'), list):
                entries = [data]
            else:
                entries = []
        elif isinstance(data, list):
            if data and isinstance(data[0], dict) and 'Location' in data[0]:
                entries = data
            else:
                return [point for point in data if isinstance(point, dict)]
        else:
            entries = []

        points = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            device_id = entry.get('DeviceId') or entry.get('DeviceID') or ''
            for point in entry.get('Location') or []:
                if not isinstance(point, dict):
                    continue
                point = dict(point)
                point.setdefault('DeviceId', device_id)
                points.append(point)
        return points

    def last_location(self, device_ids):
        """
        Fetch the last reported location for one or more devices
        (POST /api/v2/location). SureMDM accepts a CSV of device IDs.
        """
        if isinstance(device_ids, str):
            ids = device_ids
        else:
            ids = ','.join(str(device_id) for device_id in device_ids if device_id)
        if not ids:
            return []

        _, data = self.post('v2/location', {'DeviceID': ids})
        return self._location_points(data)

    def location_history(self, device_id, from_time=None, to_time=None):
        """
        Fetch a device's recorded location trail for a window
        (GET /api/v2/location). Location tracking has to already be enabled
        on the device in SureMDM for this to return anything.

        from_time / to_time are strings formatted 'YYYY-MM-DDTHH:MM:SS'.
        """
        if not device_id:
            return []

        params = {'DeviceID': device_id}
        if from_time:
            params['FromTime'] = from_time
        if to_time:
            params['ToTime'] = to_time
        _, data = self.get('v2/location', params)
        return self._location_points(data)

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
