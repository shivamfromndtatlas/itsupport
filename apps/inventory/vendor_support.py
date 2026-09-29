"""
Best-effort scraping of Dell / Lenovo public support pages for an asset's
warranty entitlements and original shipped configuration, keyed by service tag
(Dell) or serial number (Lenovo).

Both vendors render these pages client-side and sit behind bot protection, so
these lookups fail often. When that happens we record the failure on
``AssetSupportInfo`` with a readable message rather than raising - the dashboard
shows "couldn't reach the vendor" and the user can retry later. The value here is
the normalized cache shape; it fills in whenever a request does get through.

Only laptops and monitors are looked up (``asset_supports_vendor_lookup``).
"""
import json
import re
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import ProxyHandler, Request, build_opener

from django.conf import settings
from django.utils import timezone

BROWSER_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    ),
    'Accept': 'application/json, text/plain, text/html, */*',
    'Accept-Language': 'en-US,en;q=0.9',
}

SUPPORTED_ASSET_TYPE_KEYWORDS = ('laptop', 'notebook', 'monitor', 'display')

DELL_HINTS = ('dell', 'latitude', 'optiplex', 'precision', 'inspiron', 'vostro', 'xps', 'wyse', 'alienware')
LENOVO_HINTS = ('lenovo', 'thinkpad', 'thinkcentre', 'thinkbook', 'ideapad', 'ideacentre', 'yoga', 'legion')

# Dell service tags are 5-7 alphanumeric chars; Dell Express Service Codes are
# all-digit. Lenovo serials are typically 7-12 alphanumeric chars, no dashes -
# used to reject GUID-style system tags / MDM ids that aren't lookup keys.
DELL_SERVICE_TAG_RE = re.compile(r'^[A-Z0-9]{5,7}$', re.IGNORECASE)
LENOVO_SERIAL_RE = re.compile(r'^[A-Z0-9]{6,14}$', re.IGNORECASE)


class VendorSupportError(RuntimeError):
    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


def _normalize(value):
    return re.sub(r'[^a-z0-9]', '', str(value or '').lower())


def _scrape_enabled():
    return getattr(settings, 'VENDOR_SUPPORT_SCRAPE', True)


def _timeout():
    return getattr(settings, 'VENDOR_SUPPORT_TIMEOUT', 15)


def _http_get(url, headers=None, timeout=None):
    request = Request(url, headers={**BROWSER_HEADERS, **(headers or {})}, method='GET')
    opener = build_opener(ProxyHandler({}))
    try:
        with opener.open(request, timeout=timeout or _timeout()) as response:
            charset = response.headers.get_content_charset() or 'utf-8'
            return response.read().decode(charset, errors='replace')
    except HTTPError as exc:
        raise VendorSupportError(
            f'The vendor support site returned HTTP {exc.code}.', status_code=exc.code
        ) from exc
    except (URLError, TimeoutError) as exc:
        reason = getattr(exc, 'reason', exc)
        raise VendorSupportError(f'Could not reach the vendor support site: {reason}.') from exc


def _parse_date(value):
    if not value:
        return None
    text = str(value).strip()
    for fmt in ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%d', '%m/%d/%Y', '%d-%b-%Y', '%d %b %Y', '%b %d, %Y'):
        try:
            return datetime.strptime(text[:len(fmt) + 4], fmt).date()
        except ValueError:
            continue
    match = re.search(r'(\d{4})-(\d{2})-(\d{2})', text)
    if match:
        try:
            return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3))).date()
        except ValueError:
            return None
    return None


def _iso(value):
    parsed = _parse_date(value)
    return parsed.isoformat() if parsed else ''


def _warranty_status(end_date):
    parsed = _parse_date(end_date)
    if not parsed:
        return 'unknown'
    return 'active' if parsed >= timezone.localdate() else 'expired'


def _epoch_ms_to_iso(value):
    try:
        return datetime.utcfromtimestamp(int(value) / 1000).date().isoformat()
    except (TypeError, ValueError, OSError):
        return ''


