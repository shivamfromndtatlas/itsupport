from io import BytesIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from apps.integrations.models import SureMDMConnection
from apps.integrations.suremdm import SureMDMClient

from .models import AssetType, InstalledApplication, InstalledAppReportImport
from .views import ASSET_TEMPLATE_BASE_HEADERS, AUTO_SYNC_FILE_NAME_PREFIX, build_xlsx_workbook, parse_asset_bulk_upload


class SyncInstalledAppsCommandTests(TestCase):
    def test_skips_when_suremdm_not_configured(self):
        call_command('sync_installed_apps')

        self.assertEqual(InstalledAppReportImport.objects.count(), 0)

    @patch.object(SureMDMClient, 'trigger_apps_refresh')
    @patch.object(SureMDMClient, 'list_devices')
    def test_harvests_embedded_apps_and_requests_a_refresh_for_next_run(self, list_devices, trigger_apps_refresh):
        SureMDMConnection.objects.create(
            base_url='https://suremdm.42gears.com/api',
            username='user',
            password='pass',
            api_key='key',
        )
        list_devices.return_value = [
            {
                'DeviceID': '123',
                'DeviceName': 'Front Desk Laptop',
                'ApplicationDetails': [
                    {'ApplicationName': 'Google Chrome', 'Version': '120.0', 'Publisher': 'Google LLC'},
                ],
            }
        ]
        trigger_apps_refresh.return_value = True

        call_command('sync_installed_apps')

        report_import = InstalledAppReportImport.objects.get()
        self.assertTrue(report_import.file_name.startswith(AUTO_SYNC_FILE_NAME_PREFIX))
        self.assertEqual(report_import.app_count, 1)
        installed_app = InstalledApplication.objects.get()
        self.assertEqual(installed_app.application_name, 'Google Chrome')
        self.assertEqual(installed_app.application_version, '120.0')
        self.assertEqual(installed_app.device_name, 'Front Desk Laptop')
        trigger_apps_refresh.assert_any_call('123')


class AssetBulkUploadParserTests(TestCase):
    def test_reads_asset_upload_sheet_when_instructions_sheet_is_first(self):
        AssetType.objects.create(name='Laptop', asset_type='hardware')
        workbook = build_xlsx_workbook([
            ('Instructions', [['Bulk Asset Upload Template'], ['Fill the Asset Upload sheet.']]),
            ('Asset Upload', [
                ASSET_TEMPLATE_BASE_HEADERS,
                ['Laptop', 'LAP-001', 'SN-001', 'Dell', '', '', '', 'available', 'Ready to issue'],
            ]),
        ])

        rows = parse_asset_bulk_upload(BytesIO(workbook))

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['asset_type'], 'Laptop')
        self.assertEqual(rows[0]['asset_id'], 'LAP-001')

    def test_normalizes_friendly_upload_status_from_availability_status(self):
        AssetType.objects.create(name='Bagpack', asset_type='hardware')
        workbook = build_xlsx_workbook([
            ('Asset Upload', [
                ASSET_TEMPLATE_BASE_HEADERS + ['Availability Status'],
                ['Bagpack', 'BAG-001', 'BAG-001', 'Dell', '', '', '', 'good', '', 'In Stock'],
            ]),
        ])

        rows = parse_asset_bulk_upload(BytesIO(workbook))

        self.assertEqual(rows[0]['status'], 'available')
        self.assertEqual(rows[0]['attribute_values']['Availability Status'], 'In Stock')


class VendorSupportTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient

        self.client = APIClient()
        User = get_user_model()
        self.user = User.objects.create_user(
            email='it@example.com',
            password='pass1234',
            full_name='IT User',
            role='super_admin',
        )
        self.client.force_authenticate(user=self.user)
        self.laptop_type = AssetType.objects.create(name='Laptop', asset_type='hardware')
        self.monitor_type = AssetType.objects.create(name='Monitor', asset_type='hardware')
        self.headset_type = AssetType.objects.create(name='Headset', asset_type='hardware')

    def _asset(self, asset_type, **kwargs):
        from .models import Asset

        defaults = {'asset_id': kwargs.pop('asset_id', 'AST-1'), 'asset_type': asset_type}
        defaults.update(kwargs)
        return Asset.objects.create(**defaults)

    def test_supported_asset_types(self):
        from .vendor_support import asset_supports_vendor_lookup

        self.assertTrue(asset_supports_vendor_lookup(self._asset(self.laptop_type, asset_id='L1')))
        self.assertTrue(asset_supports_vendor_lookup(self._asset(self.monitor_type, asset_id='M1')))
        self.assertFalse(asset_supports_vendor_lookup(self._asset(self.headset_type, asset_id='H1')))

    def test_detect_manufacturer_and_service_tag(self):
        from .vendor_support import detect_manufacturer, resolve_service_tag

        dell = self._asset(self.laptop_type, asset_id='2PMFGL3', vendor='Dell Inc.', serial_number='2PMFGL3')
        self.assertEqual(detect_manufacturer(dell), 'dell')
        self.assertEqual(resolve_service_tag(dell, manufacturer='dell'), '2PMFGL3')

        lenovo = self._asset(
            self.laptop_type, asset_id='LN-1', serial_number='PF3ABCDE',
            attribute_values={'Brand': 'Lenovo'},
        )
        self.assertEqual(detect_manufacturer(lenovo), 'lenovo')
        self.assertEqual(resolve_service_tag(lenovo, manufacturer='lenovo'), 'PF3ABCDE')

    def test_refresh_records_success(self):
        from .models import AssetSupportInfo
        from .vendor_support import refresh_asset_support_info

        asset = self._asset(self.laptop_type, asset_id='2PMFGL3', vendor='Dell', serial_number='2PMFGL3')
        fake = {
            'product_name': 'Dell Latitude 3520, CTO',
            'ship_date': None,
            'warranty': {
                'plan': 'ProSupport', 'start_date': '2021-08-01', 'end_date': '2099-08-01',
                'status': 'active', 'entitlements': [
                    {'plan': 'ProSupport', 'start_date': '2021-08-01', 'end_date': '2099-08-01'},
                ],
            },
            'product_specifications': [{'code': '379-BEJJ', 'description': '11th Gen Intel Core i5-1135G7'}],
            'source_url': 'https://www.dell.com/support/home/en-us/product-support/servicetag/2PMFGL3/overview',
            'raw': {'ok': True},
        }
        with patch('apps.inventory.vendor_support.fetch_dell_support', return_value=fake) as fetcher:
            info = refresh_asset_support_info(asset)

        fetcher.assert_called_once_with('2PMFGL3')
        self.assertEqual(info.fetch_status, 'success')
        self.assertEqual(info.manufacturer, 'dell')
        self.assertEqual(info.warranty['plan'], 'ProSupport')
        self.assertEqual(info.product_specifications[0]['code'], '379-BEJJ')
        self.assertEqual(AssetSupportInfo.objects.count(), 1)

    def test_refresh_records_scrape_failure_without_raising(self):
        from .vendor_support import VendorSupportError, refresh_asset_support_info

        asset = self._asset(self.laptop_type, asset_id='2PMFGL3', vendor='Dell', serial_number='2PMFGL3')
        with patch('apps.inventory.vendor_support.fetch_dell_support', side_effect=VendorSupportError('blocked', status_code=403)):
            info = refresh_asset_support_info(asset)

        self.assertEqual(info.fetch_status, 'error')
        self.assertIn('blocked', info.fetch_error)

    def test_refresh_marks_unsupported_asset_type(self):
        from .vendor_support import refresh_asset_support_info

        asset = self._asset(self.headset_type, asset_id='H1', vendor='Dell')
        info = refresh_asset_support_info(asset)
        self.assertEqual(info.fetch_status, 'unsupported')

    def test_device_dashboard_includes_support_info(self):
        asset = self._asset(self.laptop_type, asset_id='2PMFGL3', vendor='Dell', serial_number='2PMFGL3')
        res = self.client.get(f'/api/inventory/assets/{asset.id}/device-dashboard/')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['support_info']['supported'])
        self.assertEqual(res.data['support_info']['fetch_status'], 'pending')

    def test_device_dashboard_support_info_not_supported_for_headset(self):
        asset = self._asset(self.headset_type, asset_id='H1')
        res = self.client.get(f'/api/inventory/assets/{asset.id}/device-dashboard/')
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.data['support_info']['supported'])

    def test_refresh_endpoint_rejects_unsupported_asset(self):
        asset = self._asset(self.headset_type, asset_id='H1')
        res = self.client.post(f'/api/inventory/assets/{asset.id}/refresh-support-info/')
        self.assertEqual(res.status_code, 400)

    def test_refresh_endpoint_returns_cached_row(self):
        asset = self._asset(self.laptop_type, asset_id='2PMFGL3', vendor='Dell', serial_number='2PMFGL3')
        fake = {
            'product_name': '', 'ship_date': None,
            'warranty': {'plan': 'Basic', 'start_date': '', 'end_date': '2030-01-01', 'status': 'active', 'entitlements': []},
            'product_specifications': [], 'source_url': '', 'raw': {},
        }
        with patch('apps.inventory.vendor_support.fetch_dell_support', return_value=fake):
            res = self.client.post(f'/api/inventory/assets/{asset.id}/refresh-support-info/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['warranty']['plan'], 'Basic')


class DellTechDirectFetchTests(TestCase):
    def _asset(self):
        from .models import Asset

        laptop = AssetType.objects.create(name='Laptop', asset_type='hardware')
        return Asset.objects.create(asset_id='2PMFGL3', asset_type=laptop, vendor='Dell', serial_number='2PMFGL3')

    def test_errors_helpfully_when_dell_not_configured(self):
        from .vendor_support import VendorSupportError, fetch_dell_support

        with self.assertRaises(VendorSupportError) as ctx:
            fetch_dell_support('2PMFGL3')
        self.assertIn('TechDirect', str(ctx.exception))

    def test_normalizes_entitlements_and_components(self):
        from apps.integrations.models import DellSupportConnection
        from .vendor_support import fetch_dell_support

        DellSupportConnection.objects.create(
            base_url='https://apigtwb2c.us.dell.com',
            client_id='cid',
            client_secret='secret',
        )

        class FakeClient:
            def asset_entitlements(self, tags):
                return [{
                    'serviceTag': '2PMFGL3',
                    'productLineDescription': 'LATITUDE 3520',
                    'shipDate': '2021-08-27T00:00:00Z',
                    'entitlements': [
                        {'serviceLevelDescription': 'Next Business Day Onsite',
                         'startDate': '2021-08-27T00:00:00Z', 'endDate': '2024-08-27T00:00:00Z',
                         'entitlementType': 'INITIAL'},
                        {'serviceLevelDescription': 'ProSupport',
                         'startDate': '2021-08-27T00:00:00Z', 'endDate': '2026-08-27T00:00:00Z',
                         'entitlementType': 'EXTENDED'},
                    ],
                }]

            def asset_components(self, tag):
                # Each SKU (itemNumber) repeats once per underlying manufacturing
                # part (partNumber), all sharing the same itemDescription - the
                # real shape returned by Dell's asset-components endpoint.
                return {'systemDescription': 'Latitude 3520', 'components': [
                    {'itemNumber': '379-BEJJ', 'partNumber': 'ABC12', 'itemDescription': '11th Gen Intel Core i5-1135G7'},
                    {'itemNumber': '379-BEJJ', 'partNumber': 'DEF34', 'itemDescription': '11th Gen Intel Core i5-1135G7'},
                    {'itemNumber': '400-BILG', 'partNumber': 'GHI56', 'itemDescription': 'M.2 512GB PCIe NVMe SSD'},
                ]}

        with patch('apps.integrations.views.get_dell_client', return_value=FakeClient()):
            result = fetch_dell_support('2pmfgl3')

        self.assertEqual(result['product_name'], 'LATITUDE 3520')
        self.assertEqual(result['warranty']['plan'], 'ProSupport')
        self.assertEqual(result['warranty']['end_date'], '2026-08-27')
        self.assertEqual(result['warranty']['start_date'], '2021-08-27')
        self.assertEqual(len(result['warranty']['entitlements']), 2)
        # Deduplicated by itemNumber (2 rows in, 1 for 379-BEJJ), sorted
        # descending by code so 400-BILG (SSD) leads 379-BEJJ (CPU).
        self.assertEqual(len(result['product_specifications']), 2)
        self.assertEqual(result['product_specifications'][0]['code'], '400-BILG')
        self.assertEqual(result['product_specifications'][1]['code'], '379-BEJJ')
        self.assertEqual(str(result['ship_date']), '2021-08-27')

    def test_components_unavailable_is_not_fatal(self):
        from apps.integrations.models import DellSupportConnection
        from apps.integrations.dell import DellComponentsUnavailable
        from .vendor_support import fetch_dell_support

        DellSupportConnection.objects.create(
            base_url='https://apigtwb2c.us.dell.com', client_id='cid', client_secret='secret',
        )

        class FakeClient:
            def asset_entitlements(self, tags):
                return [{'serviceTag': '2PMFGL3', 'productLineDescription': 'LATITUDE 3520',
                         'entitlements': [{'serviceLevelDescription': 'Basic',
                                           'startDate': '2021-01-01', 'endDate': '2022-01-01'}]}]

            def asset_components(self, tag):
                raise DellComponentsUnavailable('not entitled', status_code=403)

        with patch('apps.integrations.views.get_dell_client', return_value=FakeClient()):
            result = fetch_dell_support('2PMFGL3')

        self.assertEqual(result['warranty']['plan'], 'Basic')
        self.assertEqual(result['product_specifications'], [])
        self.assertIn('not entitled', result['raw']['components_note'])
