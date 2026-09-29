"""
Client for the Google Workspace Admin SDK Directory API (read-only).

Auth is a service account with domain-wide delegation: sign a JWT whose ``sub``
is a super admin, exchange it at Google's token endpoint for a ~1h bearer token,
then call:

  GET /users?domain=<domain>&projection=full          (people in one domain)
  GET /groups?customer=my_customer                    (every group in the account)
  GET /groups/<groupKey>/members                      (direct members of a group)

The Directory API has no "which groups is everyone in" call, and
``groups?userKey=`` is one request per user. Reading each group's members once
and inverting the result costs one request per *group*, which is far fewer on
any realistic directory.
"""
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import ProxyHandler, Request, build_opener

import jwt

# Fixed rather than read from the pasted key file, so a hand-edited JSON can't
# redirect the signed assertion to another host.
TOKEN_URL = 'https://oauth2.googleapis.com/token'
DIRECTORY_BASE = 'https://admin.googleapis.com/admin/directory/v1'
REPORTS_BASE = 'https://admin.googleapis.com/admin/reports/v1'
SCOPES = (
    'https://www.googleapis.com/auth/admin.directory.user.readonly',
    'https://www.googleapis.com/auth/admin.directory.group.readonly',
)
# Each of these gets its own token, on purpose: Google rejects the whole JWT if any
# scope in it isn't delegated. Bundling them with SCOPES would break the directory
# for anyone who hasn't added the reports scopes yet, and bundling them with each
# other would blame both when only one is missing. Audit covers the Drive, login
# and Gmail event logs; usage covers the per-day email counts.
AUDIT_SCOPES = ('https://www.googleapis.com/auth/admin.reports.audit.readonly',)
USAGE_SCOPES = ('https://www.googleapis.com/auth/admin.reports.usage.readonly',)

# Google reports quota problems as 403 + one of these reasons, not only 429.
RETRYABLE_REASONS = {'rateLimitExceeded', 'userRateLimitExceeded', 'quotaExceeded', 'backendError'}
MAX_ATTEMPTS = 4
GROUP_FETCH_WORKERS = 8
USAGE_FETCH_WORKERS = 8
# Usage reports trail real time; asking for a day Google hasn't computed yet is a 400.
USAGE_LAG_DAYS = 3
MAX_ACTIVITY_EVENTS = 3000
# The Directory API stamps users who have never signed in with the Unix epoch.
NEVER_LOGGED_IN = '1970-01-01T00:00:00.000Z'


class GoogleWorkspaceError(RuntimeError):
    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


def _error_detail(exc):
    """Pull (message, reason) out of a Google error body, whichever shape it has."""
    try:
        body = json.loads(exc.read().decode('utf-8', 'replace') or '{}')
    except ValueError:
        return '', ''
    error = body.get('error')
    if isinstance(error, dict):
        reasons = error.get('errors') or [{}]
        return error.get('message') or '', reasons[0].get('reason') or ''
    # Token endpoint: {"error": "invalid_grant", "error_description": "..."}
    return body.get('error_description') or '', error or ''


