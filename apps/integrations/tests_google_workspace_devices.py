import json
from unittest.mock import MagicMock, patch

import jwt
from django.core.cache import cache
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.inventory.models import Asset, AssetType
from apps.users.models import User

from .google_workspace import (
    CLOUD_IDENTITY_BASE,
    CLOUD_IDENTITY_SCOPES,
    MOBILE_SCOPES,
    TOKEN_URL,
    GoogleWorkspaceClient,
    GoogleWorkspaceError,
)
from .google_workspace_devices import (
    apply_portal_assets,
    cloud_devices_for_user,
    guess_form_factor,
    merge_devices,
    normalize_cloud_device,
    normalize_mobile_device,
)
from .models import GoogleWorkspaceConnection
from .tests_google_workspace import KEY_INFO, PUBLIC_PEM, http_error, token_response
from .views import is_laptop_asset


def cloud_device(**overrides):
    base = {
        'name': 'devices/d1', 'deviceType': 'WINDOWS', 'manufacturer': 'Dell Inc.', 'model': 'Latitude 5420',
        'serialNumber': 'ABC123', 'osVersion': 'Windows 11', 'hostname': 'ATLAS-LT-01', 'ownerType': 'COMPANY',
    }
    base.update(overrides)
    return base


def device_user(email='asha@ndtatlas.com', device='d1', **overrides):
    base = {
        'name': f'devices/{device}/deviceUsers/u-{device}', 'userEmail': email, 'managementState': 'APPROVED',
        'createTime': '2026-01-05T10:00:00Z', 'lastSyncTime': '2026-10-01T08:00:00Z',
    }
    base.update(overrides)
    return base


class NormalizationTests(APITestCase):
    def test_android_phone_gets_a_tidy_make_and_is_mobile(self):
        row = normalize_mobile_device({
            'type': 'ANDROID', 'manufacturer': 'samsung', 'model': 'SM-S911B', 'serialNumber': 'R5CT123',
            'os': 'Android 14', 'status': 'APPROVED', 'lastSync': '2026-10-02T00:00:00Z',
        })
        self.assertEqual((row['platform'], row['category'], row['make'], row['model']), ('Android', 'mobile', 'Samsung', 'SM-S911B'))
        self.assertEqual((row['serial'], row['status'], row['sources']), ('R5CT123', 'Approved', ['mobile']))

    def test_iphone_with_no_manufacturer_is_apple(self):
        row = normalize_mobile_device({'type': 'IOS_SYNC', 'model': 'iPhone 15', 'os': 'iOS 17.4'})
        self.assertEqual((row['platform'], row['make'], row['category'], row['serial']), ('iOS', 'Apple', 'mobile', ''))

    def test_platform_falls_back_to_the_os_string(self):
        self.assertEqual(normalize_mobile_device({'os': 'Android 9'})['platform'], 'Android')
        self.assertEqual(normalize_mobile_device({'type': 'GOOGLE_SYNC'})['platform'], 'Google Sync')

    def test_windows_laptop_by_model_name(self):
        row = normalize_cloud_device(cloud_device(), device_user())
        self.assertEqual((row['platform'], row['category'], row['make'], row['serial']), ('Windows', 'computer', 'Dell Inc.', 'ABC123'))
        self.assertEqual((row['form_factor'], row['form_factor_source'], row['ownership']), ('laptop', 'model', 'company'))
        self.assertEqual((row['first_seen'], row['last_sync']), ('2026-01-05T10:00:00Z', '2026-10-01T08:00:00Z'))

    def test_form_factor_is_only_guessed_when_the_model_is_unambiguous(self):
        self.assertEqual(guess_form_factor('MacBook Pro 14'), 'laptop')
        self.assertEqual(guess_form_factor('Mac mini'), 'desktop')
        self.assertEqual(guess_form_factor('OptiPlex 7090'), 'desktop')
        self.assertEqual(guess_form_factor('XPS 8940'), '')  # XPS spans laptops and towers
        self.assertEqual(guess_form_factor(''), '')

    def test_mac_gets_apple_as_make_and_byod_is_personal(self):
        row = normalize_cloud_device(cloud_device(deviceType='MAC_OS', manufacturer='', model='MacBook Air', ownerType='BYOD'), device_user())
        self.assertEqual((row['platform'], row['make'], row['form_factor'], row['ownership']), ('macOS', 'Apple', 'laptop', 'personal'))

    def test_unknown_device_type_is_not_called_a_computer(self):
        row = normalize_cloud_device(cloud_device(deviceType='DEVICE_TYPE_UNSPECIFIED'), device_user())
        self.assertEqual((row['platform'], row['category'], row['form_factor']), ('', 'unknown', ''))


