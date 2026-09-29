"""
Turns Google Workspace Reports API audit items (Drive / login / Gmail) into the
flat rows the user activity dashboard shows.

Reports API events carry ``parameters: [{name, value | boolValue | intValue |
multiValue | messageValue | multiMessageValue}]``. Field names below come from
Google's audit-log reference; anything an account doesn't supply comes back as an
empty string rather than an error.
"""
import re
from datetime import datetime, timezone

DRIVE_SHARE_EVENTS = ('change_user_access', 'change_document_visibility', 'change_document_access_scope')
# Drive "visibility" values that expose a file beyond the organisation.
EXTERNAL_VISIBILITIES = {'public_on_the_web', 'people_with_link', 'shared_externally'}
LOGIN_LABELS = {
    'login_success': 'Signed in',
    'login_failure': 'Sign-in failed',
    'logout': 'Signed out',
    'login_verification': 'Verification challenge',
    'login_challenge': 'Sign-in challenge',
    'suspicious_login': 'Suspicious sign-in',
}
# event_info.mail_event_type values in the Gmail audit log that mean mail moved.
MAIL_EVENT_TYPES = {1: 'sent', 2: 'received', 10: 'forwarded', 11: 'auto_forwarded'}
# Directions where the user's mail goes to someone else, so recipients can be outside the org.
OUTBOUND_DIRECTIONS = {'sent', 'forwarded', 'auto_forwarded'}
MAX_FIELD_LENGTH = 300


def _as_list(value):
    if value is None or value == '':
        return []
    return value if isinstance(value, list) else [value]


def _first(value):
    values = _as_list(value)
    return values[0] if values else ''


def _text(value):
    return str(_first(value))


def flatten_parameters(parameters, prefix=''):
    """
    Flatten an event's parameter list to ``{'dotted.name': value}``. Nested messages
    get a dotted prefix, and a name that repeats collects into a list, so callers
    can look fields up by name whatever shape the account returns.
    """
    flat = {}

    def put(name, value):
        flat[name] = _as_list(flat[name]) + _as_list(value) if name in flat else value

    for parameter in parameters or []:
        name = f'{prefix}{parameter.get("name", "")}'
        if 'value' in parameter:
            put(name, parameter['value'])
        elif 'boolValue' in parameter:
            put(name, parameter['boolValue'])
        elif 'intValue' in parameter:
            put(name, int(parameter['intValue']))
        elif 'multiValue' in parameter:
            put(name, list(parameter['multiValue']))
        elif 'multiIntValue' in parameter:
            put(name, [int(value) for value in parameter['multiIntValue']])
        elif 'messageValue' in parameter:
            for key, value in flatten_parameters(parameter['messageValue'].get('parameter'), f'{name}.').items():
                put(key, value)
        elif 'multiMessageValue' in parameter:
            for message in parameter['multiMessageValue']:
                for key, value in flatten_parameters(message.get('parameter'), f'{name}.').items():
                    put(key, value)
    return flat


def _event_time(item):
    raw = (item.get('id') or {}).get('time') or ''
    if str(raw).isdigit():  # some responses give epoch seconds instead of RFC 3339
        return datetime.fromtimestamp(int(raw), timezone.utc).isoformat()
    return raw


def classify_share_scope(params, internal_domains):
    """'internal', 'external', or '' when the event doesn't say. Google's own verdict wins."""
    change = _text(params.get('visibility_change')).lower()
    if change in ('internal', 'external'):
        return change
    target_domain = _text(params.get('target_domain')).lower()
    if target_domain:
        return 'internal' if target_domain in internal_domains else 'external'
    if _first(params.get('visibility')) in EXTERNAL_VISIBILITIES:
        return 'external'
    return ''


def _share_action(event_name, params):
    """granted / removed / changed, so taking access away isn't counted as sharing."""
    if event_name == 'change_user_access':
        new_value = [str(value).lower() for value in _as_list(params.get('new_value'))]
        return 'removed' if new_value == ['none'] else 'granted'
    if event_name == 'change_document_visibility':
        return 'removed' if _first(params.get('visibility')) == 'private' else 'granted'
    return 'changed'


def normalize_drive_events(item, internal_domains):
    """Download and sharing rows from one Drive audit item (which may hold several events)."""
    rows = []
    for event in item.get('events') or []:
        name = event.get('name') or ''
        is_download = name == 'download'
        if not is_download and name not in DRIVE_SHARE_EVENTS:
            continue
        params = flatten_parameters(event.get('parameters'))
        old_value = ', '.join(map(str, _as_list(params.get('old_value'))))
        new_value = ', '.join(map(str, _as_list(params.get('new_value'))))
        rows.append({
            'time': _event_time(item),
            'source': 'drive',
            'category': 'download' if is_download else 'share',
            'event': name,
            'action': 'downloaded' if is_download else _share_action(name, params),
            'title': _text(params.get('doc_title')),
            'doc_type': _text(params.get('doc_type')),
            'doc_id': _text(params.get('doc_id')),
            'owner': _text(params.get('owner')),
            'visibility': _text(params.get('visibility')),
            'old_visibility': _text(params.get('old_visibility')),
            'target_user': _text(params.get('target_user')),
            'target_domain': _text(params.get('target_domain')),
            'access_change': f'{old_value} → {new_value}' if new_value else '',
            'scope': '' if is_download else classify_share_scope(params, internal_domains),
            'ip': item.get('ipAddress') or '',
        })
    return rows