class GoogleWorkspaceClient:
    def __init__(self, service_account_info, admin_email, timeout=30):
        self.service_account_info = service_account_info
        self.admin_email = admin_email
        self.timeout = timeout
        # scope tuple -> (access token, expiry epoch)
        self._tokens = {}
        self._token_lock = threading.Lock()

    @staticmethod
    def _opener():
        return build_opener(ProxyHandler({}))

    def _fetch_token(self, scopes):
        now = int(time.time())
        try:
            assertion = jwt.encode(
                {
                    'iss': self.service_account_info['client_email'],
                    'sub': self.admin_email,
                    'scope': ' '.join(scopes),
                    'aud': TOKEN_URL,
                    'iat': now,
                    'exp': now + 3600,
                },
                self.service_account_info['private_key'],
                algorithm='RS256',
            )
        except (KeyError, ValueError, TypeError, jwt.PyJWTError) as exc:
            raise GoogleWorkspaceError(
                'The saved service account key is unreadable. Upload the JSON key file again.'
            ) from exc

        request = Request(
            TOKEN_URL,
            data=urlencode({
                'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer',
                'assertion': assertion,
            }).encode('utf-8'),
            headers={'Content-Type': 'application/x-www-form-urlencoded', 'Accept': 'application/json'},
            method='POST',
        )
        try:
            with self._opener().open(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode('utf-8') or '{}')
        except HTTPError as exc:
            description, reason = _error_detail(exc)
            if reason == 'unauthorized_client':
                message = (
                    'Google refused the delegation. In the Admin console (Security > API controls > '
                    'Domain-wide delegation), edit this service account\'s existing entry and make sure '
                    f'it lists {"this scope" if len(scopes) == 1 else "these scopes"}: ' + ', '.join(scopes)
                    + '. It must match exactly, and Google can take a few minutes to apply a change.'
                )
            elif reason == 'invalid_grant':
                message = (
                    f'Google rejected the sign-in as {self.admin_email}. It must be an active super '
                    f'admin in this Workspace account, and the service account key must still be enabled. '
                    f'({description or "invalid_grant"})'
                )
            else:
                message = f'Google token request failed (HTTP {exc.code}): {description or reason or "no detail"}'
            raise GoogleWorkspaceError(message, status_code=exc.code) from exc
        except (URLError, TimeoutError) as exc:
            raise GoogleWorkspaceError(f'Could not reach Google to authenticate: {getattr(exc, "reason", exc)}') from exc

        token = payload.get('access_token')
        if not token:
            raise GoogleWorkspaceError('Google did not return an access token.')
        # Refresh a minute early so a request never goes out on a dying token.
        self._tokens[scopes] = (token, now + int(payload.get('expires_in') or 3600) - 60)
        return token

    def _token(self, scopes=SCOPES):
        with self._token_lock:
            cached = self._tokens.get(scopes)
            if cached and time.time() < cached[1]:
                return cached[0]
            return self._fetch_token(scopes)

    def _get(self, path, params=None, *, base=DIRECTORY_BASE, scopes=SCOPES):
        url = f'{base}{path}'
        if params:
            url = f'{url}?{urlencode(params)}'
        reports = base == REPORTS_BASE

        for attempt in range(1, MAX_ATTEMPTS + 1):
            request = Request(
                url,
                headers={'Authorization': f'Bearer {self._token(scopes)}', 'Accept': 'application/json'},
                method='GET',
            )
            try:
                with self._opener().open(request, timeout=self.timeout) as response:
                    raw = response.read().decode('utf-8')
                    return json.loads(raw) if raw else {}
            except HTTPError as exc:
                message, reason = _error_detail(exc)
                retryable = exc.code in (429, 500, 502, 503, 504) or (exc.code == 403 and reason in RETRYABLE_REASONS)
                if retryable and attempt < MAX_ATTEMPTS:
                    time.sleep(2 ** (attempt - 1))
                    continue
                raise GoogleWorkspaceError(
                    self._describe_http_error(exc.code, message, reason, reports=reports), status_code=exc.code
                ) from exc
            except (URLError, TimeoutError) as exc:
                if attempt < MAX_ATTEMPTS:
                    time.sleep(2 ** (attempt - 1))
                    continue
                raise GoogleWorkspaceError(f'Could not reach the Google Admin SDK: {getattr(exc, "reason", exc)}') from exc

    @staticmethod
    def _describe_http_error(code, message, reason, reports=False):
        lowered = (message or '').lower()
        if code == 403 and ('has not been used' in lowered or 'is disabled' in lowered or reason == 'accessNotConfigured'):
            return (
                'The Admin SDK API is not enabled for the Google Cloud project that owns this service '
                'account. Enable "Admin SDK API" in that project and try again.'
            )
        if code == 403 and reports:
            return (
                'Google denied access to the activity reports. The impersonated admin needs the Reports '
                'privilege (super admins have it), and this Workspace edition must include the report. '
                + (f'({message})' if message else '')
            ).strip()
        if code == 403:
            return (
                'Google denied access to the directory. The impersonated admin must be a super admin, '
                'and delegation must include both directory read-only scopes.'
                + (f' ({message})' if message else '')
            )
        if code == 400 and reports:
            return f'Google rejected the reports request. ({message})'
        if code == 400:
            return f'Google rejected the request. Check that this is a verified domain in the account. ({message})'
        if code == 401:
            return 'Google rejected the access token.'
        return f'Google Directory API returned HTTP {code}: {message or reason or "no detail"}'

    def _paginate(self, path, params, items_key):
        items = []
        page_token = None
        while True:
            page_params = dict(params)
            if page_token:
                page_params['pageToken'] = page_token
            data = self._get(path, page_params)
            items.extend(data.get(items_key) or [])
            page_token = data.get('nextPageToken')
            if not page_token:
                return items

    def ping(self, domain):
        """Cheapest calls that prove both scopes work; raises GoogleWorkspaceError otherwise."""
        self._get('/users', {'domain': domain, 'maxResults': 1})
        self._get('/groups', {'customer': 'my_customer', 'maxResults': 1})

    def list_users(self, domain):
        return self._paginate(
            '/users',
            {'domain': domain, 'projection': 'full', 'orderBy': 'email', 'maxResults': 500},
            'users',
        )

    def list_groups(self):
        return self._paginate('/groups', {'customer': 'my_customer', 'maxResults': 200}, 'groups')

    def list_group_members(self, group_key):
        return self._paginate(f'/groups/{quote(group_key, safe="")}/members', {'maxResults': 200}, 'members')

    def groups_with_members(self):
        """
        Every group in the account with its direct members attached. A group whose
        members can't be read is kept (so it still appears) with ``members_error``
        set, rather than failing the whole load.
        """
        groups = self.list_groups()
        if not groups:
            return []
        self._token()  # authenticate once up front instead of racing in the pool

        def load(group):
            try:
                return group, self.list_group_members(group['id']), ''
            except GoogleWorkspaceError as exc:
                return group, [], str(exc)

        with ThreadPoolExecutor(max_workers=GROUP_FETCH_WORKERS) as pool:
            results = list(pool.map(load, groups))

        return [{**group, 'members': members, 'members_error': error} for group, members, error in results]

    def list_activities(self, user_key, application, start, end, event_name=None, max_events=MAX_ACTIVITY_EVENTS):
        """
        Audit-log items for one user, newest first, as ``(items, truncated)``.

        ``truncated`` means the user had more than ``max_events`` matching items:
        a busy account can have tens of thousands of Drive events, so the cap is
        what keeps one page view from paging through all of them.
        """
        params = {'startTime': _rfc3339(start), 'endTime': _rfc3339(end), 'maxResults': 1000}
        if event_name:
            params['eventName'] = event_name
        path = f'/activity/users/{quote(user_key, safe="")}/applications/{application}'

        items, page_token = [], None
        while True:
            page_params = dict(params)
            if page_token:
                page_params['pageToken'] = page_token
            data = self._get(path, page_params, base=REPORTS_BASE, scopes=AUDIT_SCOPES)
            items.extend(data.get('items') or [])
            page_token = data.get('nextPageToken')
            if not page_token:
                return items, False
            if len(items) >= max_events:
                return items[:max_events], True

    def user_usage(self, user_key, day, parameters):
        """
        One day of usage counters for a user as ``{parameter: int}``, or ``None`` when
        Google has no data for that day (still being computed, or no activity).
        """
        data = self._get(
            f'/usage/users/{quote(user_key, safe="")}/dates/{day.isoformat()}',
            {'parameters': ','.join(parameters)},
            base=REPORTS_BASE,
            scopes=USAGE_SCOPES,
        )
        reports = data.get('usageReports') or []
        if not reports:
            return None
        values = {}
        for parameter in reports[0].get('parameters') or []:
            if 'intValue' in parameter:
                values[parameter['name']] = int(parameter['intValue'])
        return values

    def user_usage_series(self, user_key, days, parameters, workers=USAGE_FETCH_WORKERS):
        """
        Daily counters for the ``days`` days ending USAGE_LAG_DAYS ago, oldest first, as
        ``[{'date': 'YYYY-MM-DD', **counters}]``. Days Google has no figure for are omitted.
        A day that errors is skipped, but if *every* day errors the first error is raised
        so a missing scope surfaces instead of looking like an empty mailbox.
        """
        last_day = datetime.now(timezone.utc).date() - timedelta(days=USAGE_LAG_DAYS)
        dates = [last_day - timedelta(days=offset) for offset in range(days - 1, -1, -1)]

        def load(day):
            try:
                return day, self.user_usage(user_key, day, parameters), None
            except GoogleWorkspaceError as exc:
                return day, None, exc

        self._token(USAGE_SCOPES)  # authenticate once up front instead of racing in the pool
        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(load, dates))

        errors = [error for _, _, error in results if error]
        if errors and len(errors) == len(results):
            raise errors[0]
        return [
            {'date': day.isoformat(), **{name: values.get(name, 0) for name in parameters}}
            for day, values, _ in results
            if values is not None
        ]


