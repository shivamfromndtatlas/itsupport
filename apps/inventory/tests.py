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
