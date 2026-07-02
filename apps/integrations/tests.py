from unittest.mock import patch

from django.utils import timezone
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.inventory.models import Asset
from apps.users.models import User

from .models import SureMDMConnection


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

    @patch('apps.integrations.views.SureMDMClient.list_devices')
    def test_active_time_summary_uses_duration_fields(self, list_devices):
        list_devices.return_value = [
            {
                'DeviceID': '123',
                'DeviceName': 'Front Desk Tablet',
                'SerialNumber': 'SN123',
                'Platform': 'Android',
                'Model': 'Tab A',
                'ActiveTime': '2h 15m',
                'LastTimeStamp': '2026-07-01 09:00:00',
            },
            {
                'DeviceID': '456',
                'DeviceName': 'Back Office Laptop',
                'SerialNumber': 'SN456',
                'Platform': 'Windows',
                'Model': 'ThinkPad',
                'UsageTime': 90,
                'LastTimeStamp': '2026-07-01 10:00:00',
            },
        ]

        response = self.client.get(reverse('suremdm-active-time'), {'start_date': '2026-07-01', 'end_date': '2026-07-01'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['total_devices'], 1)
        self.assertEqual(response.data['results'][0]['date'], '2026-07-01')
        self.assertEqual(response.data['results'][0]['name'], 'Front Desk Tablet')
        self.assertEqual(response.data['results'][0]['active_minutes'], 135.0)

    @patch('apps.integrations.views.SureMDMClient.list_devices')
    def test_active_time_uses_interval_events_when_available(self, list_devices):
        list_devices.return_value = [
            {
                'DeviceID': '123',
                'DeviceName': 'Front Desk Tablet',
                'SerialNumber': 'SN123',
                'Platform': 'Windows',
                'Model': 'Tab A',
                'raw': {
                    'activity_events': [
                        {'start_time': '2026-07-01 11:00:00', 'end_time': '2026-07-01 14:00:00'},
                        {'start_time': '2026-07-01 15:00:00', 'end_time': '2026-07-01 20:00:00'},
                    ]
                },
            }
        ]

        response = self.client.get(reverse('suremdm-active-time'), {'start_date': '2026-07-01', 'end_date': '2026-07-01'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['total_devices'], 2)
        self.assertEqual(len(response.data['results']), 2)
        self.assertEqual(response.data['results'][0]['active_minutes'], 180.0)
        self.assertEqual(response.data['results'][1]['active_minutes'], 300.0)

    @patch('apps.integrations.views.SureMDMClient.list_devices')
    def test_active_time_uses_start_time_with_duration_hint(self, list_devices):
        list_devices.return_value = [
            {
                'DeviceID': '123',
                'DeviceName': 'Front Desk Tablet',
                'SerialNumber': 'SN123',
                'Platform': 'Windows',
                'Model': 'Tab A',
                'raw': {
                    'sessions': [
                        {'StartTime': '2026-07-01 11:00:00', 'Duration': '180m'},
                    ]
                },
            }
        ]

        response = self.client.get(reverse('suremdm-active-time'), {'start_date': '2026-07-01', 'end_date': '2026-07-01'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['total_devices'], 1)
        self.assertTrue(response.data['results'][0]['active_from'])
        self.assertTrue(response.data['results'][0]['logged_off_at'])
        self.assertEqual(response.data['results'][0]['active_minutes'], 180.0)

    @patch('apps.integrations.views.SureMDMClient.list_devices')
    def test_active_time_uses_end_time_with_duration_hint(self, list_devices):
        list_devices.return_value = [
            {
                'DeviceID': '123',
                'DeviceName': 'Front Desk Tablet',
                'SerialNumber': 'SN123',
                'Platform': 'Windows',
                'Model': 'Tab A',
                'raw': {
                    'sessions': [
                        {'end_time': '2026-07-01 14:00:00', 'Duration': '180m'},
                    ]
                },
            }
        ]

        response = self.client.get(reverse('suremdm-active-time'), {'start_date': '2026-07-01', 'end_date': '2026-07-01'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['total_devices'], 1)
        self.assertTrue(response.data['results'][0]['active_from'])
        self.assertTrue(response.data['results'][0]['logged_off_at'])
        self.assertEqual(response.data['results'][0]['active_minutes'], 180.0)

    @patch('apps.integrations.views.SureMDMClient.list_devices')
    def test_active_time_does_not_duplicate_start_when_duration_missing(self, list_devices):
        list_devices.return_value = [
            {
                'DeviceID': '123',
                'DeviceName': 'Front Desk Tablet',
                'SerialNumber': 'SN123',
                'Platform': 'Windows',
                'Model': 'Tab A',
                'LastTimeStamp': '2026-07-01 14:00:00',
            }
        ]

        response = self.client.get(reverse('suremdm-active-time'), {'start_date': '2026-07-01', 'end_date': '2026-07-01'})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['results'][0]['active_from'])
        self.assertTrue(response.data['results'][0]['logged_off_at'])
        self.assertEqual(response.data['results'][0]['date'], '2026-07-01')

    @patch('apps.integrations.views.SureMDMClient.list_devices')
    def test_active_time_fallback_returns_each_requested_day(self, list_devices):
        list_devices.return_value = [
            {
                'DeviceID': '123',
                'DeviceName': 'Front Desk Tablet',
                'SerialNumber': 'SN123',
                'Platform': 'Windows',
                'Model': 'Tab A',
                'UsageTime': 120,
                'LastTimeStamp': '2026-07-02 14:00:00',
            }
        ]

        response = self.client.get(reverse('suremdm-active-time'), {'start_date': '2026-07-01', 'end_date': '2026-07-03'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['total_devices'], 3)
        self.assertEqual(len(response.data['results']), 3)
        self.assertEqual([row['date'] for row in response.data['results']], ['2026-07-01', '2026-07-02', '2026-07-03'])
        self.assertEqual(response.data['results'][0]['active_minutes'], 0.0)
        self.assertTrue(response.data['results'][0]['logged_off_at'])
        self.assertEqual(response.data['results'][1]['active_minutes'], 120.0)
        self.assertTrue(response.data['results'][1]['active_from'])
        self.assertTrue(response.data['results'][1]['logged_off_at'])
        self.assertNotEqual(response.data['results'][1]['active_from'], response.data['results'][1]['logged_off_at'])
        self.assertEqual(response.data['results'][2]['active_minutes'], 0.0)

    @patch('apps.integrations.views.SureMDMClient.list_devices')
    def test_active_time_includes_all_matching_devices(self, list_devices):
        list_devices.return_value = [
            {
                'DeviceID': '123',
                'DeviceName': 'Front Desk Tablet',
                'SerialNumber': 'SN123',
                'Platform': 'Windows',
                'Model': 'Tab A',
                'UsageTime': 120,
                'LastTimeStamp': '2026-07-02 10:00:00',
            },
            {
                'DeviceID': '456',
                'DeviceName': 'Back Office Laptop',
                'SerialNumber': 'SN456',
                'Platform': 'Windows',
                'Model': 'ThinkPad',
                'raw': {
                    'events': [
                        {'status': 'online', 'EventTime': '2026-07-02 11:00:00'},
                        {'status': 'offline', 'EventTime': '2026-07-02 14:00:00'},
                    ]
                },
            },
        ]

        response = self.client.get(reverse('suremdm-active-time'), {'start_date': '2026-07-02', 'end_date': '2026-07-02'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['total_devices'], 2)
        self.assertEqual(len(response.data['results']), 2)
        self.assertEqual(response.data['total_active_minutes'], 300.0)
        self.assertEqual({row['device_id'] for row in response.data['results']}, {'123', '456'})

    @patch('apps.integrations.views.SureMDMClient.list_devices')
    def test_active_time_pairs_online_offline_events(self, list_devices):
        list_devices.return_value = [
            {
                'DeviceID': '123',
                'DeviceName': 'Front Desk Tablet',
                'SerialNumber': 'SN123',
                'Platform': 'Windows',
                'Model': 'Tab A',
                'raw': {
                    'events': [
                        {'status': 'online', 'EventTime': '2026-07-01 11:00:00'},
                        {'status': 'offline', 'EventTime': '2026-07-01 14:00:00'},
                    ]
                },
            }
        ]

        response = self.client.get(reverse('suremdm-active-time'), {'start_date': '2026-07-01', 'end_date': '2026-07-01'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['total_devices'], 1)
        self.assertTrue(response.data['results'][0]['active_from'])
        self.assertTrue(response.data['results'][0]['logged_off_at'])
        self.assertEqual(response.data['results'][0]['active_minutes'], 180.0)

    @patch('apps.integrations.views.SureMDMClient.list_devices')
    def test_active_time_parses_indian_style_timestamp_strings(self, list_devices):
        list_devices.return_value = [
            {
                'DeviceID': '123',
                'DeviceName': 'Front Desk Tablet',
                'SerialNumber': 'SN123',
                'Platform': 'Windows',
                'Model': 'Tab A',
                'raw': {
                    'events': [
                        {'status': 'online', 'EventTime': '02/07/2026, 11:00:00 AM'},
                        {'status': 'offline', 'EventTime': '02/07/2026, 02:00:00 PM'},
                    ]
                },
            }
        ]

        response = self.client.get(reverse('suremdm-active-time'), {'start_date': '2026-07-02', 'end_date': '2026-07-02'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['total_devices'], 1)
        self.assertTrue(response.data['results'][0]['active_from'])
        self.assertTrue(response.data['results'][0]['logged_off_at'])
        self.assertEqual(response.data['results'][0]['active_minutes'], 180.0)

    def test_connection_response_does_not_expose_secrets(self):
        response = self.client.get(reverse('suremdm-connection'))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['has_password'])
        self.assertTrue(response.data['has_api_key'])
        self.assertNotIn('password', response.data)
        self.assertNotIn('api_key', response.data)
