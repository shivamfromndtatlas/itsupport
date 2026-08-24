import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import ProxyHandler, Request, build_opener


class TeamViewerError(RuntimeError):
    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


class TeamViewerClient:
    """
    Client for the TeamViewer Web API (https://webapi.teamviewer.com/api/v1).

    Auth is a single API token (a personal "Script" token or a company-wide
    token from the Management Console) sent as a Bearer token. Each token is
    scoped to specific permissions (Devices.Read, Account.Read, etc.) at
    creation time, so /ping is used to validate the token itself without
    requiring any particular scope beyond a valid token.
    """

    def __init__(self, base_url, api_token, timeout=20):
        self.base_url = base_url.rstrip('/') + '/'
        self.api_token = api_token
        self.timeout = timeout

    def _opener(self):
        return build_opener(ProxyHandler({}))

    def _headers(self):
        return {
            'Authorization': f'Bearer {self.api_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

    def _request(self, method, path, params=None):
        url = urljoin(self.base_url, path.lstrip('/'))
        if params:
            url = f'{url}?{urlencode({k: v for k, v in params.items() if v is not None})}'
        request = Request(url, headers=self._headers(), method=method)

        try:
            with self._opener().open(request, timeout=self.timeout) as response:
                raw = response.read().decode('utf-8')
                return response.status, json.loads(raw) if raw else {}
        except HTTPError as exc:
            raw = exc.read().decode('utf-8')
            if exc.code == 401:
                message = 'TeamViewer rejected the request. Re-enter and save the API token, then test again.'
            else:
                message = raw or exc.reason or 'TeamViewer request failed.'
                message = f'TeamViewer returned HTTP {exc.code}: {message}'
            raise TeamViewerError(message, status_code=exc.code) from exc
        except URLError as exc:
            raise TeamViewerError(f'Could not reach TeamViewer: {exc.reason}') from exc

    def get(self, path, params=None):
        return self._request('GET', path, params=params)

    def ping(self):
        _, data = self.get('ping')
        return bool(data.get('token_valid'))

    def list_managed_groups(self):
        """
        Managed groups (TeamViewer Remote Management / Tensor) are a
        separate resource from the classic Computers & Contacts groups
        returned by GET /groups - listing them needs a permission the
        token may not carry, which surfaces as a 401 here even though the
        token itself is otherwise valid.
        """
        _, data = self.get('managed/groups')
        return data.get('groups') or data.get('managed_groups') or []

    def list_devices(self, limit=None, include_managed=True):
        """
        GET /devices only returns classic Computers & Contacts devices
        (each carries a remotecontrol_id). Devices added through Remote
        Management live under managed groups instead and don't show up
        there, so - when the token has visibility into managed/groups -
        each managed group's devices are pulled in via the same /devices
        endpoint filtered by that group's id, and merged in by device_id.

        Returns (devices, managed_groups_error): managed_groups_error is
        set (and non-fatal) when managed groups couldn't be listed, so
        classic devices still come back and the caller can surface why
        managed devices are missing.
        """
        devices_by_id = {}
        _, data = self.get('devices')
        for device in data.get('devices') or []:
            devices_by_id[device.get('device_id')] = device

        managed_groups_error = None
        if include_managed:
            try:
                for group in self.list_managed_groups():
                    group_id = group.get('id')
                    if not group_id:
                        continue
                    _, group_data = self.get('devices', {'groupid': group_id})
                    for device in group_data.get('devices') or []:
                        devices_by_id.setdefault(device.get('device_id'), device)
            except TeamViewerError as exc:
                managed_groups_error = exc

        devices = list(devices_by_id.values())
        return (devices[:limit] if limit else devices), managed_groups_error