def _extract_enclosing_object(text, needle):
    """
    Given the index/substring ``needle`` inside a larger blob of HTML/JS, return
    the smallest ``{...}`` JSON object that fully contains it, parsed. Used to
    pull data islands out of a vendor page's inline scripts.
    """
    anchor = text.find(needle) if isinstance(needle, str) else int(needle)
    if anchor < 0:
        return None

    depth = 0
    start = anchor
    while start >= 0:
        char = text[start]
        if char == '}':
            depth += 1
        elif char == '{':
            if depth == 0:
                break
            depth -= 1
        start -= 1
    if start < 0:
        return None

    depth = 0
    end = start
    while end < len(text):
        char = text[end]
        if char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0:
                break
        end += 1

    try:
        return json.loads(text[start:end + 1])
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Manufacturer / identifier resolution
# ---------------------------------------------------------------------------

def asset_supports_vendor_lookup(asset):
    name = _normalize(getattr(asset.asset_type, 'name', ''))
    return any(_normalize(keyword) in name for keyword in SUPPORTED_ASSET_TYPE_KEYWORDS)


def detect_manufacturer(asset, device=None):
    device = device or {}
    haystack = ' '.join(
        str(value or '').lower()
        for value in (
            asset.vendor,
            device.get('manufacturer'),
            device.get('model'),
            (asset.attribute_values or {}).get('Brand'),
            (asset.attribute_values or {}).get('brand'),
            (asset.attribute_values or {}).get('Manufacturer'),
            (asset.attribute_values or {}).get('model'),
            asset.notes,
        )
    )
    if any(hint in haystack for hint in DELL_HINTS):
        return 'dell'
    if any(hint in haystack for hint in LENOVO_HINTS):
        return 'lenovo'
    return ''


def resolve_service_tag(asset, device=None, manufacturer=None):
    device = device or {}
    attrs = asset.attribute_values or {}
    # Dell keys its support pages by service tag, which is usually the same value
    # SureMDM reports as the system tag. Lenovo keys by serial number.
    candidates = [
        device.get('system_tag'),
        attrs.get('System Tag'),
        attrs.get('system_tag'),
        attrs.get('Service Tag'),
        attrs.get('service_tag'),
        asset.serial_number,
        device.get('serial_number'),
        asset.asset_id,
    ]
    for candidate in candidates:
        text = str(candidate or '').strip()
        if not text:
            continue
        if manufacturer == 'dell':
            if not DELL_SERVICE_TAG_RE.match(text):
                continue
            return text.upper()
        if manufacturer == 'lenovo':
            # Skip GUID-style system tags / MDM ids - Lenovo keys by serial.
            if not LENOVO_SERIAL_RE.match(text):
                continue
            return text.upper()
        return text
    return ''


# ---------------------------------------------------------------------------
# Dell
# ---------------------------------------------------------------------------

DELL_OVERVIEW_URL = 'https://www.dell.com/support/home/en-us/product-support/servicetag/{tag}/overview'


def _dell_pick_asset(assets, tag):
    normalized = _normalize(tag)
    for item in assets or []:
        if not isinstance(item, dict):
            continue
        item_tag = item.get('serviceTag') or item.get('ServiceTag') or item.get('servicetag')
        if _normalize(item_tag) == normalized:
            return item
    return assets[0] if assets and isinstance(assets[0], dict) else None


