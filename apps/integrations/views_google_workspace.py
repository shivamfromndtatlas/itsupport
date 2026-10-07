import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ViewSet

from apps.inventory.models import Asset
from apps.users.permissions import IsITSpecialistOrSuperAdmin

from .google_workspace import GoogleWorkspaceClient, GoogleWorkspaceError, build_directory
from .google_workspace_devices import (
    apply_portal_assets,
    cloud_devices_for_user,
    cloud_fleet_devices,
    merge_devices,
    normalize_mobile_device,
)
from .google_workspace_activity import (
    DRIVE_SHARE_EVENTS,
    normalize_drive_events,
    normalize_gmail_events,
    normalize_login_events,
    summarize_drive,
)
from .models import GoogleWorkspaceConnection
from .serializers import GoogleWorkspaceConnectionSerializer
from .views import is_laptop_asset

# Loading a directory is one request per group, so results are held briefly and
# the UI's Refresh button passes ?refresh=1 to bypass this.
DIRECTORY_CACHE_SECONDS = 600
ACTIVITY_CACHE_SECONDS = 300
logger = logging.getLogger(__name__)
PHOTO_CACHE_SECONDS = 3600
MAX_PHOTOS_PER_REQUEST = 50
PHOTO_FETCH_WORKERS = 8
SOURCE_LABELS = {'mobile': 'Mobile devices', 'cloud_identity': 'Computers'}
ACTIVITY_DAYS = (7, 30, 90)
DEFAULT_ACTIVITY_DAYS = 30
# Google requires a Gmail audit window of at most 30 days.
GMAIL_EVENT_MAX_DAYS = 30
GMAIL_EVENTS_RETURNED = 500
DRIVE_EVENT_QUERIES = ('download', *DRIVE_SHARE_EVENTS)
GMAIL_USAGE_PARAMETERS = ('gmail:num_emails_sent', 'gmail:num_emails_received')

# Google-side failures use 502, not 401: the frontend's axios interceptor treats
# any 401 as an expired portal session and would retry, then log the user out.
UPSTREAM_ERROR_STATUS = status.HTTP_502_BAD_GATEWAY


def directory_cache_key(connection):
    return f'google-workspace:directory:{connection.pk}'


def get_google_workspace_client(connection):
    return GoogleWorkspaceClient(json.loads(connection.service_account_json), connection.admin_email)