class SnapshotLookupTests(APITestCase):
    def test_only_the_users_devices_are_returned_matching_email_case_insensitively(self):
        snapshot = {
            'devices': {'devices/d1': cloud_device(), 'devices/d2': cloud_device(name='devices/d2', serialNumber='ZZZ', model='ThinkPad T14')},
            'device_users': [device_user('Asha@NDTAtlas.com', 'd1'), device_user('ravi@ndtatlas.com', 'd2')],
        }
        rows = cloud_devices_for_user(snapshot, 'asha@ndtatlas.com')
        self.assertEqual([r['serial'] for r in rows], ['ABC123'])

    def test_a_sign_in_on_a_device_missing_from_the_device_list_is_still_reported(self):
        rows = cloud_devices_for_user({'devices': {}, 'device_users': [device_user(device='gone')]}, 'asha@ndtatlas.com')
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]['serial'], rows[0]['platform']), ('', ''))
        self.assertEqual(rows[0]['last_sync'], '2026-10-01T08:00:00Z')


class MergeTests(APITestCase):
    def test_same_serial_from_both_sources_is_one_device_with_both_sources(self):
        cloud = normalize_cloud_device(
            cloud_device(deviceType='ANDROID', model='Pixel 8', serialNumber='sn1', manufacturer='Google', osVersion=''),
            device_user(),
        )
        mobile = normalize_mobile_device({'type': 'ANDROID', 'model': 'Pixel 8', 'serialNumber': 'SN1', 'os': 'Android 14', 'lastSync': '2026-10-05T00:00:00Z'})
        [row] = merge_devices([mobile, cloud])
        self.assertEqual(row['sources'], ['cloud_identity', 'mobile'])
        self.assertEqual((row['make'], row['os']), ('Google', 'Android 14'))  # cloud wins ties, gaps filled from mobile
        self.assertEqual(row['id'], 'device-0')

    def test_serial_less_phones_merge_only_when_unambiguous(self):
        def mobile(model='Pixel 8'):
            return normalize_mobile_device({'type': 'ANDROID', 'model': model, 'os': 'Android 14'})

        def cloud(model='Pixel 8'):
            return normalize_cloud_device(cloud_device(deviceType='ANDROID', model=model, serialNumber=''), device_user())

        self.assertEqual(len(merge_devices([mobile(), cloud()])), 1)
        # Two identical serial-less phones in the same source stay two devices.
        self.assertEqual(len(merge_devices([mobile(), mobile()])), 2)
        self.assertEqual(len(merge_devices([mobile(), mobile(), cloud()])), 3)
        # Different models are different devices.
        self.assertEqual(len(merge_devices([mobile('Pixel 8'), cloud('Galaxy S23')])), 2)

    def test_newest_sync_first(self):
        old = normalize_cloud_device(cloud_device(serialNumber='A'), device_user(lastSyncTime='2026-01-01T00:00:00Z'))
        new = normalize_cloud_device(cloud_device(serialNumber='B'), device_user(device='d2', lastSyncTime='2026-09-01T00:00:00Z'))
        self.assertEqual([r['serial'] for r in merge_devices([old, new])], ['B', 'A'])


