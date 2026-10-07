"""
Turns Google device records into the rows the user dashboard's "Devices" section shows.

Two sources describe a user's devices, and neither is complete on its own:

* Directory API ``mobiledevices`` - Android / iOS / Google Sync devices the user has added
  their account to (the Admin console's mobile management).
* Cloud Identity ``devices`` + ``deviceUsers`` - the broader Devices list, which also holds
  Windows / macOS / Linux / ChromeOS machines (endpoint verification, Windows management).

They overlap for managed mobile devices, so rows are merged by serial number.
Google reports an OS family, not a form factor: nothing says "laptop" vs "desktop". The
laptop label therefore comes from the portal's own asset inventory when the serial matches,
and otherwise from an unambiguous model name (MacBook, ThinkPad, ...), else it is left unset.
"""

CLOUD_PLATFORMS = {
    'ANDROID': 'Android',
    'IOS': 'iOS',
    'GOOGLE_SYNC': 'Google Sync',
    'WINDOWS': 'Windows',
    'MAC_OS': 'macOS',
    'LINUX': 'Linux',
    'CHROME_OS': 'ChromeOS',
}
MOBILE_PLATFORMS = {'Android', 'iOS', 'Google Sync'}
APPLE_PLATFORMS = {'iOS', 'macOS'}

LAPTOP_MODEL_WORDS = (
    'macbook', 'thinkpad', 'latitude', 'elitebook', 'probook', 'zbook', 'chromebook', 'laptop', 'notebook',
)
DESKTOP_MODEL_WORDS = (
    'imac', 'mac mini', 'mac studio', 'mac pro', 'optiplex', 'thinkcentre', 'prodesk', 'elitedesk', 'desktop', 'tower',
)


def _text(value):
    return str(value).strip() if value not in (None, '') else ''


def _tidy_make(value):
    """Android reports makers in whatever case the vendor shipped ("samsung"); tidy only all-lowercase ones."""
    value = _text(value)
    return value.title() if value.islower() else value


def mobile_platform(raw):
    """Platform from a Directory mobile device: its ``type`` first, then the OS string."""
    kind = _text(raw.get('type')).upper()
    os_name = _text(raw.get('os')).lower()
    if 'ANDROID' in kind or os_name.startswith('android'):
        return 'Android'
    if kind.startswith('IOS') or os_name.startswith('ios') or 'iphone' in _text(raw.get('model')).lower():
        return 'iOS'
    if 'SYNC' in kind:
        return 'Google Sync'
    return ''


def category_of(platform):
    if platform in MOBILE_PLATFORMS:
        return 'mobile'
    return 'computer' if platform else 'unknown'


def guess_form_factor(model):
    """'laptop' / 'desktop' only when the model name is unambiguous, else ''."""
    lowered = _text(model).lower()
    if any(word in lowered for word in LAPTOP_MODEL_WORDS):
        return 'laptop'
    if any(word in lowered for word in DESKTOP_MODEL_WORDS):
        return 'desktop'
    return ''


def _finish(row):
    platform = row['platform']
    if not row['make'] and platform in APPLE_PLATFORMS:
        row['make'] = 'Apple'
    row['category'] = category_of(platform)
    if row['category'] == 'computer':
        row['form_factor'] = guess_form_factor(row['model'])
        row['form_factor_source'] = 'model' if row['form_factor'] else ''
    return row


def _base_row(source):
    return {
        'sources': [source],
        'platform': '',
        'category': 'unknown',
        'form_factor': '',
        'form_factor_source': '',
        'make': '',
        'model': '',
        'serial': '',
        'os': '',
        'hostname': '',
        'ownership': '',
        'status': '',
        'first_seen': '',
        'last_sync': '',
        'user_agent': '',
        'device_id': '',
        'users': [],
        # email -> when that user's account last synced on this device (a device can have several users).
        'user_syncs': {},
    }


def normalize_mobile_device(raw):
    row = _base_row('mobile')
    row.update({
        'platform': mobile_platform(raw),
        'make': _tidy_make(raw.get('manufacturer') or raw.get('brand')),
        'model': _text(raw.get('model')),
        'serial': _text(raw.get('serialNumber')),
        'os': _text(raw.get('os')),
        'hostname': _text(raw.get('hardware')),
        'status': _text(raw.get('status')).replace('_', ' ').capitalize(),
        'first_seen': _text(raw.get('firstSync')),
        'last_sync': _text(raw.get('lastSync')),
        'user_agent': _text(raw.get('userAgent')),
        'device_id': _text(raw.get('resourceId') or raw.get('deviceId')),
        'users': sorted({_text(e).lower() for e in raw.get('email') or [] if _text(e)}),
    })
    row['user_syncs'] = {email: row['last_sync'] for email in row['users'] if row['last_sync']}
    return _finish(row)


