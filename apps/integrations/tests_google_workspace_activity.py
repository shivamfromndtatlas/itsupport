import json
from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import jwt
from django.core.cache import cache
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.activity_log.models import ActivityLog
from apps.users.models import User

from .google_workspace import (
    AUDIT_SCOPES,
    SCOPES,
    USAGE_SCOPES,
    TOKEN_URL,
    GoogleWorkspaceClient,
    GoogleWorkspaceError,
)
from .google_workspace_activity import (
    classify_share_scope,
    flatten_parameters,
    normalize_drive_events,
    normalize_gmail_events,
    normalize_login_events,
    summarize_drive,
)
from .models import GoogleWorkspaceConnection
from .tests_google_workspace import KEY_INFO, PUBLIC_PEM, http_error, token_response

INTERNAL = {'ndtatlas.com', 'amplifailabs.in'}


def drive_item(name, params, time='2026-09-10T10:00:00.000Z', ip='1.2.3.4', qualifier='q1'):
    return {
        'id': {'time': time, 'uniqueQualifier': qualifier},
        'ipAddress': ip,
        'events': [{'name': name, 'type': 'access', 'parameters': params}],
    }


def p(name, value):
    return {'name': name, 'value': value}


class FlattenParametersTests(APITestCase):
    def test_handles_every_value_shape(self):
        flat = flatten_parameters([
            p('doc_title', 'Q3 plan'),
            {'name': 'primary_event', 'boolValue': True},
            {'name': 'count', 'intValue': '7'},
            {'name': 'new_value', 'multiValue': ['can_view']},
            {'name': 'message_info', 'messageValue': {'parameter': [p('subject', 'Hello')]}},
            {'name': 'message_info', 'multiMessageValue': [
                {'parameter': [p('destination.address', 'a@x.com')]},
                {'parameter': [p('destination.address', 'b@x.com')]},
            ]},
        ])
        self.assertEqual(flat['doc_title'], 'Q3 plan')
        self.assertIs(flat['primary_event'], True)
        self.assertEqual(flat['count'], 7)
        self.assertEqual(flat['new_value'], ['can_view'])
        self.assertEqual(flat['message_info.subject'], 'Hello')
        self.assertEqual(flat['message_info.destination.address'], ['a@x.com', 'b@x.com'])