class PortalAssetTests(APITestCase):
    def setUp(self):
        self.laptop_type = AssetType.objects.create(name='Laptop', asset_type='hardware')
        self.desktop_type = AssetType.objects.create(name='Desktop', asset_type='hardware')

    def asset(self, serial, asset_type, asset_id):
        return Asset.objects.create(asset_id=asset_id, asset_type=asset_type, serial_number=serial, status='assigned')

    def test_portal_asset_type_overrides_a_model_name_guess(self):
        # "OptiPlex" would be guessed a desktop, but the portal says this serial is a laptop.
        row = normalize_cloud_device(cloud_device(model='OptiPlex 7090', serialNumber='abc999'), device_user())
        self.assertEqual(row['form_factor'], 'desktop')
        asset = self.asset('ABC999', self.laptop_type, 'LT-1')

        [result] = apply_portal_assets([row], {'ABC999': asset}, is_laptop_asset)

        self.assertEqual((result['form_factor'], result['form_factor_source']), ('laptop', 'portal'))
        self.assertEqual(result['portal_asset'], {'id': asset.id, 'asset_id': 'LT-1', 'type': 'Laptop', 'status': 'assigned'})

    def test_non_laptop_asset_uses_its_type_name_and_phones_are_left_alone(self):
        pc = normalize_cloud_device(cloud_device(model='Custom build', serialNumber='PC1'), device_user())
        phone = normalize_mobile_device({'type': 'ANDROID', 'model': 'Pixel', 'serialNumber': 'PH1'})
        assets = {'PC1': self.asset('PC1', self.desktop_type, 'DT-1'), 'PH1': self.asset('PH1', self.desktop_type, 'DT-2')}

        pc_result, phone_result = apply_portal_assets([pc, phone], assets, is_laptop_asset)

        self.assertEqual((pc_result['form_factor'], pc_result['form_factor_source']), ('desktop', 'portal'))
        self.assertEqual(phone_result['form_factor'], '')  # form factor only applies to computers
        self.assertEqual(phone_result['portal_asset']['asset_id'], 'DT-2')

    def test_unmatched_and_serial_less_devices_have_no_portal_asset(self):
        rows = [normalize_cloud_device(cloud_device(serialNumber=''), device_user())]
        [result] = apply_portal_assets(rows, {'': 'would-be-wrong'}, is_laptop_asset)
        self.assertIsNone(result['portal_asset'])


class DeviceClientTests(APITestCase):
    def setUp(self):
        self.gw = GoogleWorkspaceClient(KEY_INFO, 'admin@ndtatlas.com')

    def test_mobile_query_asks_for_the_user_and_drops_other_matches(self):
        response = {'mobiledevices': [
            {'email': ['asha@ndtatlas.com'], 'model': 'A'},
            {'email': ['asha@ndtatlas.com.au'], 'model': 'search is substring based, so this is someone else'},
            {'email': ['ASHA@ndtatlas.com', 'other@ndtatlas.com'], 'model': 'B'},
        ]}
        with patch.object(GoogleWorkspaceClient, '_get', return_value=response) as get:
            devices = self.gw.list_mobile_devices('asha@ndtatlas.com')

        self.assertEqual([d['model'] for d in devices], ['A', 'B'])
        path, params = get.call_args[0]
        self.assertEqual(path, '/customer/my_customer/devices/mobile')
        self.assertEqual((params['query'], params['projection']), ('email:asha@ndtatlas.com', 'FULL'))
        self.assertEqual(get.call_args[1]['scopes'], MOBILE_SCOPES)

    def test_cloud_identity_fleet_pages_both_lists_with_the_right_api_and_scope(self):
        pages = [
            {'devices': [{'name': 'devices/d1'}], 'nextPageToken': 'p2'},
            {'devices': [{'name': 'devices/d2'}]},
            {'deviceUsers': [{'name': 'devices/d1/deviceUsers/u1'}], 'nextPageToken': 'u2'},
            {'deviceUsers': [{'name': 'devices/d2/deviceUsers/u2'}]},
        ]
        with patch.object(GoogleWorkspaceClient, '_get', side_effect=pages) as get:
            snapshot = self.gw.cloud_identity_devices()

        self.assertEqual(sorted(snapshot['devices']), ['devices/d1', 'devices/d2'])
        self.assertEqual(len(snapshot['device_users']), 2)
        paths = [call[0][0] for call in get.call_args_list]
        self.assertEqual(paths, ['/devices', '/devices', '/devices/-/deviceUsers', '/devices/-/deviceUsers'])
        for call in get.call_args_list:
            self.assertEqual((call[1]['base'], call[1]['scopes']), (CLOUD_IDENTITY_BASE, CLOUD_IDENTITY_SCOPES))
            self.assertEqual(call[0][1]['customer'], 'customers/my_customer')
        self.assertEqual(get.call_args_list[1][0][1]['pageToken'], 'p2')

    def test_each_device_token_asks_only_for_its_own_scope(self):
        for scopes in (MOBILE_SCOPES, CLOUD_IDENTITY_SCOPES):
            with self.subTest(scopes=scopes):
                client = GoogleWorkspaceClient(KEY_INFO, 'admin@ndtatlas.com')
                opener = MagicMock()
                opener.open.return_value = token_response()
                with patch.object(GoogleWorkspaceClient, '_opener', return_value=opener):
                    client._token(scopes)
                assertion = dict(pair.split('=') for pair in opener.open.call_args[0][0].data.decode().split('&'))['assertion']
                claims = jwt.decode(assertion, PUBLIC_PEM, algorithms=['RS256'], audience=TOKEN_URL)
                self.assertEqual(claims['scope'], ' '.join(scopes))

    def test_cloud_identity_api_not_enabled_names_that_api_not_admin_sdk(self):
        self.gw._tokens[CLOUD_IDENTITY_SCOPES] = ('tok', 10 ** 12)
        opener = MagicMock()
        opener.open.side_effect = http_error(403, {'error': {'code': 403, 'message': 'Cloud Identity API has not been used in project 1 before or it is disabled.', 'errors': [{'reason': 'accessNotConfigured'}]}})
        with patch.object(GoogleWorkspaceClient, '_opener', return_value=opener):
            with self.assertRaises(GoogleWorkspaceError) as caught:
                self.gw._get('/devices', base=CLOUD_IDENTITY_BASE, scopes=CLOUD_IDENTITY_SCOPES)
        self.assertIn('Enable "Cloud Identity API"', str(caught.exception))
        self.assertNotIn('Admin SDK', str(caught.exception))


class UserDevicesApiTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.it_user = User.objects.create_user(email='it@example.com', password='pw', full_name='IT', role='it_specialist')
        self.client.force_authenticate(self.it_user)
        GoogleWorkspaceConnection.objects.create(
            domain='ndtatlas.com', admin_email='admin@ndtatlas.com',
            service_account_json=json.dumps(KEY_INFO), service_account_email=KEY_INFO['client_email'],
        )
        self.email = 'asha@ndtatlas.com'
        self.snapshot = {
            'devices': {'devices/d1': cloud_device()},
            'device_users': [device_user(self.email, 'd1'), device_user('ravi@ndtatlas.com', 'd9')],
        }
        self.phone = {'type': 'ANDROID', 'manufacturer': 'samsung', 'model': 'SM-S911B', 'serialNumber': 'R5CT123',
                      'os': 'Android 14', 'email': [self.email], 'lastSync': '2026-10-02T00:00:00Z'}

    def get(self, **params):
        params.setdefault('email', self.email)
        return self.client.get(reverse('google-workspace-user-devices'), params)

    PATCH = 'apps.integrations.views_google_workspace.GoogleWorkspaceClient'

    def test_lists_laptop_and_phone_with_summary_and_portal_match(self):
        laptop_type = AssetType.objects.create(name='Laptop', asset_type='hardware')
        Asset.objects.create(asset_id='LT-77', asset_type=laptop_type, serial_number='abc123', status='assigned')
        with patch(f'{self.PATCH}.cloud_identity_devices', return_value=self.snapshot), \
                patch(f'{self.PATCH}.list_mobile_devices', return_value=[self.phone]):
            response = self.get()

        self.assertEqual(response.status_code, 200, response.data)
        by_serial = {d['serial']: d for d in response.data['devices']}
        self.assertEqual(set(by_serial), {'ABC123', 'R5CT123'})
        laptop, phone = by_serial['ABC123'], by_serial['R5CT123']
        self.assertEqual((laptop['category'], laptop['form_factor'], laptop['form_factor_source']), ('computer', 'laptop', 'portal'))
        self.assertEqual(laptop['portal_asset']['asset_id'], 'LT-77')
        self.assertEqual((phone['category'], phone['make'], phone['platform']), ('mobile', 'Samsung', 'Android'))
        self.assertIsNone(phone['portal_asset'])
        self.assertEqual(response.data['summary'], {'total': 2, 'mobile': 1, 'laptops': 1, 'other_computers': 0})
        self.assertEqual(response.data['sources']['mobile'], {'ok': True, 'error': '', 'count': 1})

    def test_one_source_failing_still_shows_the_other(self):
        with patch(f'{self.PATCH}.cloud_identity_devices', side_effect=GoogleWorkspaceError('Enable "Cloud Identity API"', 403)), \
                patch(f'{self.PATCH}.list_mobile_devices', return_value=[self.phone]):
            response = self.get()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['devices']), 1)
        self.assertEqual(response.data['sources']['cloud_identity'], {'ok': False, 'error': 'Enable "Cloud Identity API"', 'count': 0})
        self.assertTrue(response.data['sources']['mobile']['ok'])

    def test_both_failing_is_a_502_naming_each_problem(self):
        with patch(f'{self.PATCH}.cloud_identity_devices', side_effect=GoogleWorkspaceError('no cloud scope', 401)), \
                patch(f'{self.PATCH}.list_mobile_devices', side_effect=GoogleWorkspaceError('no mobile scope', 401)):
            response = self.get()
        self.assertEqual(response.status_code, 502)  # a 401 would log the portal user out
        self.assertIn('Mobile devices: no mobile scope', response.data['detail'])
        self.assertIn('Computers: no cloud scope', response.data['detail'])

    def test_a_user_with_no_devices_is_an_empty_success(self):
        with patch(f'{self.PATCH}.cloud_identity_devices', return_value={'devices': {}, 'device_users': []}), \
                patch(f'{self.PATCH}.list_mobile_devices', return_value=[]):
            response = self.get()
        self.assertEqual((response.status_code, response.data['devices']), (200, []))
        self.assertEqual(response.data['summary']['total'], 0)

    def test_fleet_read_is_shared_between_users_and_refresh_bypasses_caches(self):
        with patch(f'{self.PATCH}.cloud_identity_devices', return_value=self.snapshot) as fleet, \
                patch(f'{self.PATCH}.list_mobile_devices', return_value=[]) as mobile:
            self.get()
            self.get()  # same user: fully cached
            self.assertEqual((fleet.call_count, mobile.call_count), (1, 1))
            self.get(email='ravi@ndtatlas.com')  # another user: mobile per user, fleet shared
            self.assertEqual((fleet.call_count, mobile.call_count), (1, 2))
            self.get(refresh='1')
            self.assertEqual((fleet.call_count, mobile.call_count), (2, 3))

    def test_failures_are_not_cached(self):
        with patch(f'{self.PATCH}.cloud_identity_devices', side_effect=[GoogleWorkspaceError('boom'), self.snapshot]), \
                patch(f'{self.PATCH}.list_mobile_devices', side_effect=[GoogleWorkspaceError('boom'), []]):
            self.assertEqual(self.get().status_code, 502)
            second = self.get()
        self.assertEqual((second.status_code, len(second.data['devices'])), (200, 1))

    def test_validation_and_permissions(self):
        self.assertEqual(self.client.get(reverse('google-workspace-user-devices')).status_code, 400)
        self.assertEqual(self.get(email='x@unconnected.org').status_code, 404)
        employee = User.objects.create_user(email='emp@example.com', password='pw', full_name='Emp', role='employee')
        self.client.force_authenticate(employee)
        self.assertEqual(self.get().status_code, 403)