def summarize_drive(rows):
    shares = [row for row in rows if row['category'] == 'share' and row['action'] != 'removed']
    return {
        'downloads': sum(1 for row in rows if row['category'] == 'download'),
        'shared_external': sum(1 for row in shares if row['scope'] == 'external'),
        'shared_internal': sum(1 for row in shares if row['scope'] == 'internal'),
    }


def normalize_login_events(item):
    rows = []
    for event in item.get('events') or []:
        name = event.get('name') or ''
        params = flatten_parameters(event.get('parameters'))
        rows.append({
            'time': _event_time(item),
            'source': 'login',
            'category': 'signin',
            'event': name,
            'label': LOGIN_LABELS.get(name) or name.replace('_', ' ').capitalize(),
            'login_type': _text(params.get('login_type')),
            'ip': item.get('ipAddress') or '',
            'risk': name == 'login_failure' or name.startswith('suspicious'),
        })
    return rows


def _find_param(params, suffix):
    return next((value for key, value in params.items() if key.endswith(suffix)), None)


# ':' is excluded so Google's "service::address" form (gmail-ui::a@b.com) yields the address alone.
EMAIL_PATTERN = re.compile(r'[^@\s<>,;:"\']+@[^@\s<>,;:"\']+\.[^@\s<>,;:"\']+')
SENDER_MARKERS = ('source', 'from', 'sender')
RECIPIENT_MARKERS = ('destination', 'to', 'recipient', 'rcpt')


def _has_marker(segment, markers):
    """True if a name segment has ``marker`` (or its plural) as a whole word: flattened_destinations, from_header_address."""
    words = segment.split('_')
    return any(word == marker or word == f'{marker}s' for word in words for marker in markers)


def _addresses_under(params, markers):
    """
    Email addresses held by any parameter whose dotted name has a segment containing
    one of ``markers`` as a word, e.g. ``message_info.source.address``,
    ``message_info.source.from_header_address`` or ``message_info.flattened_destinations``.
    Matching on "the value is an address" rather than one exact field name keeps this
    working whichever way the account nests them. ``.address`` fields come first and
    duplicates are dropped.
    """
    matched = []
    for key, value in params.items():
        segments = key.lower().split('.')
        if not any(_has_marker(segment, markers) for segment in segments):
            continue
        addresses = [address for part in _as_list(value) for address in EMAIL_PATTERN.findall(str(part))]
        if addresses:
            matched.append((0 if segments[-1] == 'address' else 1, addresses))
    ordered = []
    for _, addresses in sorted(matched, key=lambda item: item[0]):
        for address in addresses:
            if address not in ordered:
                ordered.append(address)
    return ordered


def _to_int(value):
    """An int, or None when the field is absent or not numeric (so the UI can show a dash, not 0)."""
    try:
        return int(_first(value))
    except (TypeError, ValueError):
        return None


def _clip(value):
    if isinstance(value, list):
        return [str(part)[:MAX_FIELD_LENGTH] for part in value[:20]]
    return str(value)[:MAX_FIELD_LENGTH]


def _is_internal(address, internal_domains):
    domain = address.rsplit('@', 1)[-1].lower()
    return any(domain == internal or domain.endswith(f'.{internal}') for internal in internal_domains)


def normalize_gmail_events(item, internal_domains=None):
    """
    Sent / received / forwarded rows from a Gmail audit item. Google documents only
    ``event_info.mail_event_type``; subject, sender and recipients are read from
    whichever ``message_info.*`` fields the account supplies, and every field is
    passed through in ``fields`` so what a given edition really returns is visible.

    With ``internal_domains`` given, outbound mail (sent / forwarded) is checked for
    recipients outside those domains and ``external_with_attachments`` is set when
    such a message also carried attachments. Received mail is never flagged: its
    recipient is the mailbox owner. Without ``internal_domains`` nothing is flagged,
    rather than treating every address as external.
    """
    rows = []
    for event in item.get('events') or []:
        params = flatten_parameters(event.get('parameters'))
        try:
            direction = MAIL_EVENT_TYPES.get(int(_first(_find_param(params, 'mail_event_type'))))
        except (TypeError, ValueError):
            direction = None
        if not direction:
            continue

        recipients = _addresses_under(params, RECIPIENT_MARKERS)
        attachments = _to_int(_find_param(params, 'num_message_attachments'))
        outbound = direction in OUTBOUND_DIRECTIONS and internal_domains is not None
        external_recipients = [a for a in recipients if not _is_internal(a, internal_domains)] if outbound else []
        rows.append({
            'time': _event_time(item),
            'direction': direction,
            'subject': _text(_find_param(params, 'subject')),
            'sender': next(iter(_addresses_under(params, SENDER_MARKERS)), ''),
            'recipients': recipients,
            'external_recipients': external_recipients,
            'attachments': attachments,
            'external_with_attachments': bool(external_recipients) and bool(attachments),
            'size': _to_int(_find_param(params, 'payload_size')),  # bytes
            'fields': {key: _clip(value) for key, value in params.items()},
        })
    return rows