class DriveNormalizationTests(APITestCase):
    def test_download_row(self):
        [row] = normalize_drive_events(
            drive_item('download', [p('doc_title', 'Salaries.xlsx'), p('doc_type', 'spreadsheet'), p('owner', 'hr@ndtatlas.com')]),
            INTERNAL,
        )
        self.assertEqual((row['category'], row['action'], row['title'], row['owner']), ('download', 'downloaded', 'Salaries.xlsx', 'hr@ndtatlas.com'))
        self.assertEqual(row['scope'], '')
        self.assertEqual(row['ip'], '1.2.3.4')

    def test_unrelated_drive_events_are_ignored(self):
        self.assertEqual(normalize_drive_events(drive_item('view', [p('doc_title', 'x')]), INTERNAL), [])

    def test_sharing_with_an_outside_domain_is_external(self):
        [row] = normalize_drive_events(
            drive_item('change_user_access', [p('target_user', 'vendor@gmail.com'), p('target_domain', 'gmail.com'), {'name': 'new_value', 'multiValue': ['can_edit']}]),
            INTERNAL,
        )
        self.assertEqual((row['scope'], row['action']), ('external', 'granted'))
        self.assertEqual(row['access_change'], ' → can_edit')

    def test_sharing_with_own_or_secondary_domain_is_internal(self):
        for domain in ('ndtatlas.com', 'amplifailabs.in'):
            with self.subTest(domain=domain):
                [row] = normalize_drive_events(drive_item('change_user_access', [p('target_domain', domain)]), INTERNAL)
                self.assertEqual(row['scope'], 'internal')

    def test_googles_own_internal_external_verdict_wins_over_domain_guess(self):
        params = {'visibility_change': 'internal', 'target_domain': 'gmail.com'}
        self.assertEqual(classify_share_scope(params, INTERNAL), 'internal')

    def test_public_link_sharing_is_external_even_without_a_target(self):
        [row] = normalize_drive_events(
            drive_item('change_document_visibility', [p('visibility', 'people_with_link'), p('old_visibility', 'private')]),
            INTERNAL,
        )
        self.assertEqual((row['scope'], row['action'], row['visibility'], row['old_visibility']), ('external', 'granted', 'people_with_link', 'private'))

    def test_removing_access_is_not_counted_as_sharing(self):
        removed = normalize_drive_events(
            drive_item('change_user_access', [p('target_domain', 'gmail.com'), {'name': 'new_value', 'multiValue': ['none']}]),
            INTERNAL,
        )
        made_private = normalize_drive_events(drive_item('change_document_visibility', [p('visibility', 'private')]), INTERNAL)
        granted = normalize_drive_events(drive_item('change_user_access', [p('target_domain', 'gmail.com')]), INTERNAL)

        self.assertEqual([r['action'] for r in removed + made_private], ['removed', 'removed'])
        summary = summarize_drive(removed + made_private + granted)
        self.assertEqual(summary, {'downloads': 0, 'shared_external': 1, 'shared_internal': 0})

    def test_epoch_seconds_time_is_converted(self):
        item = drive_item('download', [p('doc_title', 'x')], time='1788000000')
        [row] = normalize_drive_events(item, INTERNAL)
        self.assertTrue(row['time'].startswith('2026-'))

    def test_a_sparse_event_yields_empty_strings_not_errors(self):
        [row] = normalize_drive_events({'id': {}, 'events': [{'name': 'download'}]}, INTERNAL)
        self.assertEqual((row['title'], row['owner'], row['ip'], row['time']), ('', '', '', ''))