def _rfc3339(moment):
    return moment.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _primary(items):
    items = items or []
    return next((item for item in items if item.get('primary')), items[0] if items else {})


def _typed_value(items, wanted_type):
    return next((item.get('value') for item in items or [] if item.get('type') == wanted_type and item.get('value')), '')


def normalize_user(raw):
    email = raw.get('primaryEmail') or ''
    name = raw.get('name') or {}
    organization = _primary(raw.get('organizations'))
    last_login = raw.get('lastLoginTime') or ''
    external_ids = raw.get('externalIds') or []

    return {
        'id': raw.get('id') or '',
        'primary_email': email,
        'domain': email.rsplit('@', 1)[-1].lower() if '@' in email else '',
        'aliases': sorted(set((raw.get('aliases') or []) + (raw.get('nonEditableAliases') or []))),
        'full_name': name.get('fullName') or ' '.join(filter(None, [name.get('givenName'), name.get('familyName')])),
        'given_name': name.get('givenName') or '',
        'family_name': name.get('familyName') or '',
        'org_unit': raw.get('orgUnitPath') or '',
        'title': organization.get('title') or '',
        'department': organization.get('department') or '',
        'cost_center': organization.get('costCenter') or '',
        'manager': _typed_value(raw.get('relations'), 'manager'),
        'employee_id': _typed_value(external_ids, 'organization') or (external_ids[0].get('value', '') if external_ids else ''),
        'phones': [
            {'type': phone.get('type') or '', 'value': phone.get('value') or ''}
            for phone in raw.get('phones') or []
            if phone.get('value')
        ],
        'is_admin': bool(raw.get('isAdmin')),
        'is_delegated_admin': bool(raw.get('isDelegatedAdmin')),
        'suspended': bool(raw.get('suspended')),
        'suspension_reason': raw.get('suspensionReason') or '',
        'archived': bool(raw.get('archived')),
        'is_enrolled_in_2sv': bool(raw.get('isEnrolledIn2Sv')),
        'is_enforced_in_2sv': bool(raw.get('isEnforcedIn2Sv')),
        'change_password_at_next_login': bool(raw.get('changePasswordAtNextLogin')),
        'created_at': raw.get('creationTime') or '',
        'last_login_at': '' if last_login == NEVER_LOGGED_IN else last_login,
        'groups': [],
    }