class FleetDevicesApiTests(APITestCase):
    PATCH = 'apps.integrations.views_google_workspace.GoogleWorkspaceClient'

    def setUp(self):
        cache.clear()
        self.client.force_authenticate(User.objects.create_user(email='it@example.com', password='pw', full_name='IT', role='it_specialist'))
        GoogleWorkspaceConnection.objects.create(domain='ndtatlas.com', admin_email='a@ndtatlas.com', service_account_json=json.dumps(KEY_INFO))
        self.snapshot = {
            'devices': {'devices/d1': cloud_device(), 'devices/d2': cloud_device(name='devices/d2', serialNumber='XYZ9', model='MacBook Pro', deviceType='MAC_OS')},
            'device_users': [
                device_user('asha@ndtatlas.com', 'd1', lastSyncTime='2026-09-01T00:00:00Z', createTime='2026-02-01T00:00:00Z'),
                device_user('ravi@ndtatlas.com', 'd1', lastSyncTime='2026-10-01T00:00:00Z', createTime='2026-01-01T00:00:00Z'),
                device_user('meera@ndtatlas.com', 'd2'),
            ],
        }
        self.phone = {'type': 'ANDROID', 'manufacturer': 'samsung', 'model': 'SM-S911B', 'serialNumber': 'R5CT123',
                      'resourceId': 'm1', 'email': ['Asha@ndtatlas.com'], 'os': 'Android 14'}

    def get(self, **params):
        return self.client.get(reverse('google-workspace-devices'), params)

    def test_one_row_per_device_with_every_user_and_portal_match(self):
        Asset.objects.create(asset_id='LT-5', asset_type=AssetType.objects.create(name='Laptop', asset_type='hardware'), serial_number='abc123')
        with patch(f'{self.PATCH}.cloud_identity_devices', return_value=self.snapshot), \
                patch(f'{self.PATCH}.list_all_mobile_devices', return_value=[self.phone]):
            response = self.get()

        self.assertEqual(response.status_code, 200, response.data)
        by_serial = {d['serial']: d for d in response.data['devices']}
        shared = by_serial['ABC123']
        self.assertEqual(shared['users'], ['asha@ndtatlas.com', 'ravi@ndtatlas.com'])
        self.assertEqual((shared['first_seen'], shared['last_sync']), ('2026-01-01T00:00:00Z', '2026-10-01T00:00:00Z'))
        self.assertEqual(shared['portal_asset']['asset_id'], 'LT-5')
        self.assertEqual(by_serial['R5CT123']['users'], ['asha@ndtatlas.com'])
        self.assertEqual(response.data['summary'], {'total': 3, 'mobile': 1, 'laptops': 2, 'other_computers': 0, 'in_portal': 1})

    def test_same_device_via_two_connections_is_counted_once(self):
        GoogleWorkspaceConnection.objects.create(domain='amplifailabs.in', admin_email='a@amplifailabs.in', service_account_json=json.dumps(KEY_INFO))
        with patch(f'{self.PATCH}.cloud_identity_devices', return_value=self.snapshot), \
                patch(f'{self.PATCH}.list_all_mobile_devices', return_value=[self.phone]):
            response = self.get()
        self.assertEqual(response.data['summary']['total'], 3)

    def test_one_source_failing_keeps_the_other_and_both_failing_is_502(self):
        with patch(f'{self.PATCH}.cloud_identity_devices', side_effect=GoogleWorkspaceError('no cloud', 403)), \
                patch(f'{self.PATCH}.list_all_mobile_devices', return_value=[self.phone]):
            partial = self.get()
        self.assertEqual((partial.status_code, len(partial.data['devices'])), (200, 1))
        self.assertFalse(partial.data['sources']['cloud_identity']['ok'])
        self.assertIn('no cloud', partial.data['sources']['cloud_identity']['error'])

        cache.clear()
        with patch(f'{self.PATCH}.cloud_identity_devices', side_effect=GoogleWorkspaceError('no cloud', 401)), \
                patch(f'{self.PATCH}.list_all_mobile_devices', side_effect=GoogleWorkspaceError('no mobile', 401)):
            both = self.get()
        self.assertEqual(both.status_code, 502)
        self.assertIn('no mobile', both.data['detail'])
        self.assertIn('no cloud', both.data['detail'])

    def test_cached_until_refresh_and_shared_with_the_per_user_view(self):
        with patch(f'{self.PATCH}.cloud_identity_devices', return_value=self.snapshot) as fleet, \
                patch(f'{self.PATCH}.list_all_mobile_devices', return_value=[]) as mobile, \
                patch(f'{self.PATCH}.list_mobile_devices', return_value=[]):
            self.get()
            self.get()
            self.assertEqual((fleet.call_count, mobile.call_count), (1, 1))
            # The per-user page reuses the same cached cloud fleet.
            self.client.get(reverse('google-workspace-user-devices'), {'email': 'asha@ndtatlas.com'})
            self.assertEqual(fleet.call_count, 1)
            self.get(refresh='1')
            self.assertEqual((fleet.call_count, mobile.call_count), (2, 2))

    def test_no_connections_is_an_empty_list_and_employees_are_forbidden(self):
        GoogleWorkspaceConnection.objects.all().delete()
        self.assertEqual(self.get().data['devices'], [])
        self.client.force_authenticate(User.objects.create_user(email='e@example.com', password='pw', full_name='E', role='employee'))
        self.assertEqual(self.get().status_code, 403)