class GoogleWorkspaceConnectionViewSet(ModelViewSet):
    permission_classes = [IsITSpecialistOrSuperAdmin]
    serializer_class = GoogleWorkspaceConnectionSerializer
    queryset = GoogleWorkspaceConnection.objects.all()

    def perform_create(self, serializer):
        serializer.save()

    def perform_update(self, serializer):
        connection = serializer.save()
        # Domain, admin or key may have changed, so cached results can't be trusted.
        cache.delete(directory_cache_key(connection))

    def perform_destroy(self, instance):
        cache.delete(directory_cache_key(instance))
        instance.delete()

    @action(detail=True, methods=['post'], url_path='test')
    def test(self, request, pk=None):
        connection = self.get_object()
        if not connection.service_account_json:
            return Response({'detail': 'No service account key is saved for this domain.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            get_google_workspace_client(connection).ping(connection.domain)
            connection.last_test_status = 'success'
            connection.last_test_message = (
                f'Signed in as {connection.admin_email} and read the {connection.domain} directory '
                f'(users and groups).'
            )
            response_status = status.HTTP_200_OK
        except GoogleWorkspaceError as exc:
            connection.last_test_status = 'failed'
            connection.last_test_message = str(exc)
            response_status = UPSTREAM_ERROR_STATUS

        connection.last_tested_at = timezone.now()
        connection.save(update_fields=['last_tested_at', 'last_test_status', 'last_test_message'])
        return Response(
            {'status': connection.last_test_status, 'message': connection.last_test_message},
            status=response_status,
        )


class GoogleWorkspaceViewSet(ViewSet):
    permission_classes = [IsITSpecialistOrSuperAdmin]

    @action(detail=False, methods=['get'], url_path='directory')
    def directory(self, request):
        """
        Users of every active domain with the Google groups each belongs to. One
        domain failing (bad key, delegation not granted) doesn't hide the others:
        it is reported in ``domains`` with ``ok: false`` and an ``error``.
        """
        refresh = request.query_params.get('refresh') in ('1', 'true')
        connections = list(GoogleWorkspaceConnection.objects.filter(is_active=True).exclude(service_account_json=''))

        results = {}
        to_fetch = []
        for connection in connections:
            cached = None if refresh else cache.get(directory_cache_key(connection))
            if cached:
                results[connection.pk] = cached
            else:
                to_fetch.append(connection)

        def fetch(connection):
            # Network only: DB access stays on the request thread.
            try:
                directory = build_directory(get_google_workspace_client(connection), connection.domain)
                return connection, {'ok': True, 'error': '', 'fetched_at': timezone.now().isoformat(), **directory}
            except GoogleWorkspaceError as exc:
                return connection, {'ok': False, 'error': str(exc), 'fetched_at': '', 'users': [], 'groups': []}

        if to_fetch:
            with ThreadPoolExecutor(max_workers=len(to_fetch)) as pool:
                fetched = list(pool.map(fetch, to_fetch))
            synced_at = timezone.now()
            for connection, result in fetched:
                results[connection.pk] = result
                if result['ok']:
                    cache.set(directory_cache_key(connection), result, DIRECTORY_CACHE_SECONDS)
                    # update_fields without updated_at: syncing shouldn't churn the edit timestamp.
                    connection.last_synced_at = synced_at
                    connection.save(update_fields=['last_synced_at'])

        domains, users, groups_by_email = [], [], {}
        for connection in connections:
            result = results[connection.pk]
            domains.append({
                'connection_id': connection.pk,
                'domain': connection.domain,
                'label': connection.label,
                'ok': result['ok'],
                'error': result['error'],
                'user_count': len(result['users']),
                'group_count': len(result['groups']),
                'groups_unreadable': sum(1 for g in result['groups'] if g['members_error']),
                'fetched_at': result['fetched_at'],
            })
            users.extend(result['users'])
            # Both domains may sit in one Workspace account, in which case each
            # connection returns the same groups.
            for group in result['groups']:
                groups_by_email.setdefault(group['email'].lower(), group)

        users.sort(key=lambda user: (user['full_name'].lower(), user['primary_email']))
        return Response({
            'domains': domains,
            'users': users,
            'groups': sorted(groups_by_email.values(), key=lambda g: g['name'].lower()),
        })

    @action(detail=False, methods=['get'], url_path='user-photos')
    def user_photos(self, request):
        """
        Profile pictures for up to 50 users in one call, as ``{email: data-URI | null}``. Batched so
        the list page makes one request per page instead of one per row, and cached for an hour
        (pictures rarely change; a user without one is remembered too).
        """
        emails = []
        for part in (request.query_params.get('emails') or '').split(','):
            part = part.strip().lower()
            if '@' in part and part not in emails:
                emails.append(part)
        if not emails:
            return Response({'detail': 'An "emails" query parameter is required.'}, status=status.HTTP_400_BAD_REQUEST)
        if len(emails) > MAX_PHOTOS_PER_REQUEST:
            return Response(
                {'detail': f'At most {MAX_PHOTOS_PER_REQUEST} emails per request.'}, status=status.HTTP_400_BAD_REQUEST
            )

        connections = {
            c.domain: c
            for c in GoogleWorkspaceConnection.objects.filter(is_active=True).exclude(service_account_json='')
        }
        photos, pending = {}, []
        for email in emails:
            connection = connections.get(email.rsplit('@', 1)[1])
            if not connection:
                photos[email] = None
                continue
            cached = cache.get(f'google-workspace:photo:{connection.pk}:{email}')
            if cached is None:
                pending.append((email, connection))
            else:
                photos[email] = cached or None  # '' remembers "no picture"

        clients = {}
        for _, connection in pending:
            if connection.pk not in clients:
                client = get_google_workspace_client(connection)
                try:
                    client._token()  # authenticate once up front instead of racing in the pool
                except GoogleWorkspaceError as exc:
                    clients[connection.pk] = exc
                    continue
                clients[connection.pk] = client

        errors = []

        def fetch(item):
            email, connection = item
            client = clients[connection.pk]
            if isinstance(client, GoogleWorkspaceError):
                errors.append(str(client))
                return email, connection, None, False
            try:
                return email, connection, client.user_photo(email), True
            except GoogleWorkspaceError as exc:
                # Show initials and don't remember it, but keep the reason so the page can say why.
                errors.append(str(exc))
                logger.warning('Could not fetch the Google profile photo for %s: %s', email, exc)
                return email, connection, None, False

        if pending:
            with ThreadPoolExecutor(max_workers=PHOTO_FETCH_WORKERS) as pool:
                for email, connection, photo, definitive in pool.map(fetch, pending):
                    photos[email] = photo
                    if definitive:
                        cache.set(f'google-workspace:photo:{connection.pk}:{email}', photo or '', PHOTO_CACHE_SECONDS)
        return Response({'photos': photos, 'error': errors[0] if errors else ''})

    @action(detail=False, methods=['get'], url_path='devices')
    def devices(self, request):
        """
        Every registered device across the connected accounts, with the users signed in on each.
        Same two Google sources as the per-user view; the cloud fleet snapshot is shared with it.
        """
        refresh = request.query_params.get('refresh') in ('1', 'true')
        connections = list(GoogleWorkspaceConnection.objects.filter(is_active=True).exclude(service_account_json=''))
        rows, source_status, seen = [], {}, set()

        def load(connection):
            client = get_google_workspace_client(connection)
            fleet_key = f'google-workspace:cloud-devices:{connection.pk}'
            mobile_key = f'google-workspace:mobile-devices:{connection.pk}'

            def cloud():
                snapshot = None if refresh else cache.get(fleet_key)
                if snapshot is None:
                    snapshot = client.cloud_identity_devices()
                    cache.set(fleet_key, snapshot, DIRECTORY_CACHE_SECONDS)
                return cloud_fleet_devices(snapshot)

            def mobile():
                raw = None if refresh else cache.get(mobile_key)
                if raw is None:
                    raw = client.list_all_mobile_devices()
                    cache.set(mobile_key, raw, DIRECTORY_CACHE_SECONDS)
                return [normalize_mobile_device(item) for item in raw]

            def run(name, fn):
                try:
                    return name, fn(), ''
                except GoogleWorkspaceError as exc:
                    return name, [], str(exc)

            with ThreadPoolExecutor(max_workers=2) as pool:
                return connection, list(pool.map(lambda job: run(*job), (('mobile', mobile), ('cloud_identity', cloud))))

        if connections:
            with ThreadPoolExecutor(max_workers=len(connections)) as pool:
                loaded = list(pool.map(load, connections))
        else:
            loaded = []

        for connection, results in loaded:
            for name, found, err in results:
                entry = source_status.setdefault(name, {'ok': True, 'errors': [], 'count': 0})
                if err:
                    entry['ok'] = False
                    entry['errors'].append(f'{connection.domain}: {err}')
                for row in found:
                    # Two domains in one Google account return the same devices; count each once.
                    identity = (name, row['device_id'])
                    if row['device_id'] and identity in seen:
                        continue
                    seen.add(identity)
                    rows.append(row)
                    entry['count'] += 1

        if connections and source_status and not any(s['ok'] for s in source_status.values()):
            detail = ' '.join(f'{SOURCE_LABELS[n]}: {" ".join(s["errors"])}' for n, s in source_status.items())
            return Response({'detail': detail}, status=UPSTREAM_ERROR_STATUS)

        merged = merge_devices(rows)
        serials = {d['serial'] for d in merged if d['serial']}
        assets = Asset.objects.filter(serial_number__in=serials).select_related('asset_type') if serials else []
        by_serial = {}
        for asset in assets:
            by_serial.setdefault(asset.serial_number.strip().upper(), asset)
        devices = apply_portal_assets(merged, by_serial, is_laptop_asset)
        return Response({
            'devices': devices,
            'sources': {n: {'ok': s['ok'], 'error': ' '.join(s['errors']), 'count': s['count']} for n, s in source_status.items()},
            'summary': {
                'total': len(devices),
                'mobile': sum(1 for d in devices if d['category'] == 'mobile'),
                'laptops': sum(1 for d in devices if d.get('form_factor') == 'laptop'),
                'other_computers': sum(1 for d in devices if d['category'] == 'computer' and d.get('form_factor') != 'laptop'),
                'in_portal': sum(1 for d in devices if d['portal_asset']),
            },
        })

    # -- Per-user activity ---------------------------------------------------
    # Each panel of the user dashboard has its own endpoint so one report being
    # unavailable (edition, missing scope) doesn't blank the others. The person is
    # named in the query string, which the portal's ActivityLogMiddleware records,
    # so who looked at whose activity lands in the Activity Log automatically.

    @staticmethod
    def _resolve_user(request):
        """``(email, connection, error_response)``: the user asked about and the connection for their domain."""
        email = (request.query_params.get('email') or '').strip().lower()
        if '@' not in email:
            return email, None, Response({'detail': 'An "email" query parameter is required.'}, status=status.HTTP_400_BAD_REQUEST)
        domain = email.rsplit('@', 1)[1]
        connection = GoogleWorkspaceConnection.objects.filter(is_active=True, domain=domain).exclude(service_account_json='').first()
        if not connection:
            return email, None, Response(
                {'detail': f'{domain} is not a connected Google Workspace domain.'}, status=status.HTTP_404_NOT_FOUND
            )
        return email, connection, None

    def _cached_activity(self, request, kind, compute):
        email, connection, error = self._resolve_user(request)
        if error:
            return error
        try:
            days = int(request.query_params.get('days', DEFAULT_ACTIVITY_DAYS))
        except ValueError:
            days = DEFAULT_ACTIVITY_DAYS
        if days not in ACTIVITY_DAYS:
            days = DEFAULT_ACTIVITY_DAYS
        domain = connection.domain

        refresh = request.query_params.get('refresh') in ('1', 'true')
        key = f'google-workspace:{kind}:{connection.pk}:{email}:{days}'
        payload = None if refresh else cache.get(key)
        if payload is None:
            # Domains the org owns, so sharing to them isn't reported as "external".
            internal_domains = set(
                GoogleWorkspaceConnection.objects.filter(is_active=True).values_list('domain', flat=True)
            ) | {domain}
            try:
                payload = compute(get_google_workspace_client(connection), email, days, internal_domains)
            except GoogleWorkspaceError as exc:
                return Response({'detail': str(exc)}, status=UPSTREAM_ERROR_STATUS)
            cache.set(key, payload, ACTIVITY_CACHE_SECONDS)
        return Response(payload)

    @action(detail=False, methods=['get'], url_path='user-devices')
    def user_devices(self, request):
        """
        Devices the user has signed in to their Google account on: make, model, serial number,
        platform and laptop / mobile. Each Google source is read independently, so one being
        unavailable (scope not delegated, API not enabled) still shows what the other found.
        """
        email, connection, error = self._resolve_user(request)
        if error:
            return error
        refresh = request.query_params.get('refresh') in ('1', 'true')
        key = f'google-workspace:devices:{connection.pk}:{email}'
        payload = None if refresh else cache.get(key)

        if payload is None:
            client = get_google_workspace_client(connection)
            fleet_key = f'google-workspace:cloud-devices:{connection.pk}'

            def mobile():
                return [normalize_mobile_device(raw) for raw in client.list_mobile_devices(email)]

            def cloud():
                # Whole-fleet read (cloud identity can't filter by user), shared by every user's page.
                snapshot = None if refresh else cache.get(fleet_key)
                if snapshot is None:
                    snapshot = client.cloud_identity_devices()
                    cache.set(fleet_key, snapshot, DIRECTORY_CACHE_SECONDS)
                return cloud_devices_for_user(snapshot, email)

            def run(name, load):
                try:
                    rows = load()
                    return name, rows, ''
                except GoogleWorkspaceError as exc:
                    return name, [], str(exc)

            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda job: run(*job), (('mobile', mobile), ('cloud_identity', cloud))))

            sources = {name: {'ok': not err, 'error': err, 'count': len(rows)} for name, rows, err in results}
            if not any(source['ok'] for source in sources.values()):
                detail = ' '.join(
                    f'{label}: {sources[name]["error"]}'
                    for name, label in (('mobile', 'Mobile devices'), ('cloud_identity', 'Computers'))
                )
                return Response({'detail': detail}, status=UPSTREAM_ERROR_STATUS)
            payload = {
                'devices': merge_devices([row for _, rows, _ in results for row in rows]),
                'sources': sources,
            }
            cache.set(key, payload, ACTIVITY_CACHE_SECONDS)

        # Portal assets change independently of Google, so they are matched on every request, not cached.
        serials = {device['serial'] for device in payload['devices'] if device['serial']}
        assets = Asset.objects.filter(serial_number__in=serials).select_related('asset_type') if serials else []
        by_serial = {}
        for asset in assets:
            by_serial.setdefault(asset.serial_number.strip().upper(), asset)
        devices = apply_portal_assets(payload['devices'], by_serial, is_laptop_asset)
        return Response({
            'devices': devices,
            'sources': payload['sources'],
            'summary': {
                'total': len(devices),
                'mobile': sum(1 for d in devices if d['category'] == 'mobile'),
                'laptops': sum(1 for d in devices if d.get('form_factor') == 'laptop'),
                'other_computers': sum(
                    1 for d in devices if d['category'] == 'computer' and d.get('form_factor') != 'laptop'
                ),
            },
        })

    @action(detail=False, methods=['get'], url_path='user-drive')
    def user_drive(self, request):
        """Files the user downloaded, and what they shared with whom (internal vs external)."""
        def compute(client, email, days, internal_domains):
            end = timezone.now()
            start = end - timedelta(days=days)
            with ThreadPoolExecutor(max_workers=len(DRIVE_EVENT_QUERIES)) as pool:
                results = list(pool.map(
                    lambda name: client.list_activities(email, 'drive', start, end, event_name=name),
                    DRIVE_EVENT_QUERIES,
                ))
            rows = [
                row
                for items, _ in results
                for item in items
                for row in normalize_drive_events(item, internal_domains)
            ]
            rows.sort(key=lambda row: row['time'], reverse=True)
            return {
                'days': days,
                'events': rows,
                'summary': summarize_drive(rows),
                'truncated': any(truncated for _, truncated in results),
            }

        return self._cached_activity(request, 'drive', compute)

    @action(detail=False, methods=['get'], url_path='user-signins')
    def user_signins(self, request):
        def compute(client, email, days, internal_domains):
            end = timezone.now()
            items, truncated = client.list_activities(email, 'login', end - timedelta(days=days), end)
            rows = [row for item in items for row in normalize_login_events(item)]
            rows.sort(key=lambda row: row['time'], reverse=True)
            return {
                'days': days,
                'events': rows,
                'summary': {
                    'signins': sum(1 for row in rows if row['event'] == 'login_success'),
                    'failures': sum(1 for row in rows if row['event'] == 'login_failure'),
                    'suspicious': sum(1 for row in rows if row['risk'] and row['event'] != 'login_failure'),
                },
                'truncated': truncated,
            }

        return self._cached_activity(request, 'signins', compute)

    @action(detail=False, methods=['get'], url_path='user-email-usage')
    def user_email_usage(self, request):
        """Emails sent and received per day. Counts only: Google's usage reports carry no message detail."""
        def compute(client, email, days, internal_domains):
            series = client.user_usage_series(email, days, GMAIL_USAGE_PARAMETERS)
            daily = [
                {'date': row['date'], 'sent': row['gmail:num_emails_sent'], 'received': row['gmail:num_emails_received']}
                for row in series
            ]
            return {
                'days': days,
                'daily': daily,
                'totals': {'sent': sum(d['sent'] for d in daily), 'received': sum(d['received'] for d in daily)},
                # Usage reports trail real time, so the newest days are missing by design.
                'data_through': daily[-1]['date'] if daily else '',
            }

        return self._cached_activity(request, 'email-usage', compute)

    @action(detail=False, methods=['get'], url_path='user-email-events')
    def user_email_events(self, request):
        """
        Individual sent / received / forwarded events from the Gmail audit log. What
        each event carries (subject, sender, recipients) depends on the Workspace
        edition, so the raw fields are passed through and the UI says when they're absent.
        """
        def compute(client, email, days, internal_domains):
            window = min(days, GMAIL_EVENT_MAX_DAYS)
            end = timezone.now()
            items, truncated = client.list_activities(email, 'gmail', end - timedelta(days=window), end)
            rows = [row for item in items for row in normalize_gmail_events(item, internal_domains)]
            rows.sort(key=lambda row: row['time'], reverse=True)
            # The newest messages, plus every flagged one however old, so the flagged
            # count always matches what the table can show.
            returned = rows[:GMAIL_EVENTS_RETURNED] + [
                row for row in rows[GMAIL_EVENTS_RETURNED:] if row['external_with_attachments']
            ]
            return {
                'days': window,
                'events': returned,
                'flagged': sum(1 for row in rows if row['external_with_attachments']),
                # Names only (no values): lets the UI show which fields Google sent.
                'field_names': sorted({name for row in rows for name in row['fields']})[:100],
                'counts': {
                    direction: sum(1 for row in rows if row['direction'] == direction)
                    for direction in ('sent', 'received', 'forwarded', 'auto_forwarded')
                },
                'truncated': truncated or len(rows) > GMAIL_EVENTS_RETURNED,
            }

        return self._cached_activity(request, 'email-events', compute)