def _dell_warranty_from_entitlements(entitlements):
    rows = []
    for item in entitlements or []:
        if not isinstance(item, dict):
            continue
        plan = (
            item.get('serviceLevelDescription')
            or item.get('ServiceLevelDescription')
            or item.get('serviceLevelCode')
            or item.get('entitlementType')
            or ''
        )
        start = item.get('startDate') or item.get('StartDate')
        end = item.get('endDate') or item.get('EndDate')
        if not (plan or end):
            continue
        rows.append({
            'plan': str(plan).strip(),
            'start_date': _iso(start),
            'end_date': _iso(end),
            'type': str(item.get('entitlementType') or '').strip(),
        })

    # Sort by coverage end date (latest first); when several entitlements share
    # the latest end date - e.g. an add-on like Accidental Damage running
    # alongside the base support plan - prefer an EXTENDED entry over the
    # original INITIAL grant, since that's the one reflecting a renewal and is
    # what a technician means by "the current plan".
    rows.sort(key=lambda r: (r.get('end_date') or '', r.get('type') == 'EXTENDED'), reverse=True)
    overall_start = min((r['start_date'] for r in rows if r['start_date']), default='')
    overall_end = rows[0]['end_date'] if rows else ''
    return {
        'plan': rows[0]['plan'] if rows else '',
        'start_date': overall_start,
        'end_date': overall_end,
        'status': _warranty_status(overall_end),
        'entitlements': rows,
    }


def _dell_specs_from_components(components):
    """
    Build the "Review Product Specifications" line-item list from Dell's
    asset-components response. Each shipped configuration option (e.g. "Windows
    11 Pro, English") appears there as several *manufacturing* part rows
    sharing one ``itemNumber`` (the SKU code shown on Dell's own page, e.g.
    "619-APTP") and the same ``itemDescription``; ``partNumber`` is the
    lower-level manufacturing part id, not the SKU, so it's not used as the
    row key. Deduplicated by itemNumber, since the same code repeats once per
    manufacturing part.
    """
    items = []
    if isinstance(components, dict):
        items = components.get('components') or components.get('Components') or []
    elif isinstance(components, list):
        items = components

    specs = []
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        code = item.get('itemNumber') or item.get('ItemNumber') or item.get('partNumber') or item.get('code') or ''
        desc = (
            item.get('itemDescription')
            or item.get('ItemDescription')
            or item.get('partDescription')
            or item.get('description')
            or ''
        )
        if not code or not desc or code in seen:
            continue
        seen.add(code)
        specs.append({'code': str(code).strip(), 'description': str(desc).strip()})

    # Dell's own "Review Product Specifications" page lists codes in
    # descending order; match that so the table reads the way IT expects.
    specs.sort(key=lambda s: s['code'], reverse=True)
    return specs


def fetch_dell_support(service_tag):
    """
    Look up a Dell asset's warranty entitlements and original configuration via
    the Dell TechDirect API (configured under Integrations -> Dell Warranty).
    Dell blocks unauthenticated scraping of its support site, so the API is the
    only reliable path.
    """
    from apps.integrations.views import get_dell_client, get_dell_connection
    from apps.integrations.dell import DellComponentsUnavailable, DellError

    connection = get_dell_connection()
    if not connection or not connection.is_active:
        raise VendorSupportError(
            'Dell warranty lookups need the Dell TechDirect API. Add the API credentials under '
            'Integrations -> Dell Warranty, then try again.'
        )
    if not connection.client_id or not connection.client_secret:
        raise VendorSupportError('The Dell TechDirect API connection is missing its client ID or secret.')

    tag = service_tag.strip().upper()
    try:
        client = get_dell_client(connection)
        assets = client.asset_entitlements([tag])
    except DellError as exc:
        raise VendorSupportError(f'Dell API: {exc}', status_code=getattr(exc, 'status_code', None))

    asset = _dell_pick_asset(assets, tag)
    if not asset:
        raise VendorSupportError(f'The Dell TechDirect API has no asset record for service tag {tag}.')

    warranty = _dell_warranty_from_entitlements(asset.get('entitlements') or asset.get('entitlementList') or [])
    product_name = (
        asset.get('productLineDescription')
        or asset.get('productFamily')
        or asset.get('systemDescription')
        or ''
    )
    ship_date = asset.get('shipDate') or asset.get('ShipDate')

    specs = []
    components_note = ''
    try:
        components = client.asset_components(tag)
        specs = _dell_specs_from_components(components)
        if not product_name and isinstance(components, dict):
            product_name = components.get('systemDescription') or ''
    except DellComponentsUnavailable as exc:
        components_note = str(exc)
    except DellError as exc:
        components_note = f'Original configuration could not be retrieved from Dell: {exc}'

    if not warranty['entitlements'] and not specs and not product_name:
        raise VendorSupportError(f'The Dell TechDirect API returned no details for service tag {tag}.')

    return {
        'product_name': str(product_name).strip(),
        'ship_date': _parse_date(ship_date),
        'warranty': warranty,
        'product_specifications': specs,
        'source_url': DELL_OVERVIEW_URL.format(tag=quote(tag)),
        'raw': {'asset_entitlements': asset, 'components_note': components_note},
    }