class ProfilePhotoTests(APITestCase):
    PATCH = 'apps.integrations.views_google_workspace.GoogleWorkspaceClient'

    def setUp(self):
        cache.clear()
        self.gw = GoogleWorkspaceClient(KEY_INFO, 'admin@ndtatlas.com')
        self.client.force_authenticate(User.objects.create_user(email='it@example.com', password='pw', full_name='IT', role='it_specialist'))
        self.connection = GoogleWorkspaceConnection.objects.create(domain='ndtatlas.com', admin_email='a@ndtatlas.com', service_account_json=json.dumps(KEY_INFO))

    def test_directory_user_flags_who_has_a_photo_without_keeping_the_private_url(self):
        from .google_workspace import normalize_user
        with_photo = normalize_user({'primaryEmail': 'a@x.com', 'thumbnailPhotoUrl': 'https://private/abc'})
        without = normalize_user({'primaryEmail': 'b@x.com'})
        self.assertEqual((with_photo['has_photo'], without['has_photo']), (True, False))
        self.assertNotIn('https://private/abc', json.dumps(with_photo))

    def test_web_safe_base64_is_converted_so_browsers_can_show_it(self):
        import base64
        raw = bytes([0xFB, 0xFF, 0xFE, 0x01, 0x02])  # standard base64 has '+' and '/' here
        web_safe = base64.urlsafe_b64encode(raw).decode().rstrip('=')
        self.assertTrue('-' in web_safe or '_' in web_safe)
        with patch.object(GoogleWorkspaceClient, '_get', return_value={'photoData': web_safe, 'mimeType': 'JPEG'}):
            uri = self.gw.user_photo('a@x.com')
        self.assertTrue(uri.startswith('data:image/jpeg;base64,'))
        self.assertEqual(base64.b64decode(uri.split(',', 1)[1], validate=True), raw)

    def test_mime_type_is_accepted_as_google_actually_sends_it_and_in_short_form(self):
        # Google's live responses say "image/jpeg" / "image/png"; the docs never showed the format.
        for sent, expected in (('image/jpeg', 'image/jpeg'), ('image/png', 'image/png'), ('IMAGE/PNG', 'image/png'), ('JPEG', 'image/jpeg'), ('png', 'image/png')):
            with self.subTest(sent=sent), patch.object(GoogleWorkspaceClient, '_get', return_value={'photoData': 'AAAA', 'mimeType': sent}):
                self.assertEqual(self.gw.user_photo('a@x.com'), f'data:{expected};base64,AAAA')

    def test_no_photo_unsupported_corrupt_and_oversized_are_none_but_real_errors_raise(self):
        with patch.object(GoogleWorkspaceClient, '_get', side_effect=GoogleWorkspaceError('Resource Not Found: photo', 404)):
            self.assertIsNone(self.gw.user_photo('a@x.com'))
        for response in ({'photoData': 'AAAA', 'mimeType': 'TIFF'}, {'photoData': '', 'mimeType': 'PNG'}, {'photoData': '!!!notbase64', 'mimeType': 'PNG'}, {}):
            with self.subTest(response=response), patch.object(GoogleWorkspaceClient, '_get', return_value=response):
                self.assertIsNone(self.gw.user_photo('a@x.com'))
        import base64
        huge = base64.b64encode(b'x' * (301 * 1024)).decode()
        with patch.object(GoogleWorkspaceClient, '_get', return_value={'photoData': huge, 'mimeType': 'PNG'}):
            self.assertIsNone(self.gw.user_photo('a@x.com'))
        with patch.object(GoogleWorkspaceClient, '_get', side_effect=GoogleWorkspaceError('denied', 403)):
            with self.assertRaises(GoogleWorkspaceError):
                self.gw.user_photo('a@x.com')

    def get(self, emails):
        # Comma string for convenience; the real client posts a list.
        return self.client.post(reverse('google-workspace-user-photos'), {'emails': emails.split(',')}, format='json')

    def test_batch_returns_photos_null_for_none_and_for_unconnected_domains(self):
        def photo(self_, email):
            return 'data:image/png;base64,AAAA' if email == 'has@ndtatlas.com' else None

        with patch(f'{self.PATCH}.user_photo', photo), patch(f'{self.PATCH}._token', return_value='tok'):
            response = self.get('Has@ndtatlas.com, none@ndtatlas.com,x@other.org,has@ndtatlas.com')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['photos'], {
            'has@ndtatlas.com': 'data:image/png;base64,AAAA', 'none@ndtatlas.com': None, 'x@other.org': None,
        })

    def test_results_including_no_photo_are_cached_but_transient_errors_are_not(self):
        calls = []

        def photo(self_, email):
            calls.append(email)
            if email == 'flaky@ndtatlas.com':
                raise GoogleWorkspaceError('blip', 503)
            return None if email == 'none@ndtatlas.com' else 'data:image/png;base64,AAAA'

        with patch(f'{self.PATCH}.user_photo', photo), patch(f'{self.PATCH}._token', return_value='tok'):
            self.get('a@ndtatlas.com,none@ndtatlas.com,flaky@ndtatlas.com')
            self.assertEqual(len(calls), 3)
            again = self.get('a@ndtatlas.com,none@ndtatlas.com,flaky@ndtatlas.com')

        self.assertEqual(sorted(calls[3:]), ['flaky@ndtatlas.com'])  # only the failed one is retried
        self.assertEqual(again.data['photos']['a@ndtatlas.com'], 'data:image/png;base64,AAAA')
        self.assertIsNone(again.data['photos']['none@ndtatlas.com'])

    def test_an_auth_failure_degrades_to_no_photos_not_an_error(self):
        with patch(f'{self.PATCH}._token', side_effect=GoogleWorkspaceError('no delegation', 401)):
            response = self.get('a@ndtatlas.com')
        self.assertEqual((response.status_code, response.data['photos']), (200, {'a@ndtatlas.com': None}))
        self.assertEqual(response.data['error'], 'no delegation')  # so the page can say why

    def test_a_failed_fetch_reports_its_reason_but_a_clean_run_reports_none(self):
        def photo(self_, email):
            raise GoogleWorkspaceError('Not Authorized to access this resource/api', 403)

        with patch(f'{self.PATCH}.user_photo', photo), patch(f'{self.PATCH}._token', return_value='tok'):
            failed = self.get('a@ndtatlas.com')
        self.assertEqual(failed.data['error'], 'Not Authorized to access this resource/api')

        cache.clear()
        with patch(f'{self.PATCH}.user_photo', return_value=None), patch(f'{self.PATCH}._token', return_value='tok'):
            self.assertEqual(self.get('a@ndtatlas.com').data['error'], '')

    def test_addresses_are_never_put_in_the_url_so_they_stay_out_of_logs(self):
        from apps.activity_log.models import ActivityLog
        with patch(f'{self.PATCH}.user_photo', return_value=None), patch(f'{self.PATCH}._token', return_value='tok'):
            self.get('a@ndtatlas.com,b@ndtatlas.com')
        # GET is no longer accepted, and nothing recorded for the request carries an address.
        self.assertEqual(self.client.get(reverse('google-workspace-user-photos'), {'emails': 'a@ndtatlas.com'}).status_code, 405)
        for entry in ActivityLog.objects.filter(path__endswith='/user-photos/'):
            self.assertNotIn('@', entry.metadata.get('query_string', ''))
            self.assertNotIn('@', entry.path)

    def test_validation_and_permissions(self):
        self.assertEqual(self.client.post(reverse('google-workspace-user-photos'), {}, format='json').status_code, 400)
        self.assertEqual(self.client.post(reverse('google-workspace-user-photos'), {'emails': 'not-a-list-of-emails'}, format='json').status_code, 400)
        self.assertEqual(self.get('not-an-email').status_code, 400)
        too_many = ','.join(f'u{i}@ndtatlas.com' for i in range(51))
        self.assertEqual(self.get(too_many).status_code, 400)
        self.client.force_authenticate(User.objects.create_user(email='e@example.com', password='pw', full_name='E', role='employee'))
        self.assertEqual(self.get('a@ndtatlas.com').status_code, 403)
