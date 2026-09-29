from datetime import datetime, timezone as dt_timezone
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from django.utils import timezone
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.inventory.models import Asset
from apps.users.models import User

from .models import SureMDMConnection, SynthesiaConnection, SynthesiaInvoice, TrellixConnection
from .trellix import TrellixClient
from .suremdm import SureMDMClient
from .synthesia import SynthesiaClient


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

    @patch.object(SureMDMClient, 'get')
    def test_location_history_client_flattens_nested_payload(self, get):
        get.return_value = (200, {
            'status': True,
            'data': [
                {
                    'DeviceId': '123',
                    'Location': [
                        {'Latitude': 1.0, 'Longitude': 2.0, 'Time': '2026-07-01T09:00:00Z'},
                        {'Latitude': 1.1, 'Longitude': 2.1, 'Time': '2026-07-01T09:05:00Z'},
                    ],
                }
            ],
        })
        client = SureMDMClient(
            base_url='https://suremdm.42gears.com/api', username='u', password='p', api_key='k'
        )

        points = client.location_history('123', '2026-07-01T00:00:00', '2026-07-02T00:00:00')

        self.assertEqual(len(points), 2)
        self.assertEqual(points[0]['DeviceId'], '123')
        get.assert_called_once_with(
            'v2/location',
            {'DeviceID': '123', 'FromTime': '2026-07-01T00:00:00', 'ToTime': '2026-07-02T00:00:00'},
        )

    @patch('apps.integrations.views.SureMDMClient.last_location')
    @patch('apps.integrations.views.SureMDMClient.list_devices')
    def test_locations_returns_last_known_position_per_device(self, list_devices, last_location):
        list_devices.return_value = [
            {
                'DeviceID': '123',
                'DeviceName': 'Front Desk Tablet',
                'SerialNumber': 'SN123',
                'Platform': 'Android',
                'Model': 'Tab A',
            }
        ]
        last_location.return_value = [
            {
                'DeviceId': '123',
                'Latitude': 14.4277771,
                'Longitude': 77.7381445,
                'Time': '2026-07-01T09:00:00Z',
                'LocationName': 'MG Road, Bengaluru',
                'LocationAccuracy': 12,
                'Speed': -1.0,
            }
        ]

        response = self.client.get(reverse('suremdm-locations'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['located_count'], 1)
        row = response.data['results'][0]
        self.assertEqual(row['latitude'], 14.4277771)
        self.assertEqual(row['longitude'], 77.7381445)
        self.assertEqual(row['address'], 'MG Road, Bengaluru')
        self.assertEqual(row['accuracy_m'], 12.0)
        self.assertIsNone(row['speed_mps'])
        self.assertTrue(row['has_location'])
        self.assertIn('14.4277771,77.7381445', row['map_url'])

    @patch('apps.integrations.views.SureMDMClient.last_location')
    @patch('apps.integrations.views.SureMDMClient.list_devices')
    def test_locations_marks_devices_without_a_fix(self, list_devices, last_location):
        list_devices.return_value = [
            {'DeviceID': '123', 'DeviceName': 'No GPS Laptop', 'SerialNumber': 'SN123', 'Platform': 'Windows'}
        ]
        last_location.return_value = []

        response = self.client.get(reverse('suremdm-locations'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['located_count'], 0)
        self.assertFalse(response.data['results'][0]['has_location'])
        self.assertEqual(response.data['results'][0]['map_url'], '')

    @patch('apps.integrations.views.ReverseGeocoder')
    @patch('apps.integrations.views.SureMDMClient.last_location')
    @patch('apps.integrations.views.SureMDMClient.list_devices')
    def test_locations_geocodes_address_when_suremdm_has_none(self, list_devices, last_location, geocoder_cls):
        list_devices.return_value = [
            {'DeviceID': '123', 'DeviceName': 'Field Laptop', 'SerialNumber': 'SN123', 'Platform': 'Windows'}
        ]
        last_location.return_value = [
            {
                'DeviceId': '123',
                'Latitude': 28.6139,
                'Longitude': 77.2090,
                'Time': '2026-07-01T09:00:00Z',
                'LocationName': 'Unable to fetch the address.',
                'LocationMode': 1,
                'LocationAccuracy': 8,
            }
        ]
        geocoder_cls.return_value.resolve.return_value = 'Connaught Place, New Delhi, India'

        response = self.client.get(reverse('suremdm-locations'))

        self.assertEqual(response.status_code, 200)
        row = response.data['results'][0]
        self.assertEqual(row['address'], 'Connaught Place, New Delhi, India')
        self.assertEqual(row['address_source'], 'geocoded')
        self.assertEqual(row['location_mode'], 'GPS')
        self.assertEqual(row['accuracy_m'], 8.0)
        self.assertEqual(response.data['geocoded_count'], 1)

    @patch('apps.integrations.views.SureMDMClient.location_history')
    @patch('apps.integrations.views.SureMDMClient.list_devices')
    def test_location_history_returns_sorted_breadcrumb_rows(self, list_devices, location_history):
        list_devices.return_value = [
            {
                'DeviceID': '123',
                'DeviceName': 'Front Desk Tablet',
                'SerialNumber': 'SN123',
                'Platform': 'Windows',
                'Model': 'Tab A',
            }
        ]
        location_history.return_value = [
            {'DeviceId': '123', 'Latitude': 12.90, 'Longitude': 77.60, 'Time': '2026-07-01T09:00:00Z', 'LocationName': 'HSR Layout'},
            {'DeviceId': '123', 'Latitude': 12.95, 'Longitude': 77.62, 'Time': '2026-07-01T10:00:00Z', 'LocationName': 'Koramangala'},
        ]

        response = self.client.get(
            reverse('suremdm-location-history'), {'start_date': '2026-07-01', 'end_date': '2026-07-01'}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['total_points'], 2)
        self.assertEqual(response.data['total_devices'], 1)
        # Newest point first.
        self.assertEqual(response.data['results'][0]['recorded_at'], '2026-07-01T10:00:00+00:00')
        self.assertEqual(response.data['results'][0]['address'], 'Koramangala')
        self.assertEqual(response.data['results'][0]['date'], '2026-07-01')

    @patch('apps.integrations.views.SureMDMClient.location_history')
    @patch('apps.integrations.views.SureMDMClient.list_devices')
    def test_location_history_drops_points_outside_the_window(self, list_devices, location_history):
        list_devices.return_value = [
            {'DeviceID': '123', 'DeviceName': 'Front Desk Tablet', 'SerialNumber': 'SN123', 'Platform': 'Windows'}
        ]
        location_history.return_value = [
            {'DeviceId': '123', 'Latitude': 12.90, 'Longitude': 77.60, 'Time': '2026-07-01T09:00:00Z', 'LocationName': 'In range'},
            {'DeviceId': '123', 'Latitude': 12.95, 'Longitude': 77.62, 'Time': '2026-07-05T10:00:00Z', 'LocationName': 'Out of range'},
        ]

        response = self.client.get(
            reverse('suremdm-location-history'), {'start_date': '2026-07-01', 'end_date': '2026-07-01'}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['total_points'], 1)
        self.assertEqual(response.data['results'][0]['address'], 'In range')

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
            auth_url='https://iam.cloud.trellix.com/iam/v1.0/token',
            tenant_name='Atlas Engineering And Inspection Services Private Limited',
            tenant_id='8F86C8E3-336A-4D24-85A0-62F04B4029B9',
            client_id='client',
            client_secret='secret',
            api_key='key',
        )

    @patch('apps.integrations.views.TrellixClient.list_devices')
    def test_devices_normalizes_response(self, list_devices):
        # Shape confirmed against a real /epo/v2/devices response.
        list_devices.return_value = [
            {
                'id': '123',
                'name': 'Finance Laptop',
                'systemSerialNumber': 'SN123',
                'osType': 'Windows 11',
                'managed': '1',
            }
        ]

        response = self.client.get(reverse('trellix-devices'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['name'], 'Finance Laptop')
        self.assertEqual(response.data['results'][0]['serial_number'], 'SN123')
        self.assertEqual(response.data['results'][0]['managed_status'], 'Managed')

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
                'id': '123',
                'name': 'Finance Laptop',
                'systemSerialNumber': 'SN123',
                'osType': 'Windows 11',
                'managed': '1',
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


class TrellixClientPaginationTests(SimpleTestCase):
    def _client(self):
        return TrellixClient(
            base_url='https://api.manage.trellix.com',
            auth_url='https://iam.cloud.trellix.com/iam/v1.0/token',
            client_id='client',
            client_secret='secret',
            api_key='key',
        )

    @patch('apps.integrations.trellix.TrellixClient.get')
    def test_paginate_offset_follows_meta_total_across_pages(self, mock_get):
        page_one = {
            'data': [{'id': str(i), 'attributes': {}} for i in range(200)],
            'meta': {'totalResourceCount': 250},
        }
        page_two = {
            'data': [{'id': str(i), 'attributes': {}} for i in range(200, 250)],
            'meta': {'totalResourceCount': 250},
        }
        mock_get.side_effect = [(200, page_one), (200, page_two)]

        results = self._client()._paginate_offset('epo/v2/devices', limit=1000, page_size=200)

        self.assertEqual(len(results), 250)
        self.assertEqual(mock_get.call_count, 2)

    @patch('apps.integrations.trellix.TrellixClient.get')
    def test_paginate_offset_stops_at_caller_limit(self, mock_get):
        mock_get.return_value = (
            200,
            {
                'data': [{'id': str(i), 'attributes': {}} for i in range(200)],
                'meta': {'totalResourceCount': 500},
            },
        )

        results = self._client()._paginate_offset('epo/v2/devices', limit=50, page_size=200)

        self.assertEqual(len(results), 50)
        self.assertEqual(mock_get.call_count, 1)

    @patch('apps.integrations.trellix.TrellixClient.get')
    def test_paginate_cursor_follows_next_link_until_exhausted(self, mock_get):
        mock_get.side_effect = [
            (200, {'data': [{'id': '1', 'attributes': {}}], 'links': {'next': '/epo/v2/events?page[limit]=1&page[cursor]=abc'}}),
            (200, {'data': [{'id': '2', 'attributes': {}}], 'links': {}}),
        ]

        results = self._client()._paginate_cursor('epo/v2/events', limit=10, page_size=1)

        self.assertEqual(len(results), 2)
        self.assertEqual(mock_get.call_count, 2)

    @patch('apps.integrations.trellix.TrellixClient.get')
    def test_paginate_cursor_stops_at_caller_limit(self, mock_get):
        mock_get.side_effect = [
            (200, {'data': [{'id': '1', 'attributes': {}}], 'links': {'next': '/epo/v2/events?page[limit]=1&page[cursor]=abc'}}),
            (200, {'data': [{'id': '2', 'attributes': {}}], 'links': {'next': '/epo/v2/events?page[limit]=1&page[cursor]=def'}}),
        ]

        results = self._client()._paginate_cursor('epo/v2/events', limit=1, page_size=1)

        self.assertEqual(len(results), 1)
        self.assertEqual(mock_get.call_count, 1)


class SynthesiaCreditSyncTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='it3@example.com',
            password='password',
            full_name='IT User',
            role='it_specialist',
        )
        self.client.force_authenticate(self.user)
        self.connection = SynthesiaConnection.objects.create(
            base_url='https://api.synthesia.io/v2',
            api_key='key',
        )
        # A logged invoice anchors the current billing cycle's start.
        SynthesiaInvoice.objects.create(
            connection=self.connection,
            payment_date='2026-08-01',
            amount='240.00',
            currency='USD',
            invoice_file=SimpleUploadedFile('invoice.pdf', b'%PDF-1.4 test', content_type='application/pdf'),
        )

    @staticmethod
    def _epoch(year, month, day):
        return int(datetime(year, month, day, tzinfo=dt_timezone.utc).timestamp())

    @patch.object(SynthesiaClient, 'list_all_videos')
    def test_sync_credits_estimates_from_videos_in_current_cycle(self, list_all_videos):
        list_all_videos.return_value = [
            # 60s of finished video this cycle -> 120 credits at 2 credits/sec.
            {'id': 'v1', 'title': 'In cycle', 'status': 'complete', 'duration': 60,
             'createdAt': self._epoch(2026, 8, 10), 'lastUpdatedAt': self._epoch(2026, 8, 10)},
            # Created before the cycle start -> excluded from the estimate.
            {'id': 'v2', 'title': 'Old', 'status': 'complete', 'duration': 300,
             'createdAt': self._epoch(2026, 7, 1), 'lastUpdatedAt': self._epoch(2026, 7, 1)},
        ]

        response = self.client.post(reverse('synthesia-sync-credits'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['credits_used_estimated'], 120)
        self.assertTrue(response.data['has_invoice_anchor'])
        self.connection.refresh_from_db()
        self.assertEqual(self.connection.credits_used_estimated, 120)
        self.assertIsNotNone(self.connection.credits_used_synced_at)

    @patch.object(SynthesiaClient, 'list_all_videos')
    def test_summary_uses_manual_override_over_estimate(self, list_all_videos):
        list_all_videos.return_value = [
            {'id': 'v1', 'title': 'In cycle', 'status': 'complete', 'duration': 60,
             'createdAt': self._epoch(2026, 8, 10), 'lastUpdatedAt': self._epoch(2026, 8, 10)},
        ]
        SynthesiaConnection.objects.filter(pk=self.connection.pk).update(
            credits_used_override=5000, credit_allowance=44000
        )

        response = self.client.get(reverse('synthesia-summary'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['credits_used_this_cycle'], 5000)
        self.assertFalse(response.data['credits_used_is_estimate'])
        # The auto estimate is still computed and surfaced alongside it.
        self.assertEqual(response.data['estimated_credits_used_this_cycle'], 120)
        self.assertEqual(response.data['credits_remaining'], 39000)

    @patch.object(SynthesiaClient, 'list_all_videos')
    def test_sync_credits_without_invoice_leaves_estimate_unset(self, list_all_videos):
        SynthesiaInvoice.objects.filter(connection=self.connection).delete()
        list_all_videos.return_value = [
            {'id': 'v1', 'title': 'In cycle', 'status': 'complete', 'duration': 60,
             'createdAt': self._epoch(2026, 8, 10), 'lastUpdatedAt': self._epoch(2026, 8, 10)},
        ]

        response = self.client.post(reverse('synthesia-sync-credits'))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['has_invoice_anchor'])
        self.connection.refresh_from_db()
        self.assertIsNone(self.connection.credits_used_estimated)
        self.assertIsNone(self.connection.credits_used_synced_at)