class LoginAndGmailNormalizationTests(APITestCase):
    def test_login_rows_flag_failures_and_suspicious_activity(self):
        rows = []
        for name in ('login_success', 'login_failure', 'suspicious_login', 'logout'):
            item = {'id': {'time': 't'}, 'ipAddress': '9.9.9.9', 'events': [{'name': name, 'parameters': [p('login_type', 'google_password')]}]}
            rows += normalize_login_events(item)
        self.assertEqual([r['risk'] for r in rows], [False, True, True, False])
        self.assertEqual(rows[0]['label'], 'Signed in')
        self.assertEqual(rows[0]['login_type'], 'google_password')

    def test_gmail_rows_keep_only_mail_movement_and_read_message_info(self):
        def gmail_item(kind, extra=()):
            return {
                'id': {'time': '2026-09-10T10:00:00.000Z'},
                'events': [{'name': 'delivery', 'parameters': [
                    {'name': 'event_info', 'messageValue': {'parameter': [{'name': 'mail_event_type', 'intValue': str(kind)}]}},
                    *extra,
                ]}],
            }

        message_info = {'name': 'message_info', 'messageValue': {'parameter': [
            p('subject', 'Invoice'),
            {'name': 'source', 'messageValue': {'parameter': [p('address', 'boss@ndtatlas.com')]}},
            {'name': 'destination', 'multiMessageValue': [{'parameter': [p('address', 'me@ndtatlas.com')]}]},
        ]}}
        sent = normalize_gmail_events(gmail_item(1, [message_info]))
        received = normalize_gmail_events(gmail_item(2))
        spam_classification = normalize_gmail_events(gmail_item(20))

        self.assertEqual(spam_classification, [])
        self.assertEqual(received[0]['direction'], 'received')
        self.assertEqual(received[0]['subject'], '')  # edition didn't supply message details
        self.assertEqual(sent[0]['direction'], 'sent')
        self.assertEqual(sent[0]['subject'], 'Invoice')
        self.assertEqual(sent[0]['sender'], 'boss@ndtatlas.com')
        self.assertEqual(sent[0]['recipients'], ['me@ndtatlas.com'])
        self.assertIn('message_info.subject', sent[0]['fields'])

    def test_sender_and_recipients_are_found_whichever_way_the_account_names_them(self):
        def gmail(params):
            return {
                'id': {'time': 't'},
                'events': [{'name': 'delivery', 'parameters': [{'name': 'event_info.mail_event_type', 'intValue': '2'}, *params]}],
            }

        header_only = normalize_gmail_events(gmail([
            p('message_info.source.from_header_address', 'Boss <boss@x.com>'),
            p('message_info.source.service', 'smtp-inbound'),  # not an address: must not be picked up
        ]))[0]
        plain = normalize_gmail_events(gmail([
            p('message_info.source', 'a@x.com'),
            {'name': 'message_info.destination', 'multiValue': ['b@x.com', 'c@x.com']},
        ]))[0]
        address_wins = normalize_gmail_events(gmail([
            p('message_info.source.from_header_address', 'display@x.com'),
            p('message_info.source.address', 'real@x.com'),
        ]))[0]
        duplicated = normalize_gmail_events(gmail([
            p('message_info.destination.address', 'b@x.com'),
            p('message_info.destination.selector', 'b@x.com'),
        ]))[0]
        none_found = normalize_gmail_events(gmail([p('message_info.subject', 'Hi')]))[0]

        self.assertEqual((header_only['sender'], header_only['recipients']), ('boss@x.com', []))
        self.assertEqual((plain['sender'], plain['recipients']), ('a@x.com', ['b@x.com', 'c@x.com']))
        self.assertEqual(address_wins['sender'], 'real@x.com')
        self.assertEqual(duplicated['recipients'], ['b@x.com'])
        self.assertEqual((none_found['sender'], none_found['recipients']), ('', []))

    def test_real_gmail_event_recipient_comes_from_flattened_destinations(self):
        # The 15 fields a real Workspace account returned for a received message: no
        # sender field exists, and the recipient is a "service::address" string.
        fields = [
            {'name': 'event_info.mail_event_type', 'intValue': '2'},
            {'name': 'event_info.timestamp_usec', 'intValue': '1789126797304389'},
            p('message_info.flattened_destinations', 'gmail-ui::ekaushal@ndtatlas.com'),
            p('message_info.rfc2822_message_id', '<jOoG2r@notifications.google.com>'),
            p('message_info.subject', 'New sign-in using a backup code'),
            {'name': 'message_info.link_domain', 'multiValue': ['google.com', 'gstatic.com']},
            {'name': 'message_info.payload_size', 'intValue': '14232'},
            {'name': 'message_info.num_message_attachments', 'intValue': '0'},
        ]
        [row] = normalize_gmail_events({'id': {'time': 't'}, 'events': [{'name': 'delivery', 'parameters': fields}]})

        self.assertEqual(row['recipients'], ['ekaushal@ndtatlas.com'])
        self.assertEqual((row['size'], row['attachments']), (14232, 0))
        # The Message-ID host is not the sender's address, so it must not be presented as one.
        self.assertEqual(row['sender'], '')
        self.assertEqual(row['subject'], 'New sign-in using a backup code')

    def test_attachment_count_and_size_parse_ints_and_keep_zero_distinct_from_missing(self):
        def gmail(params):
            return {'id': {'time': 't'}, 'events': [{'name': 'delivery', 'parameters': [{'name': 'event_info.mail_event_type', 'intValue': '1'}, *params]}]}

        [with_files] = normalize_gmail_events(gmail([
            {'name': 'message_info.num_message_attachments', 'intValue': '3'},
            p('message_info.payload_size', '2048'),  # string form is accepted too
        ]))
        [none_attached] = normalize_gmail_events(gmail([{'name': 'message_info.num_message_attachments', 'intValue': '0'}]))
        [unknown] = normalize_gmail_events(gmail([p('message_info.payload_size', 'n/a')]))

        self.assertEqual((with_files['attachments'], with_files['size']), (3, 2048))
        self.assertEqual((none_attached['attachments'], none_attached['size']), (0, None))
        self.assertEqual((unknown['attachments'], unknown['size']), (None, None))

    def test_outbound_mail_with_files_to_outside_recipients_is_flagged(self):
        def gmail(kind, recipients, attachments):
            params = [
                {'name': 'event_info.mail_event_type', 'intValue': str(kind)},
                {'name': 'message_info.flattened_destinations', 'multiValue': [f'smtp-outbound::{r}' for r in recipients]},
            ]
            if attachments is not None:
                params.append({'name': 'message_info.num_message_attachments', 'intValue': str(attachments)})
            return {'id': {'time': 't'}, 'events': [{'name': 'delivery', 'parameters': params}]}

        domains = {'ndtatlas.com', 'amplifailabs.in'}

        def row(kind, recipients, attachments, internal=domains):
            [result] = normalize_gmail_events(gmail(kind, recipients, attachments), internal)
            return result

        flagged = row(1, ['buyer@gmail.com'], 2)
        self.assertTrue(flagged['external_with_attachments'])
        self.assertEqual(flagged['external_recipients'], ['buyer@gmail.com'])

        # Mixed recipients: flagged, and only the outside ones are listed.
        mixed = row(1, ['colleague@ndtatlas.com', 'buyer@gmail.com'], 1)
        self.assertTrue(mixed['external_with_attachments'])
        self.assertEqual(mixed['external_recipients'], ['buyer@gmail.com'])

        # Forwarded mail counts as outbound too.
        self.assertTrue(row(10, ['x@yahoo.com'], 1)['external_with_attachments'])

        # Outside recipient but no files: listed as external, not flagged.
        no_files = row(1, ['buyer@gmail.com'], 0)
        self.assertEqual((no_files['external_with_attachments'], no_files['external_recipients']), (False, ['buyer@gmail.com']))
        # Attachment count unknown: never flagged on a guess.
        self.assertFalse(row(1, ['buyer@gmail.com'], None)['external_with_attachments'])

        # Files but everyone is inside the org, including subdomains.
        self.assertFalse(row(1, ['a@ndtatlas.com', 'b@mail.ndtatlas.com', 'c@amplifailabs.in'], 3)['external_with_attachments'])
        # A look-alike domain is not internal.
        self.assertTrue(row(1, ['a@notndtatlas.com'], 1)['external_with_attachments'])

        # Received mail is never flagged, even with files and a foreign-looking address.
        received = row(2, ['owner@gmail.com'], 5)
        self.assertEqual((received['external_with_attachments'], received['external_recipients']), (False, []))

        # No domains supplied: nothing is flagged rather than everything.
        unflagged = normalize_gmail_events(gmail(1, ['buyer@gmail.com'], 2))[0]
        self.assertEqual((unflagged['external_with_attachments'], unflagged['external_recipients']), (False, []))

    def test_several_flattened_destinations_and_look_alike_names(self):
        def gmail(params):
            return {'id': {'time': 't'}, 'events': [{'name': 'delivery', 'parameters': [{'name': 'event_info.mail_event_type', 'intValue': '1'}, *params]}]}

        [many] = normalize_gmail_events(gmail([
            {'name': 'message_info.flattened_destinations', 'multiValue': ['smtp-outbound::a@x.com', 'smtp-outbound::b@y.org']},
        ]))
        [look_alike] = normalize_gmail_events(gmail([
            p('message_info.resource_owner', 'x@y.com'),        # "resource" is not the word "source"
            p('message_info.total_recipient_count', '3 items'),  # no address in the value
        ]))

        self.assertEqual(many['recipients'], ['a@x.com', 'b@y.org'])
        self.assertEqual((look_alike['sender'], look_alike['recipients']), ('', []))