# ---------------------------------------------------------------------------
# Lenovo
# ---------------------------------------------------------------------------

# Lenovo renders warranty client-side, but the product support page ships a
# data island in its inline scripts: an object keyed by "BaseWarranties" that
# also carries the shipped date, machine type and product name. That's what we
# parse - the older /api/v4/... JSON endpoints now 404.
LENOVO_PRODUCT_PAGE = 'https://pcsupport.lenovo.com/us/en/products/{serial}'
LENOVO_WARRANTY_ARRAY_KEYS = (
    'BaseWarranties',
    'UpmaWarranties',
    'AodWarranties',
    'InstantWarranties',
    'SaeWarranties',
    'ContractWarranties',
)


def _lenovo_warranty_from_island(island):
    entitlements = []
    seen = set()
    for key in LENOVO_WARRANTY_ARRAY_KEYS:
        for item in island.get(key) or []:
            if not isinstance(item, dict):
                continue
            plan = (
                item.get('Name')
                or item.get('Description')
                or item.get('WarrentyType')
                or item.get('DeliveryType')
                or ''
            )
            start = item.get('Start') or item.get('StartDate')
            end = item.get('End') or item.get('EndDate')
            if not (plan or end):
                continue
            row = {
                'plan': str(plan).strip(),
                'start_date': _iso(start),
                'end_date': _iso(end),
                'type': str(item.get('Type') or key.replace('Warranties', '')).strip(),
                'status': str(item.get('StatusV2') or '').strip().lower(),
            }
            dedupe_key = (row['plan'], row['start_date'], row['end_date'])
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            entitlements.append(row)

    entitlements.sort(key=lambda r: r.get('end_date') or '', reverse=True)

    period = island.get('EntireWarrantyPeriod') or {}
    overall_start = _epoch_ms_to_iso(period.get('Start')) or (entitlements[-1]['start_date'] if entitlements else '')
    overall_end = _epoch_ms_to_iso(period.get('End')) or (entitlements[0]['end_date'] if entitlements else '')
    latest = entitlements[0] if entitlements else {}
    return {
        'plan': latest.get('plan', ''),
        'start_date': overall_start,
        'end_date': overall_end,
        'status': _warranty_status(overall_end),
        'entitlements': entitlements,
    }


def _lenovo_specs_from_island(island, product_name):
    """
    Lenovo doesn't publish a shipped bill-of-materials the way Dell does, so the
    "original configuration" here is the identifying spec: product, machine type,
    model, MTM and shipped date, presented as labelled rows.
    """
    machine_type = str(island.get('MachineType') or '').strip()
    mode = str(island.get('Mode') or island.get('MTM') or '').strip()
    model = f'{machine_type}{mode}'.strip()
    rows = [
        ('Product', product_name or str(island.get('ProductName') or '').strip()),
        ('Machine Type', machine_type),
        ('Model', model if model != machine_type else ''),
        ('MTM', str(island.get('MTM') or '').strip()),
        ('Serial', str(island.get('Serial') or '').strip()),
        ('Manufacture Date', _iso(island.get('ManufactureDate'))),
        ('Shipped Date', _iso(island.get('Shiped'))),
        ('Ship-to Country', str(island.get('ShipToCountry') or island.get('Country') or '').strip()),
    ]
    return [{'code': label, 'description': value} for label, value in rows if value]


