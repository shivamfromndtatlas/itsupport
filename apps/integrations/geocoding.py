"""
Best-effort reverse geocoding for SureMDM device coordinates.

SureMDM's own "last location" payload frequently carries the string
"Unable to fetch the address." instead of a resolved address (its server-side
geocoder failed or was rate limited when the device reported). To still show a
human-readable location, we resolve coordinates ourselves against OpenStreetMap's
Nominatim service, with results cached so we only hit the network for
coordinates we've never seen.

Nominatim's usage policy asks for <= 1 request/second and a identifying
User-Agent, so callers pass a small per-request budget and we pause between live
lookups. Anything already cached is free and doesn't count against the budget.
"""
import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import ProxyHandler, Request, build_opener

from django.conf import settings
from django.core.cache import cache

NOMINATIM_URL = 'https://nominatim.openstreetmap.org/reverse'
USER_AGENT = 'ITSupportPortal/1.0 (device location tracking)'
_CACHE_PREFIX = 'suremdm_geocode:'
_HIT_TTL = 60 * 60 * 24 * 30  # 30 days
_MISS_TTL = 60 * 60 * 6       # back off for 6 hours after a failed lookup
_MIN_INTERVAL_SECONDS = 1.1

_last_call_at = 0.0


def _cache_key(lat, lng):
    return f'{_CACHE_PREFIX}{round(float(lat), 5)},{round(float(lng), 5)}'


def _fetch(lat, lng, timeout):
    global _last_call_at

    wait = _MIN_INTERVAL_SECONDS - (time.monotonic() - _last_call_at)
    if wait > 0:
        time.sleep(wait)

    params = urlencode({'format': 'jsonv2', 'lat': lat, 'lon': lng, 'zoom': 18, 'addressdetails': 0})
    request = Request(f'{NOMINATIM_URL}?{params}', headers={'User-Agent': USER_AGENT}, method='GET')
    opener = build_opener(ProxyHandler({}))
    try:
        with opener.open(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode('utf-8') or '{}')
    except (HTTPError, URLError, ValueError, TimeoutError):
        return None
    finally:
        _last_call_at = time.monotonic()

    return (payload.get('display_name') or '').strip() or None


class ReverseGeocoder:
    """
    Resolves a batch of coordinates, honouring a live-lookup budget.

    ``resolve(lat, lng)`` returns an address string or ''. Cached coordinates
    always resolve; uncached ones only resolve while ``budget`` remains.
    """

    def __init__(self, budget=None, timeout=6):
        self.enabled = getattr(settings, 'SUREMDM_REVERSE_GEOCODE', True)
        if budget is None:
            budget = getattr(settings, 'SUREMDM_GEOCODE_BUDGET', 12)
        self.budget = budget
        self.timeout = timeout

    def resolve(self, lat, lng):
        if lat is None or lng is None:
            return ''

        key = _cache_key(lat, lng)
        cached = cache.get(key)
        if cached is not None:
            return cached

        if not self.enabled or self.budget <= 0:
            return ''

        self.budget -= 1
        address = _fetch(lat, lng, self.timeout)
        if address:
            cache.set(key, address, _HIT_TTL)
            return address
        cache.set(key, '', _MISS_TTL)
        return ''
