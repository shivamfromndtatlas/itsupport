import json
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.core.cache import cache
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.users.models import User

from .google_workspace import (
    NEVER_LOGGED_IN,
    SCOPES,
    TOKEN_URL,
    GoogleWorkspaceClient,
    GoogleWorkspaceError,
    build_directory,
    normalize_user,
)
from .models import GoogleWorkspaceConnection


def make_service_account_key(email='reader@proj.iam.gserviceaccount.com'):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    public_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    info = {
        'type': 'service_account',
        'client_email': email,
        'client_id': '109876543210987654321',
        'private_key': pem,
        'project_id': 'proj',
    }
    return info, public_pem


KEY_INFO, PUBLIC_PEM = make_service_account_key()


def http_error(code, body):
    return HTTPError('https://example', code, 'err', {}, MagicMock(read=lambda: json.dumps(body).encode()))


def token_response(access_token='tok', expires_in=3600):
    response = MagicMock()
    response.__enter__.return_value.read.return_value = json.dumps(
        {'access_token': access_token, 'expires_in': expires_in}
    ).encode()
    return response


class ClientAuthTests(APITestCase):
    def test_assertion_is_signed_for_the_impersonated_admin_with_directory_scopes(self):
        client = GoogleWorkspaceClient(KEY_INFO, 'admin@ndtatlas.com')
        opener = MagicMock()
        opener.open.return_value = token_response()

        with patch.object(GoogleWorkspaceClient, '_opener', return_value=opener):
            self.assertEqual(client._token(), 'tok')

        request = opener.open.call_args[0][0]
        self.assertEqual(request.full_url, TOKEN_URL)
        assertion = dict(pair.split('=') for pair in request.data.decode().split('&'))['assertion']
        claims = jwt.decode(assertion, PUBLIC_PEM, algorithms=['RS256'], audience=TOKEN_URL)
        self.assertEqual(claims['iss'], KEY_INFO['client_email'])
        self.assertEqual(claims['sub'], 'admin@ndtatlas.com')
        self.assertEqual(claims['scope'], ' '.join(SCOPES))

    def test_token_is_reused_until_it_expires(self):
        client = GoogleWorkspaceClient(KEY_INFO, 'admin@ndtatlas.com')
        opener = MagicMock()
        opener.open.return_value = token_response()

        with patch.object(GoogleWorkspaceClient, '_opener', return_value=opener):
            client._token()
            client._token()
        self.assertEqual(opener.open.call_count, 1)

    def test_unauthorized_client_explains_domain_wide_delegation(self):
        client = GoogleWorkspaceClient(KEY_INFO, 'admin@ndtatlas.com')
        opener = MagicMock()
        opener.open.side_effect = http_error(
            401, {'error': 'unauthorized_client', 'error_description': 'Client is unauthorized'}
        )

        with patch.object(GoogleWorkspaceClient, '_opener', return_value=opener):
            with self.assertRaisesRegex(GoogleWorkspaceError, 'Domain-wide delegation'):
                client._token()

    def test_invalid_grant_names_the_admin_email(self):
        client = GoogleWorkspaceClient(KEY_INFO, 'ghost@ndtatlas.com')
        opener = MagicMock()
        opener.open.side_effect = http_error(400, {'error': 'invalid_grant', 'error_description': 'Invalid email'})

        with patch.object(GoogleWorkspaceClient, '_opener', return_value=opener):
            with self.assertRaisesRegex(GoogleWorkspaceError, 'ghost@ndtatlas.com'):
                client._token()

    def test_corrupt_key_is_reported_not_raised_as_a_crash(self):
        client = GoogleWorkspaceClient({'client_email': 'x@y.z', 'private_key': 'not a key'}, 'admin@ndtatlas.com')
        with self.assertRaisesRegex(GoogleWorkspaceError, 'unreadable'):
            client._token()


