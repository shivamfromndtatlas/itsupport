import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import ProxyHandler, Request, build_opener


class SynthesiaError(RuntimeError):
    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


class SynthesiaClient:
    """
    Client for the Synthesia video API (https://docs.synthesia.io).

    Auth is a single API key sent as-is in the Authorization header (no
    "Bearer" prefix) - this is Synthesia's documented scheme, unlike most
    OAuth2-style APIs.
    """

    def __init__(self, base_url, api_key, timeout=20):
        self.base_url = base_url.rstrip('/') + '/'
        self.api_key = api_key
        self.timeout = timeout

    def _opener(self):
        return build_opener(ProxyHandler({}))

    def _headers(self):
        return {
            'Authorization': self.api_key,
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
                message = 'Synthesia rejected the request. Re-enter and save the API key, then test again.'
            else:
                message = raw or exc.reason or 'Synthesia request failed.'
                message = f'Synthesia returned HTTP {exc.code}: {message}'
            raise SynthesiaError(message, status_code=exc.code) from exc
        except URLError as exc:
            raise SynthesiaError(f'Could not reach Synthesia: {exc.reason}') from exc

    def get(self, path, params=None):
        return self._request('GET', path, params=params)

    def list_videos(self, limit=100, offset=0, source=None):
        params = {'limit': limit, 'offset': offset}
        if source:
            params['source'] = source
        _, data = self.get('videos', params)
        return data.get('videos') or [], data.get('nextOffset')

    def list_all_videos(self, source=None, page_limit=100, max_videos=2000):
        videos = []
        offset = 0
        while True:
            page, next_offset = self.list_videos(limit=page_limit, offset=offset, source=source)
            if not page:
                break
            videos.extend(page)
            if next_offset is None or next_offset == offset or len(videos) >= max_videos:
                break
            offset = next_offset
        return videos[:max_videos]

    def get_video(self, video_id):
        _, data = self.get(f'videos/{video_id}')
        return data