def fetch_lenovo_support(serial):
    serial = serial.strip()
    source_url = LENOVO_PRODUCT_PAGE.format(serial=quote(serial))
    html = _http_get(source_url)

    island = _extract_enclosing_object(html, '"BaseWarranties"')
    config = _extract_enclosing_object(html, '"product":{') or {}
    product = config.get('product') if isinstance(config, dict) else {}
    product_name = str((product or {}).get('Name') or '').strip()

    if island is None:
        if product_name:
            island = {}
        else:
            raise VendorSupportError(
                'Lenovo did not return warranty or configuration data for this serial '
                '(the support page markup may have changed, or the serial is unknown).'
            )

    if not product_name:
        product_name = str(island.get('ProductName') or '').strip()

    warranty = _lenovo_warranty_from_island(island)
    specs = _lenovo_specs_from_island(island, product_name)

    if not warranty['entitlements'] and not product_name and not specs:
        raise VendorSupportError('Lenovo returned the support page but no warranty or product details were found in it.')

    return {
        'product_name': product_name,
        'ship_date': _parse_date(island.get('Shiped')),
        'warranty': warranty,
        'product_specifications': specs,
        'source_url': source_url,
        'raw': {'warranty_island': island, 'product': product},
    }


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def _fetcher_for(manufacturer):
    # Resolved by name (not a module-level dict) so tests can patch
    # ``fetch_dell_support`` / ``fetch_lenovo_support`` on this module.
    if manufacturer == 'dell':
        return fetch_dell_support
    if manufacturer == 'lenovo':
        return fetch_lenovo_support
    return None


def refresh_asset_support_info(asset, device=None, force=True):
    """
    Fetch (or re-fetch) manufacturer support data for ``asset`` and upsert the
    cached :class:`~apps.inventory.models.AssetSupportInfo`. Never raises for an
    expected scrape failure - the failure is recorded on the row instead.

    Returns the ``AssetSupportInfo`` instance (created if needed).
    """
    from .models import AssetSupportInfo

    info, _ = AssetSupportInfo.objects.get_or_create(asset=asset)

    if not asset_supports_vendor_lookup(asset):
        info.fetch_status = 'unsupported'
        info.fetch_error = 'Vendor support lookup only applies to laptops and monitors.'
        info.save()
        return info

    manufacturer = detect_manufacturer(asset, device)
    service_tag = resolve_service_tag(asset, device, manufacturer)
    info.manufacturer = manufacturer
    info.service_tag = service_tag

    if not manufacturer:
        info.fetch_status = 'error'
        info.fetch_error = 'Could not tell whether this asset is a Dell or Lenovo device.'
        info.save()
        return info
    if not service_tag:
        info.fetch_status = 'error'
        info.fetch_error = (
            'No Dell service tag found for this asset.'
            if manufacturer == 'dell'
            else 'No Lenovo serial number found for this asset.'
        )
        info.save()
        return info
    if not _scrape_enabled():
        info.fetch_status = 'error'
        info.fetch_error = 'Vendor support scraping is disabled (VENDOR_SUPPORT_SCRAPE=false).'
        info.save()
        return info

    try:
        result = _fetcher_for(manufacturer)(service_tag)
    except VendorSupportError as exc:
        info.fetch_status = 'error'
        info.fetch_error = str(exc)
        info.fetched_at = timezone.now()
        info.save()
        return info

    info.product_name = result.get('product_name', '')
    info.ship_date = result.get('ship_date')
    info.warranty = result.get('warranty') or {}
    info.product_specifications = result.get('product_specifications') or []
    info.source_url = result.get('source_url', '')
    info.raw = result.get('raw') or {}
    info.fetch_status = 'success'
    info.fetch_error = ''
    info.fetched_at = timezone.now()
    info.save()
    return info
