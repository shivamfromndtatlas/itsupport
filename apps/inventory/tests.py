from io import BytesIO

from django.test import TestCase

from .models import AssetType
from .views import ASSET_TEMPLATE_BASE_HEADERS, build_xlsx_workbook, parse_asset_bulk_upload


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