class ClientRequestTests(APITestCase):
    def setUp(self):
        self.gw = GoogleWorkspaceClient(KEY_INFO, 'admin@ndtatlas.com')
        self.gw._tokens[SCOPES] = ('tok', 10 ** 12)

    def test_pagination_follows_next_page_token(self):
        pages = [
            {'users': [{'id': '1'}], 'nextPageToken': 'p2'},
            {'users': [{'id': '2'}]},
        ]
        with patch.object(GoogleWorkspaceClient, '_get', side_effect=pages) as get:
            users = self.gw.list_users('ndtatlas.com')

        self.assertEqual([u['id'] for u in users], ['1', '2'])
        self.assertNotIn('pageToken', get.call_args_list[0][0][1])
        self.assertEqual(get.call_args_list[1][0][1]['pageToken'], 'p2')

    def test_group_key_is_url_encoded_in_member_path(self):
        with patch.object(GoogleWorkspaceClient, '_get', return_value={'members': []}) as get:
            self.gw.list_group_members('a/b c')
        self.assertEqual(get.call_args[0][0], '/groups/a%2Fb%20c/members')

    def test_rate_limit_403_is_retried_then_succeeds(self):
        ok = MagicMock()
        ok.__enter__.return_value.read.return_value = b'{"users": []}'
        opener = MagicMock()
        opener.open.side_effect = [
            http_error(
                403,
                {'error': {'code': 403, 'message': 'slow down', 'errors': [{'reason': 'userRateLimitExceeded'}]}},
            ),
            ok,
        ]

        with patch.object(GoogleWorkspaceClient, '_opener', return_value=opener), \
                patch('apps.integrations.google_workspace.time.sleep'):
            self.assertEqual(self.gw._get('/users'), {'users': []})
        self.assertEqual(opener.open.call_count, 2)

    def test_forbidden_without_rate_limit_reason_is_not_retried(self):
        opener = MagicMock()
        opener.open.side_effect = http_error(
            403,
            {
                'error': {
                    'code': 403,
                    'message': 'Not Authorized to access this resource/api',
                    'errors': [{'reason': 'forbidden'}],
                }
            },
        )

        with patch.object(GoogleWorkspaceClient, '_opener', return_value=opener):
            with self.assertRaisesRegex(GoogleWorkspaceError, 'super admin'):
                self.gw._get('/users')
        self.assertEqual(opener.open.call_count, 1)

    def test_admin_sdk_disabled_gets_a_specific_message(self):
        opener = MagicMock()
        opener.open.side_effect = http_error(
            403,
            {
                'error': {
                    'code': 403,
                    'message': 'Admin SDK API has not been used in project 1 before or it is disabled.',
                    'errors': [{'reason': 'accessNotConfigured'}],
                }
            },
        )

        with patch.object(GoogleWorkspaceClient, '_opener', return_value=opener):
            with self.assertRaisesRegex(GoogleWorkspaceError, 'Enable "Admin SDK API"'):
                self.gw._get('/users')

    def test_group_with_unreadable_members_is_kept_with_an_error(self):
        groups = [{'id': 'g1', 'email': 'a@x.com'}, {'id': 'g2', 'email': 'b@x.com'}]

        def members(group_key):
            if group_key == 'g2':
                raise GoogleWorkspaceError('denied')
            return [{'email': 'u@x.com', 'type': 'USER'}]

        with patch.object(GoogleWorkspaceClient, 'list_groups', return_value=groups), \
                patch.object(GoogleWorkspaceClient, 'list_group_members', side_effect=members):
            result = {g['id']: g for g in self.gw.groups_with_members()}

        self.assertEqual(len(result['g1']['members']), 1)
        self.assertEqual(result['g1']['members_error'], '')
        self.assertEqual(result['g2']['members_error'], 'denied')


class DirectoryAssemblyTests(APITestCase):
    def raw_user(self, **overrides):
        base = {
            'id': 'u1',
            'primaryEmail': 'asha@ndtatlas.com',
            'name': {'fullName': 'Asha Rao', 'givenName': 'Asha', 'familyName': 'Rao'},
            'aliases': ['asha.rao@aeis.com'],
            'orgUnitPath': '/Engineering',
            'organizations': [{'title': 'SRE', 'department': 'Platform', 'primary': True}],
            'relations': [{'type': 'manager', 'value': 'lead@ndtatlas.com'}],
            'externalIds': [{'type': 'organization', 'value': 'E-42'}],
            'isEnrolledIn2Sv': True,
            'creationTime': '2024-01-01T00:00:00.000Z',
            'lastLoginTime': '2026-09-01T10:00:00.000Z',
        }
        base.update(overrides)
        return base

    def test_normalize_user_flattens_profile_fields(self):
        user = normalize_user(self.raw_user())
        self.assertEqual(user['full_name'], 'Asha Rao')
        self.assertEqual(user['domain'], 'ndtatlas.com')
        self.assertEqual((user['title'], user['department']), ('SRE', 'Platform'))
        self.assertEqual(user['manager'], 'lead@ndtatlas.com')
        self.assertEqual(user['employee_id'], 'E-42')
        self.assertTrue(user['is_enrolled_in_2sv'])

    def test_epoch_last_login_means_never_signed_in(self):
        user = normalize_user(self.raw_user(lastLoginTime=NEVER_LOGGED_IN))
        self.assertEqual(user['last_login_at'], '')

    def test_groups_are_matched_by_primary_or_alias_and_deduped(self):
        client = MagicMock()
        client.list_users.return_value = [self.raw_user()]
        client.groups_with_members.return_value = [
            {
                'id': 'g1', 'email': 'eng@ndtatlas.com', 'name': 'Engineering',
                'members': [
                    # Same person listed under primary and alias: one membership.
                    {'email': 'asha@ndtatlas.com', 'type': 'USER', 'role': 'OWNER'},
                    {'email': 'asha.rao@aeis.com', 'type': 'USER', 'role': 'MEMBER'},
                ],
                'members_error': '',
            },
            {
                'id': 'g2', 'email': 'all@aeis.com', 'name': 'All Staff',
                'members': [
                    {'email': 'ASHA.RAO@aeis.com', 'type': 'USER', 'role': 'MEMBER'},
                    {'email': 'eng@ndtatlas.com', 'type': 'GROUP', 'role': 'MEMBER'},
                    {'email': 'stranger@gmail.com', 'type': 'USER', 'role': 'MEMBER'},
                ],
                'members_error': '',
            },
            {'id': 'g3', 'email': 'other@ndtatlas.com', 'name': 'Other', 'members': [], 'members_error': ''},
        ]

        directory = build_directory(client, 'ndtatlas.com')

        [user] = directory['users']
        self.assertEqual(
            [(g['email'], g['role']) for g in user['groups']],
            [('all@aeis.com', 'MEMBER'), ('eng@ndtatlas.com', 'OWNER')],
        )
        counts = {g['email']: g['member_count'] for g in directory['groups']}
        self.assertEqual(counts, {'eng@ndtatlas.com': 2, 'all@aeis.com': 3, 'other@ndtatlas.com': 0})


class GoogleWorkspaceApiTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.it_user = User.objects.create_user(
            email='it@example.com', password='pw', full_name='IT', role='it_specialist'
        )
        self.client.force_authenticate(self.it_user)

    def create_payload(self, **overrides):
        payload = {
            'domain': 'NDTAtlas.com ',
            'label': 'NDT Atlas',
            'admin_email': 'admin@ndtatlas.com',
            'service_account_json': json.dumps(KEY_INFO),
        }
        payload.update(overrides)
        return payload

    def make_connection(self, domain='ndtatlas.com', **overrides):
        return GoogleWorkspaceConnection.objects.create(
            domain=domain,
            admin_email=f'admin@{domain}',
            service_account_json=json.dumps(KEY_INFO),
            service_account_email=KEY_INFO['client_email'],
            **overrides,
        )

    def test_create_normalises_domain_and_never_returns_the_key(self):
        response = self.client.post(reverse('google-workspace-connection-list'), self.create_payload(), format='json')

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['domain'], 'ndtatlas.com')
        self.assertEqual(response.data['service_account_email'], KEY_INFO['client_email'])
        self.assertEqual(response.data['service_account_client_id'], KEY_INFO['client_id'])
        self.assertTrue(response.data['has_service_account_key'])
        self.assertNotIn('service_account_json', response.data)
        self.assertNotIn('BEGIN PRIVATE KEY', json.dumps(response.data))

    def test_stored_key_keeps_only_what_auth_needs(self):
        self.client.post(reverse('google-workspace-connection-list'), self.create_payload(), format='json')
        stored = json.loads(GoogleWorkspaceConnection.objects.get().service_account_json)
        self.assertEqual(set(stored), {'type', 'client_email', 'client_id', 'private_key'})
        self.assertNotIn('project_id', stored)

    def test_rejects_bad_domain_and_bad_keys(self):
        url = reverse('google-workspace-connection-list')
        truncated = dict(KEY_INFO, private_key=KEY_INFO['private_key'][:80])
        bad_payloads = [
            self.create_payload(domain='https://ndtatlas.com'),
            self.create_payload(service_account_json='{nope'),
            self.create_payload(service_account_json=json.dumps({'type': 'authorized_user'})),
            self.create_payload(service_account_json=json.dumps(truncated)),
            self.create_payload(service_account_json=''),
        ]
        for payload in bad_payloads:
            with self.subTest(payload=payload):
                self.assertEqual(self.client.post(url, payload, format='json').status_code, 400)
        self.assertEqual(GoogleWorkspaceConnection.objects.count(), 0)

    def test_edit_with_blank_key_keeps_the_saved_key(self):
        connection = self.make_connection()
        response = self.client.patch(
            reverse('google-workspace-connection-detail', args=[connection.pk]),
            {'label': 'Renamed', 'service_account_json': ''},
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        connection.refresh_from_db()
        self.assertEqual(connection.label, 'Renamed')
        self.assertIn('private_key', connection.service_account_json)

    def test_non_it_users_are_forbidden(self):
        employee = User.objects.create_user(
            email='emp@example.com', password='pw', full_name='Emp', role='employee'
        )
        self.client.force_authenticate(employee)
        self.assertEqual(self.client.get(reverse('google-workspace-directory')).status_code, 403)
        self.assertEqual(self.client.get(reverse('google-workspace-connection-list')).status_code, 403)

    @patch('apps.integrations.views_google_workspace.GoogleWorkspaceClient.ping')
    def test_test_action_records_success(self, ping):
        connection = self.make_connection()
        response = self.client.post(reverse('google-workspace-connection-test', args=[connection.pk]))
        self.assertEqual(response.status_code, 200)
        connection.refresh_from_db()
        self.assertEqual(connection.last_test_status, 'success')
        ping.assert_called_once_with('ndtatlas.com')

    @patch(
        'apps.integrations.views_google_workspace.GoogleWorkspaceClient.ping',
        side_effect=GoogleWorkspaceError('no delegation', 401),
    )
    def test_test_action_failure_is_not_a_401(self, ping):
        connection = self.make_connection()
        response = self.client.post(reverse('google-workspace-connection-test', args=[connection.pk]))
        # A 401 here would make the frontend interceptor log the user out.
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data['message'], 'no delegation')
        connection.refresh_from_db()
        self.assertEqual(connection.last_test_status, 'failed')

    @patch('apps.integrations.views_google_workspace.build_directory')
    def test_directory_merges_domains_and_isolates_a_failing_one(self, build):
        self.make_connection('ndtatlas.com')
        self.make_connection('aeis.com')
        shared_group = {
            'id': 'g', 'email': 'all@ndtatlas.com', 'name': 'All',
            'description': '', 'member_count': 1, 'members_error': '',
        }

        def fake(client, domain):
            if domain == 'aeis.com':
                raise GoogleWorkspaceError('delegation missing')
            return {
                'users': [
                    {'full_name': 'Zed', 'primary_email': 'zed@ndtatlas.com'},
                    {'full_name': 'Amy', 'primary_email': 'amy@ndtatlas.com'},
                ],
                'groups': [shared_group],
            }

        build.side_effect = fake
        response = self.client.get(reverse('google-workspace-directory'))

        self.assertEqual(response.status_code, 200)
        by_domain = {d['domain']: d for d in response.data['domains']}
        self.assertTrue(by_domain['ndtatlas.com']['ok'])
        self.assertEqual(by_domain['ndtatlas.com']['user_count'], 2)
        self.assertFalse(by_domain['aeis.com']['ok'])
        self.assertEqual(by_domain['aeis.com']['error'], 'delegation missing')
        self.assertEqual([u['full_name'] for u in response.data['users']], ['Amy', 'Zed'])
        self.assertIsNotNone(GoogleWorkspaceConnection.objects.get(domain='ndtatlas.com').last_synced_at)
        self.assertIsNone(GoogleWorkspaceConnection.objects.get(domain='aeis.com').last_synced_at)

    @patch('apps.integrations.views_google_workspace.build_directory')
    def test_directory_is_cached_until_refresh(self, build):
        self.make_connection()
        build.return_value = {'users': [], 'groups': []}
        url = reverse('google-workspace-directory')

        self.client.get(url)
        self.client.get(url)
        self.assertEqual(build.call_count, 1)

        self.client.get(url, {'refresh': '1'})
        self.assertEqual(build.call_count, 2)

    @patch('apps.integrations.views_google_workspace.build_directory')
    def test_failed_load_is_not_cached(self, build):
        self.make_connection()
        build.side_effect = [GoogleWorkspaceError('boom'), {'users': [], 'groups': []}]
        url = reverse('google-workspace-directory')

        self.assertFalse(self.client.get(url).data['domains'][0]['ok'])
        self.assertTrue(self.client.get(url).data['domains'][0]['ok'])

    @patch('apps.integrations.views_google_workspace.build_directory')
    def test_inactive_or_keyless_connections_are_skipped(self, build):
        self.make_connection('ndtatlas.com', is_active=False)
        GoogleWorkspaceConnection.objects.create(domain='aeis.com', admin_email='a@aeis.com')
        response = self.client.get(reverse('google-workspace-directory'))
        self.assertEqual(response.data['domains'], [])
        build.assert_not_called()

    @patch('apps.integrations.views_google_workspace.build_directory')
    def test_editing_a_connection_invalidates_its_cache(self, build):
        connection = self.make_connection()
        build.return_value = {'users': [], 'groups': []}
        self.client.get(reverse('google-workspace-directory'))

        self.client.patch(
            reverse('google-workspace-connection-detail', args=[connection.pk]),
            {'admin_email': 'new@ndtatlas.com'},
            format='json',
        )
        self.client.get(reverse('google-workspace-directory'))
        self.assertEqual(build.call_count, 2)
