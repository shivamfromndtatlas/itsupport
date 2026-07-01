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

    def test_connection_response_does_not_expose_secrets(self):
        response = self.client.get(reverse('suremdm-connection'))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['has_password'])
        self.assertTrue(response.data['has_api_key'])
        self.assertNotIn('password', response.data)
        self.assertNotIn('api_key', response.data)