def build_directory(client, domain):
    """Users of ``domain`` with the groups each is a direct member of."""
    users = [normalize_user(raw) for raw in client.list_users(domain)]
    groups = client.groups_with_members()

    # Group members may be listed under an alias rather than the primary address.
    by_address = {}
    for user in users:
        for address in [user['primary_email'], *user['aliases']]:
            by_address[address.lower()] = user

    seen = {user['id']: set() for user in users}
    for group in groups:
        for member in group['members']:
            if member.get('type') != 'USER':
                continue
            user = by_address.get((member.get('email') or '').lower())
            if not user or group['id'] in seen[user['id']]:
                continue
            seen[user['id']].add(group['id'])
            user['groups'].append({
                'id': group['id'],
                'email': group.get('email') or '',
                'name': group.get('name') or group.get('email') or '',
                'role': member.get('role') or 'MEMBER',
            })

    for user in users:
        user['groups'].sort(key=lambda g: (g['name'].lower(), g['email']))

    return {
        'users': users,
        'groups': [
            {
                'id': group['id'],
                'email': group.get('email') or '',
                'name': group.get('name') or group.get('email') or '',
                'description': group.get('description') or '',
                'member_count': len(group['members']),
                'members_error': group['members_error'],
            }
            for group in groups
        ],
    }