def normalize_cloud_device(device, device_user):
    row = _base_row('cloud_identity')
    row.update({
        'platform': CLOUD_PLATFORMS.get(_text(device.get('deviceType')).upper(), ''),
        'make': _tidy_make(device.get('manufacturer') or device.get('brand')),
        'model': _text(device.get('model')),
        'serial': _text(device.get('serialNumber')),
        'os': _text(device.get('osVersion')),
        'hostname': _text(device.get('hostname')),
        'ownership': {'COMPANY': 'company', 'BYOD': 'personal'}.get(_text(device.get('ownerType')).upper(), ''),
        'status': _text(device_user.get('managementState')).replace('_', ' ').capitalize(),
        # Per user, not per device: when this person first signed in / last synced here.
        'first_seen': _text(device_user.get('createTime') or device_user.get('firstSyncTime')),
        'last_sync': _text(device_user.get('lastSyncTime') or device.get('lastSyncTime')),
        'user_agent': _text(device_user.get('userAgent')),
        'device_id': _text(device.get('name')),
        'users': [_text(device_user.get('userEmail')).lower()] if _text(device_user.get('userEmail')) else [],
    })
    if row['users'] and row['last_sync']:
        row['user_syncs'] = {row['users'][0]: row['last_sync']}
    return _finish(row)


def cloud_devices_for_user(snapshot, email):
    """Rows for ``email`` out of a ``cloud_identity_devices()`` snapshot."""
    wanted = email.lower()
    rows = []
    for device_user in snapshot.get('device_users') or []:
        if _text(device_user.get('userEmail')).lower() != wanted:
            continue
        # "devices/{device}/deviceUsers/{id}" -> "devices/{device}"
        device_name = '/'.join(_text(device_user.get('name')).split('/')[:2])
        rows.append(normalize_cloud_device(snapshot['devices'].get(device_name) or {}, device_user))
    return rows


def cloud_fleet_devices(snapshot):
    """One row per device in a ``cloud_identity_devices()`` snapshot, with every user signed in on it."""
    by_device = {}
    for device_user in snapshot.get('device_users') or []:
        name = '/'.join(_text(device_user.get('name')).split('/')[:2])
        by_device.setdefault(name, []).append(device_user)
    rows = []
    for name, users in by_device.items():
        newest = max(users, key=lambda u: _text(u.get('lastSyncTime')))
        row = normalize_cloud_device(snapshot['devices'].get(name) or {'name': name}, newest)
        row['users'] = sorted({_text(u.get('userEmail')).lower() for u in users if _text(u.get('userEmail'))})
        row['user_syncs'] = {
            _text(u.get('userEmail')).lower(): _text(u.get('lastSyncTime') or (snapshot['devices'].get(name) or {}).get('lastSyncTime'))
            for u in users
            if _text(u.get('userEmail')) and (u.get('lastSyncTime') or (snapshot['devices'].get(name) or {}).get('lastSyncTime'))
        }
        row['first_seen'] = min(
            (_text(u.get('createTime') or u.get('firstSyncTime')) for u in users if u.get('createTime') or u.get('firstSyncTime')),
            default='',
        )
        rows.append(row)
    return rows


def _merge(first, second):
    """Fill ``first``'s gaps from ``second``. Cloud Identity wins ties: it reports more fields."""
    merged = dict(first)
    for key, value in second.items():
        if key == 'sources':
            merged['sources'] = sorted(set(first['sources']) | set(value))
        elif key == 'users':
            merged['users'] = sorted(set(first['users']) | set(value))
        elif key == 'user_syncs':
            # Per user, keep the newer of the two sources' times (ISO timestamps sort as text).
            merged['user_syncs'] = {
                email: max(first['user_syncs'].get(email, ''), value.get(email, ''))
                for email in set(first['user_syncs']) | set(value)
            }
        elif not merged.get(key):
            merged[key] = value
    return _finish(merged)


def merge_devices(rows):
    """
    One row per physical device. Rows sharing a serial number are the same device. Rows without
    one are merged across sources only when unambiguous (a single candidate per source with the
    same platform and model); two identical phones with no serial must not collapse into one.
    """
    by_serial, loose, merged = {}, [], []
    for row in sorted(rows, key=lambda r: r['sources'] != ['cloud_identity']):  # cloud rows first
        serial = row['serial'].upper()
        if not serial:
            loose.append(row)
        elif serial in by_serial:
            by_serial[serial] = _merge(by_serial[serial], row)
        else:
            by_serial[serial] = row
    merged.extend(by_serial.values())

    groups = {}
    for row in loose:
        groups.setdefault((row['platform'], row['model'].lower()), []).append(row)
    for group in groups.values():
        cloud = [r for r in group if 'cloud_identity' in r['sources']]
        mobile = [r for r in group if 'mobile' in r['sources'] and 'cloud_identity' not in r['sources']]
        if len(group) == 2 and len(cloud) == 1 and len(mobile) == 1:
            merged.append(_merge(cloud[0], mobile[0]))
        else:
            merged.extend(group)

    merged.sort(key=lambda r: r['last_sync'], reverse=True)
    for index, row in enumerate(merged):
        row['id'] = f'device-{index}'
    return merged


def apply_portal_assets(rows, assets_by_serial, is_laptop):
    """
    Attach the portal asset (matched on serial number) to each row, and let its asset type
    settle laptop vs desktop for computers. The portal is the authority on what the company
    bought, so it overrides a model-name guess.
    """
    result = []
    for row in rows:
        row = dict(row)
        asset = assets_by_serial.get(row['serial'].upper()) if row['serial'] else None
        row['portal_asset'] = None
        if asset:
            row['portal_asset'] = {
                'id': asset.id,
                'asset_id': asset.asset_id,
                'type': asset.asset_type.name,
                'status': asset.status,
            }
            if row['category'] == 'computer':
                row['form_factor'] = 'laptop' if is_laptop(asset) else asset.asset_type.name.lower()
                row['form_factor_source'] = 'portal'
        result.append(row)
    return result