class ReportsClientTests(APITestCase):
    def setUp(self):
        self.gw = GoogleWorkspaceClient(KEY_INFO, 'admin@ndtatlas.com')
        self.gw._tokens[AUDIT_SCOPES] = ('tok', 10 ** 12)
        self.gw._tokens[USAGE_SCOPES] = ('tok', 10 ** 12)

    def test_each_report_token_asks_only_for_its_own_scope(self):
        for scopes in (AUDIT_SCOPES, USAGE_SCOPES):
            with self.subTest(scopes=scopes):
                client = GoogleWorkspaceClient(KEY_INFO, 'admin@ndtatlas.com')
                opener = MagicMock()
                opener.open.return_value = token_response()

                with patch.object(GoogleWorkspaceClient, '_opener', return_value=opener):
                    client._token(scopes)

                assertion = dict(pair.split('=') for pair in opener.open.call_args[0][0].data.decode().split('&'))['assertion']
                claims = jwt.decode(assertion, PUBLIC_PEM, algorithms=['RS256'], audience=TOKEN_URL)
                self.assertEqual(claims['scope'], ' '.join(scopes))
                self.assertEqual(len(scopes), 1)

    def test_a_missing_scope_is_named_exactly_and_breaks_nothing_else(self):
        # Only the usage scope has been left off the delegation entry.
        client = GoogleWorkspaceClient(KEY_INFO, 'admin@ndtatlas.com')

        def respond(request, timeout=None):
            assertion = dict(pair.split('=') for pair in request.data.decode().split('&'))['assertion']
            scope = jwt.decode(assertion, PUBLIC_PEM, algorithms=['RS256'], audience=TOKEN_URL)['scope']
            if 'admin.reports.usage' in scope:
                raise http_error(401, {'error': 'unauthorized_client', 'error_description': 'not authorised'})
            return token_response()

        opener = MagicMock()
        opener.open.side_effect = respond
        with patch.object(GoogleWorkspaceClient, '_opener', return_value=opener):
            with self.assertRaises(GoogleWorkspaceError) as caught:
                client._token(USAGE_SCOPES)
            self.assertIn('admin.reports.usage.readonly', str(caught.exception))
            self.assertNotIn('admin.reports.audit', str(caught.exception))
            self.assertEqual(client._token(AUDIT_SCOPES), 'tok')
            self.assertEqual(client._token(SCOPES), 'tok')

    def test_list_activities_builds_the_reports_request(self):
        start = datetime(2026, 8, 22, 9, 30, tzinfo=timezone.utc)
        end = datetime(2026, 9, 21, 9, 30, tzinfo=timezone.utc)
        with patch.object(GoogleWorkspaceClient, '_get', return_value={'items': [{'id': {}}]}) as get:
            items, truncated = self.gw.list_activities('a.b+c@ndtatlas.com', 'drive', start, end, event_name='download')

        path, params = get.call_args[0]
        self.assertEqual(path, '/activity/users/a.b%2Bc%40ndtatlas.com/applications/drive')
        self.assertEqual((params['startTime'], params['endTime'], params['eventName']), ('2026-08-22T09:30:00Z', '2026-09-21T09:30:00Z', 'download'))
        self.assertEqual(get.call_args[1]['scopes'], AUDIT_SCOPES)
        self.assertEqual((len(items), truncated), (1, False))

    def test_list_activities_stops_at_the_cap_and_says_so(self):
        page = {'items': [{'id': {}}] * 1000, 'nextPageToken': 'more'}
        with patch.object(GoogleWorkspaceClient, '_get', return_value=page) as get:
            items, truncated = self.gw.list_activities('a@x.com', 'drive', datetime.now(timezone.utc), datetime.now(timezone.utc), max_events=2500)
        self.assertEqual((len(items), truncated, get.call_count), (2500, True, 3))

    def test_user_usage_parses_int64_strings(self):
        response = {'usageReports': [{'parameters': [{'name': 'gmail:num_emails_sent', 'intValue': '12'}]}]}
        with patch.object(GoogleWorkspaceClient, '_get', return_value=response) as get:
            values = self.gw.user_usage('a@x.com', date(2026, 9, 1), ['gmail:num_emails_sent'])
        self.assertEqual(values, {'gmail:num_emails_sent': 12})
        self.assertEqual(get.call_args[0][0], '/usage/users/a%40x.com/dates/2026-09-01')
        self.assertEqual(get.call_args[1]['scopes'], USAGE_SCOPES)

    def test_series_ends_three_days_back_and_drops_days_without_data(self):
        def fake_usage(user_key, day, parameters):
            return None if day.day == 18 else {'gmail:num_emails_sent': day.day, 'gmail:num_emails_received': 1}

        with patch('apps.integrations.google_workspace.datetime') as fake_datetime, \
                patch.object(GoogleWorkspaceClient, 'user_usage', side_effect=fake_usage):
            fake_datetime.now.return_value = datetime(2026, 9, 21, 12, tzinfo=timezone.utc)
            series = self.gw.user_usage_series('a@x.com', 3, ('gmail:num_emails_sent', 'gmail:num_emails_received'))

        self.assertEqual([row['date'] for row in series], ['2026-09-16', '2026-09-17'])  # newest day is 09-18, no data
        self.assertEqual(series[0]['gmail:num_emails_sent'], 16)

    def test_series_raises_when_every_day_fails_but_tolerates_a_partial_failure(self):
        params = ('gmail:num_emails_sent',)
        with patch.object(GoogleWorkspaceClient, 'user_usage', side_effect=GoogleWorkspaceError('no scope', 401)):
            with self.assertRaisesRegex(GoogleWorkspaceError, 'no scope'):
                self.gw.user_usage_series('a@x.com', 3, params)

        outcomes = iter([GoogleWorkspaceError('blip', 400), {'gmail:num_emails_sent': 4}, {'gmail:num_emails_sent': 5}])

        def flaky(user_key, day, parameters):
            outcome = next(outcomes)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        with patch.object(GoogleWorkspaceClient, 'user_usage', side_effect=flaky):
            series = self.gw.user_usage_series('a@x.com', 3, params, workers=1)
        self.assertEqual(len(series), 2)


class UserActivityApiTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.it_user = User.objects.create_user(email='it@example.com', password='pw', full_name='IT', role='it_specialist')
        self.client.force_authenticate(self.it_user)
        self.connection = GoogleWorkspaceConnection.objects.create(
            domain='ndtatlas.com', admin_email='admin@ndtatlas.com',
            service_account_json=json.dumps(KEY_INFO), service_account_email=KEY_INFO['client_email'],
        )
        self.email = 'asha@ndtatlas.com'

    def get(self, name, **params):
        params.setdefault('email', self.email)
        return self.client.get(reverse(f'google-workspace-{name}'), params)

    @patch('apps.integrations.views_google_workspace.GoogleWorkspaceClient.list_activities')
    def test_drive_merges_download_and_share_queries_newest_first_with_summary(self, list_activities):
        by_event = {
            'download': [drive_item('download', [p('doc_title', 'a.pdf')], time='2026-09-10T10:00:00Z')],
            'change_user_access': [drive_item('change_user_access', [p('target_domain', 'gmail.com')], time='2026-09-12T10:00:00Z')],
            'change_document_visibility': [],
            'change_document_access_scope': [],
        }
        list_activities.side_effect = lambda user, app, start, end, event_name=None, **kw: (by_event[event_name], False)

        response = self.get('user-drive')

        self.assertEqual(response.status_code, 200)
        self.assertEqual([e['category'] for e in response.data['events']], ['share', 'download'])
        self.assertEqual(response.data['summary'], {'downloads': 1, 'shared_external': 1, 'shared_internal': 0})
        self.assertEqual(response.data['days'], 30)
        self.assertFalse(response.data['truncated'])
        self.assertEqual({call.args[1] for call in list_activities.call_args_list}, {'drive'})

    @patch('apps.integrations.views_google_workspace.GoogleWorkspaceClient.list_activities')
    def test_a_share_to_another_connected_domain_is_internal(self, list_activities):
        GoogleWorkspaceConnection.objects.create(domain='amplifailabs.in', admin_email='a@amplifailabs.in', service_account_json=json.dumps(KEY_INFO))
        list_activities.side_effect = lambda user, app, start, end, event_name=None, **kw: (
            [drive_item('change_user_access', [p('target_domain', 'amplifailabs.in')])] if event_name == 'change_user_access' else [], False
        )
        self.assertEqual(self.get('user-drive').data['summary']['shared_internal'], 1)

    @patch('apps.integrations.views_google_workspace.GoogleWorkspaceClient.list_activities', return_value=([], False))
    def test_results_are_cached_per_user_and_range_until_refresh(self, list_activities):
        self.get('user-signins')
        self.get('user-signins')
        self.assertEqual(list_activities.call_count, 1)
        self.get('user-signins', days=7)
        self.get('user-signins', email='other@ndtatlas.com')
        self.assertEqual(list_activities.call_count, 3)
        self.get('user-signins', refresh='1')
        self.assertEqual(list_activities.call_count, 4)

    @patch('apps.integrations.views_google_workspace.GoogleWorkspaceClient.list_activities')
    def test_signins_summary(self, list_activities):
        items = [
            {'id': {'time': f'2026-09-1{i}T00:00:00Z'}, 'ipAddress': '1.1.1.1', 'events': [{'name': name}]}
            for i, name in enumerate(['login_success', 'login_success', 'login_failure', 'suspicious_login'])
        ]
        list_activities.return_value = (items, True)
        data = self.get('user-signins').data
        self.assertEqual(data['summary'], {'signins': 2, 'failures': 1, 'suspicious': 1})
        self.assertTrue(data['truncated'])
        self.assertEqual(data['events'][0]['event'], 'suspicious_login')  # newest first

    @patch('apps.integrations.views_google_workspace.GoogleWorkspaceClient.user_usage_series')
    def test_email_usage_totals_and_data_through(self, series):
        series.return_value = [
            {'date': '2026-09-16', 'gmail:num_emails_sent': 3, 'gmail:num_emails_received': 10},
            {'date': '2026-09-17', 'gmail:num_emails_sent': 4, 'gmail:num_emails_received': 20},
        ]
        data = self.get('user-email-usage', days=7).data
        self.assertEqual(data['totals'], {'sent': 7, 'received': 30})
        self.assertEqual(data['data_through'], '2026-09-17')
        self.assertEqual(data['daily'][0], {'date': '2026-09-16', 'sent': 3, 'received': 10})

    @patch('apps.integrations.views_google_workspace.GoogleWorkspaceClient.list_activities')
    def test_email_events_are_capped_to_a_30_day_window(self, list_activities):
        list_activities.return_value = ([], False)
        data = self.get('user-email-events', days=90).data
        start, end = list_activities.call_args[0][2:4]
        self.assertEqual(data['days'], 30)
        self.assertEqual((end - start).days, 30)

    @patch('apps.integrations.views_google_workspace.GoogleWorkspaceClient.list_activities')
    def test_email_events_counts(self, list_activities):
        def item(kind):
            return {'id': {'time': '2026-09-10T10:00:00Z'}, 'events': [{'name': 'delivery', 'parameters': [{'name': 'event_info.mail_event_type', 'intValue': str(kind)}]}]}
        list_activities.return_value = ([item(1), item(1), item(2), item(20)], False)
        data = self.get('user-email-events').data
        self.assertEqual(data['counts'], {'sent': 2, 'received': 1, 'forwarded': 0, 'auto_forwarded': 0})
        self.assertEqual(len(data['events']), 3)
        self.assertEqual(data['field_names'], ['event_info.mail_event_type'])

    @patch('apps.integrations.views_google_workspace.GoogleWorkspaceClient.list_activities')
    def test_email_events_flag_files_to_outside_recipients_using_connected_domains(self, list_activities):
        GoogleWorkspaceConnection.objects.create(domain='amplifailabs.in', admin_email='a@amplifailabs.in', service_account_json=json.dumps(KEY_INFO))

        def item(minute, recipient, attachments):
            return {'id': {'time': f'2026-09-10T10:{minute:02d}:00Z'}, 'events': [{'name': 'delivery', 'parameters': [
                {'name': 'event_info.mail_event_type', 'intValue': '1'},
                {'name': 'message_info.flattened_destinations', 'value': f'smtp-outbound::{recipient}'},
                {'name': 'message_info.num_message_attachments', 'intValue': str(attachments)},
            ]}]}

        list_activities.return_value = ([
            item(1, 'buyer@gmail.com', 2),         # flagged
            item(2, 'partner@amplifailabs.in', 2),  # sibling domain of this org: not flagged
            item(3, 'buyer@gmail.com', 0),         # outside but no files: not flagged
        ], False)

        data = self.get('user-email-events').data

        self.assertEqual(data['flagged'], 1)
        self.assertEqual([e['external_with_attachments'] for e in data['events']], [False, False, True])  # newest first

    @patch('apps.integrations.views_google_workspace.GoogleWorkspaceClient.list_activities')
    def test_old_flagged_messages_are_returned_even_beyond_the_row_cap(self, list_activities):
        def item(minute, recipient, attachments):
            return {'id': {'time': f'2026-09-10T{minute // 60:02d}:{minute % 60:02d}:00Z'}, 'events': [{'name': 'delivery', 'parameters': [
                {'name': 'event_info.mail_event_type', 'intValue': '1'},
                {'name': 'message_info.flattened_destinations', 'value': f'smtp-outbound::{recipient}'},
                {'name': 'message_info.num_message_attachments', 'intValue': str(attachments)},
            ]}]}

        # 600 internal messages after one old flagged one.
        items = [item(0, 'buyer@gmail.com', 1)] + [item(minute, 'me@ndtatlas.com', 0) for minute in range(1, 601)]
        list_activities.return_value = (items, False)

        data = self.get('user-email-events').data

        self.assertEqual(len(data['events']), 501)  # newest 500 + the one old flagged message
        self.assertEqual(data['flagged'], 1)
        self.assertTrue(data['events'][-1]['external_with_attachments'])
        self.assertTrue(data['truncated'])

    @patch('apps.integrations.views_google_workspace.GoogleWorkspaceClient.list_activities', side_effect=GoogleWorkspaceError('add the reports scopes', 401))
    def test_google_failures_are_502_with_the_reason_and_are_not_cached(self, list_activities):
        response = self.get('user-drive')
        self.assertEqual(response.status_code, 502)  # a 401 would log the portal user out
        self.assertEqual(response.data['detail'], 'add the reports scopes')
        calls_after_first = list_activities.call_count
        self.get('user-drive')
        # Not cached, so Google is asked again. (Compared, not counted exactly:
        # MagicMock's counter isn't thread-safe and the four queries run in parallel.)
        self.assertGreater(list_activities.call_count, calls_after_first)

    def test_validation(self):
        self.assertEqual(self.client.get(reverse('google-workspace-user-drive')).status_code, 400)
        self.assertEqual(self.get('user-drive', email='no-at-sign').status_code, 400)
        missing = self.get('user-drive', email='someone@unconnected.org')
        self.assertEqual(missing.status_code, 404)
        self.assertIn('unconnected.org', missing.data['detail'])

    @patch('apps.integrations.views_google_workspace.GoogleWorkspaceClient.list_activities', return_value=([], False))
    def test_unsupported_day_ranges_fall_back_to_30(self, list_activities):
        self.assertEqual(self.get('user-signins', days=9999).data['days'], 30)
        self.assertEqual(self.get('user-signins', days='abc').data['days'], 30)

    def test_only_it_and_super_admins_can_read_activity(self):
        employee = User.objects.create_user(email='emp@example.com', password='pw', full_name='Emp', role='employee')
        self.client.force_authenticate(employee)
        for name in ('user-drive', 'user-signins', 'user-email-usage', 'user-email-events'):
            self.assertEqual(self.get(name).status_code, 403, name)

    @patch('apps.integrations.views_google_workspace.GoogleWorkspaceClient.list_activities', return_value=([], False))
    def test_who_looked_at_whose_activity_lands_in_the_activity_log(self, list_activities):
        self.get('user-drive')
        entry = ActivityLog.objects.filter(path__endswith='/user-drive/').first()
        self.assertIsNotNone(entry)
        self.assertEqual(entry.user, self.it_user)
        self.assertIn('asha%40ndtatlas.com', entry.metadata['query_string'])
