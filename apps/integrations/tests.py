from unittest.mock import patch

from django.utils import timezone
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.inventory.models import Asset
from apps.users.models import User

from .models import SureMDMConnection, TrellixConnection
from .suremdm import SureMDMClient


class SureMDMIntegrationTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='it@example.com',
            password='password',
            full_name='IT User',
            role='it_specialist',
        )
        self.client.force_authenticate(self.user)
        SureMDMConnection.objects.create(
            base_url='https://suremdm.42gears.com/api',
            username='user',
            password='pass',
            api_key='key',
        )

    @patch.object(SureMDMClient, 'post')
    def test_trigger_apps_refresh_posts_get_device_apps_job(self, post):
        post.return_value = (200, {})
        client = SureMDMClient(base_url='https://suremdm.42gears.com/api', username='user', password='pass', api_key='key')

        result = client.trigger_apps_refresh('123')

        self.assertTrue(result)
        post.assert_called_once_with('dynamicjob', {'JobType': 'GET_DEVICE_APPS', 'DeviceID': '123'})

    def test_trigger_apps_refresh_without_device_id_is_a_noop(self):
        client = SureMDMClient(base_url='https://suremdm.42gears.com/api', username='user', password='pass', api_key='key')

        self.assertFalse(client.trigger_apps_refresh(None))

    @patch('apps.integrations.views.SureMDMClient.list_devices')
    def test_sync_assets_creates_suremdm_assets(self, list_devices):
        list_devices.return_value = [
            {
                'DeviceID': '123',
                'DeviceName': 'Front Desk Tablet',
                'SerialNumber': 'SN123',
                'Platform': 'Android',
                'Model': 'Tab A',
            }
        ]

        response = self.client.post(reverse('suremdm-sync-assets'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['created'], 1)
        self.assertTrue(Asset.objects.filter(asset_id='SUREMDM-123').exists())

    @patch('apps.integrations.views.SureMDMClient.device_log')
    @patch('apps.integrations.views.SureMDMClient.list_devices')
    def test_active_time_pairs_online_offline_log_events(self, list_devices, device_log):
        list_devices.return_value = [
            {
                'DeviceID': '123',
                'DeviceName': 'Front Desk Tablet',
                'SerialNumber': 'SN123',
                'Platform': 'Windows',
                'Model': 'Tab A',
            }
        ]
        device_log.return_value = [
            {'Time': '2026-07-01T09:00:00.000Z', 'Message': '1'},
            {'Time': '2026-07-01T09:30:00.000Z', 'Message': '2'},
            {'Time': '2026-07-01T12:00:00.000Z', 'Message': '0'},
        ]

        response = self.client.get(reverse('suremdm-active-time'), {'start_date': '2026-07-01', 'end_date': '2026-07-01'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['total_devices'], 1)
        self.assertEqual(response.data['results'][0]['date'], '2026-07-01')
        self.assertEqual(response.data['results'][0]['name'], 'Front Desk Tablet')
        self.assertEqual(response.data['results'][0]['active_minutes'], 180.0)
        self.assertEqual(response.data['results'][0]['activity_source'], 'online_status_log')

    @patch('apps.integrations.views.SureMDMClient.device_log')
    @patch('apps.integrations.views.SureMDMClient.list_devices')
    def test_active_time_sums_multiple_sessions_same_day(self, list_devices, device_log):
        list_devices.return_value = [
            {
                'DeviceID': '123',
                'DeviceName': 'Front Desk Tablet',
                'SerialNumber': 'SN123',
                'Platform': 'Windows',
                'Model': 'Tab A',
            }
        ]
        device_log.return_value = [
            {'Time': '2026-07-01T09:00:00.000Z', 'Message': '1'},
            {'Time': '2026-07-01T10:00:00.000Z', 'Message': '0'},
            {'Time': '2026-07-01T11:00:00.000Z', 'Message': '1'},
            {'Time': '2026-07-01T13:00:00.000Z', 'Message': '0'},
        ]

        response = self.client.get(reverse('suremdm-active-time'), {'start_date': '2026-07-01', 'end_date': '2026-07-01'})

        self.assertEqual(response.status_code, 200)
        # Two separate sessions the same day are kept as distinct rows.
        self.assertEqual(len(response.data['results']), 2)
        results_by_start = {row['active_from']: row for row in response.data['results']}
        self.assertIn('2026-07-01T09:00:00+00:00', results_by_start)
        self.assertIn('2026-07-01T11:00:00+00:00', results_by_start)
        self.assertEqual(results_by_start['2026-07-01T09:00:00+00:00']['active_minutes'], 60.0)
        self.assertEqual(results_by_start['2026-07-01T09:00:00+00:00']['logged_off_at'], '2026-07-01T10:00:00+00:00')
        self.assertEqual(results_by_start['2026-07-01T11:00:00+00:00']['active_minutes'], 120.0)
        self.assertEqual(results_by_start['2026-07-01T11:00:00+00:00']['logged_off_at'], '2026-07-01T13:00:00+00:00')
        # Both rows report the same day-level total (60 + 120 minutes).
        self.assertEqual(results_by_start['2026-07-01T09:00:00+00:00']['day_active_minutes'], 180.0)
        self.assertEqual(results_by_start['2026-07-01T11:00:00+00:00']['day_active_minutes'], 180.0)

    @patch('apps.integrations.views.SureMDMClient.device_log')
    @patch('apps.integrations.views.SureMDMClient.list_devices')
    def test_active_time_splits_session_across_midnight(self, list_devices, device_log):
        list_devices.return_value = [
            {
                'DeviceID': '123',
                'DeviceName': 'Front Desk Tablet',
                'SerialNumber': 'SN123',
                'Platform': 'Windows',
                'Model': 'Tab A',
            }
        ]
        # Server runs in IST (UTC+5:30), so local midnight for 2026-07-02
        # falls at 2026-07-01T18:30:00Z. This session straddles that boundary.
        device_log.return_value = [
            {'Time': '2026-07-01T17:00:00.000Z', 'Message': '1'},
            {'Time': '2026-07-01T20:00:00.000Z', 'Message': '0'},
        ]

        response = self.client.get(reverse('suremdm-active-time'), {'start_date': '2026-07-01', 'end_date': '2026-07-02'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 2)
        by_date = {row['date']: row for row in response.data['results']}
        self.assertIn('2026-07-01', by_date)
        self.assertIn('2026-07-02', by_date)
        self.assertAlmostEqual(by_date['2026-07-01']['active_minutes'] + by_date['2026-07-02']['active_minutes'], 180.0)

    @patch('apps.integrations.views.SureMDMClient.device_log')
    @patch('apps.integrations.views.SureMDMClient.list_devices')
    def test_active_time_treats_still_online_device_as_open_session(self, list_devices, device_log):
        list_devices.return_value = [
            {
                'DeviceID': '123',
                'DeviceName': 'Front Desk Tablet',
                'SerialNumber': 'SN123',
                'Platform': 'Windows',
                'Model': 'Tab A',
            }
        ]
        device_log.return_value = [
            {'Time': '2026-07-01T09:00:00.000Z', 'Message': '1'},
        ]

        response = self.client.get(reverse('suremdm-active-time'), {'start_date': '2026-07-01', 'end_date': '2026-07-01'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 1)
        # Still-online session is clipped at the end of the requested range
        # (local midnight; the server runs in IST, UTC+5:30).
        self.assertEqual(response.data['results'][0]['logged_off_at'], '2026-07-02T00:00:00+05:30')

    @patch('apps.integrations.views.SureMDMClient.device_log')
    @patch('apps.integrations.views.SureMDMClient.list_devices')
    def test_active_time_no_log_events_returns_no_rows(self, list_devices, device_log):
        list_devices.return_value = [
            {
                'DeviceID': '123',
                'DeviceName': 'Front Desk Tablet',
                'SerialNumber': 'SN123',
                'Platform': 'Windows',
                'Model': 'Tab A',
            }
        ]
        device_log.return_value = []

        response = self.client.get(reverse('suremdm-active-time'), {'start_date': '2026-07-01', 'end_date': '2026-07-01'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['results'], [])
        self.assertEqual(response.data['total_active_minutes'], 0.0)

    @patch('apps.integrations.views.SureMDMClient.device_log')
    @patch('apps.integrations.views.SureMDMClient.list_devices')
    def test_active_time_includes_all_matching_devices(self, list_devices, device_log):
        list_devices.return_value = [
            {
                'DeviceID': '123',
                'DeviceName': 'Front Desk Tablet',
                'SerialNumber': 'SN123',
                'Platform': 'Windows',
                'Model': 'Tab A',
            },
            {
                'DeviceID': '456',
                'DeviceName': 'Back Office Laptop',
                'SerialNumber': 'SN456',
                'Platform': 'Windows',
                'Model': 'ThinkPad',
            },
        ]
        device_log.return_value = [
            {'Time': '2026-07-02T11:00:00.000Z', 'Message': '1'},
            {'Time': '2026-07-02T14:00:00.000Z', 'Message': '0'},
        ]

        response = self.client.get(reverse('suremdm-active-time'), {'start_date': '2026-07-02', 'end_date': '2026-07-02'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 2)
        self.assertEqual(response.data['total_active_minutes'], 360.0)
        self.assertEqual({row['device_id'] for row in response.data['results']}, {'123', '456'})

    def test_connection_response_does_not_expose_secrets(self):
        response = self.client.get(reverse('suremdm-connection'))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['has_password'])
        self.assertTrue(response.data['has_api_key'])
        self.assertNotIn('password', response.data)
        self.assertNotIn('api_key', response.data)


class TrellixIntegrationTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='it2@example.com',
            password='password',
            full_name='IT User',
            role='it_specialist',
        )
        self.client.force_authenticate(self.user)
        TrellixConnection.objects.create(
            base_url='https://api.manage.trellix.com',
            auth_url='https://iam.mcafee-cloud.com/iam/v1.1/token',
            tenant_name='Atlas Engineering And Inspection Services Private Limited',
            tenant_id='8F86C8E3-336A-4D24-85A0-62F04B4029B9',
            client_id='client',
            client_secret='secret',
            api_key='key',
        )

    @patch('apps.integrations.views.TrellixClient.list_devices')
    def test_devices_normalizes_response(self, list_devices):
        list_devices.return_value = [
            {
                'deviceId': '123',
                'deviceName': 'Finance Laptop',
                'serialNumber': 'SN123',
                'platform': 'Windows',
                'threatStatus': 'Protected',
            }
        ]

        response = self.client.get(reverse('trellix-devices'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['name'], 'Finance Laptop')
        self.assertEqual(response.data['results'][0]['threat_status'], 'Protected')

    @patch('apps.integrations.views.TrellixClient.list_threat_events')
    def test_threats_normalizes_response(self, list_threat_events):
        list_threat_events.return_value = [
            {
                'eventId': 'evt-1',
                'deviceName': 'Finance Laptop',
                'threatName': 'Trojan.GenericKD',
                'severity': 'High',
                'actionTaken': 'Quarantined',
                'detectedAt': '2026-07-01T09:00:00.000Z',
            }
        ]

        response = self.client.get(reverse('trellix-threats'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['threat_name'], 'Trojan.GenericKD')
        self.assertEqual(response.data['results'][0]['severity'], 'High')

    @patch('apps.integrations.views.TrellixClient.list_devices')
    def test_sync_assets_creates_trellix_assets(self, list_devices):
        list_devices.return_value = [
            {
                'deviceId': '123',
                'deviceName': 'Finance Laptop',
                'serialNumber': 'SN123',
                'platform': 'Windows',
            }
        ]

        response = self.client.post(reverse('trellix-sync-assets'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['created'], 1)
        self.assertTrue(Asset.objects.filter(asset_id='TRELLIX-123').exists())

    def test_connection_response_does_not_expose_secrets(self):
        response = self.client.get(reverse('trellix-connection'))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['has_client_secret'])
        self.assertTrue(response.data['has_api_key'])
        self.assertNotIn('client_secret', response.data)
        self.assertNotIn('api_key', response.data)

    def test_missing_credentials_returns_400(self):
        TrellixConnection.objects.update(client_secret='', api_key='')

        response = self.client.get(reverse('trellix-devices'))

        self.assertEqual(response.status_code, 400)
