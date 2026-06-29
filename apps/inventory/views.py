import posixpath
import zipfile
from io import BytesIO
from xml.etree import ElementTree
from urllib.parse import quote

from django.db import models, transaction
from django.db.models import Count, Sum
from django.http import HttpResponse
from rest_framework import viewsets
from rest_framework import status as drf_status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.users.permissions import IsITOrHROrSuperAdmin, IsITSpecialistOrSuperAdmin

from .models import (
    Asset,
    AssetAttribute,
    AssetType,
    InstalledApplication,
    InstalledAppReportImport,
    SoftwareLicense,
)
from .serializers import (
    AssetAttributeSerializer,
    AssetCreateSerializer,
    AssetSerializer,
    AssetTypeSerializer,
    SoftwareLicenseSerializer,
)


APP_NAME_KEYS = ('ApplicationName', 'AppName', 'Name', 'name', 'DisplayName', 'Title')
APP_VERSION_KEYS = ('Version', 'version', 'AppVersion', 'ApplicationVersion', 'DisplayVersion')
APP_VENDOR_KEYS = ('Publisher', 'publisher', 'Vendor', 'vendor', 'Manufacturer', 'Developer')
APP_INSTALLED_ON_KEYS = ('InstallDate', 'InstalledOn', 'InstalledDate', 'install_date')
ASSET_SYSTEM_TAG_KEYS = (
    'system_tag',
    'System Tag',
    'SystemTag',
    'asset_tag',
    'Asset Tag',
    'Device Tag',
    'computer_name',
    'Computer Name',
)
XLSX_NS = {'a': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
REL_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
REPORT_HEADER_ALIASES = {
    'device_name': ('device name', 'device', 'system tag', 'systemtag', 'computer name', 'hostname'),
    'application_package': ('application package', 'package', 'package name'),
    'application_name': ('application name', 'application', 'app name', 'name'),
    'application_type': ('application type', 'type', 'status'),
    'user_name': ('username', 'user name', 'user'),
    'application_version': ('application version', 'version', 'app version'),
    'signature_key_hash': ('application signature key hash', 'signature key hash', 'hash'),
}
ASSET_TEMPLATE_BASE_HEADERS = [
    'Asset Type',
    'Asset ID',
    'Serial Number',
    'Vendor',
    'Purchase Date',
    'Purchase Cost',
    'Warranty Expiry',
    'Status',
    'Notes',
]
ASSET_UPLOAD_HEADER_ALIASES = {
    'asset_type': ('asset type', 'type'),
    'asset_id': ('asset id', 'assetid'),
    'serial_number': ('serial number', 'serialnumber', 'serial'),
    'vendor': ('vendor', 'manufacturer'),
    'purchase_date': ('purchase date', 'purchase'),
    'purchase_cost': ('purchase cost', 'cost', 'price'),
    'warranty_expiry': ('warranty expiry', 'warranty'),
    'status': ('status',),
    'notes': ('notes', 'remark', 'remarks'),
}
XLSX_MIME_TYPE = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
ASSET_STATUS_UPLOAD_ALIASES = {
    'available': 'available',
    'in stock': 'available',
    'reserved stock': 'available',
    'good': 'available',
    'new': 'available',
    'working': 'available',
    'assigned': 'assigned',
    'issued': 'assigned',
    'in use': 'assigned',
    'maintenance': 'maintenance',
    'under maintenance': 'maintenance',
    'under repair': 'maintenance',
    'repair': 'maintenance',
    'retired': 'retired',
    'discarded': 'retired',
    'scrapped': 'retired',
}


def first_value(data, *keys, default=''):
    if not isinstance(data, dict):
        return default
    for key in keys:
        value = data.get(key)
        if value not in (None, ''):
            if isinstance(value, dict):
                return value.get('text') or value.get('value') or value.get('Value') or default
            return value
    return default


def normalize_installed_app(app):
    return {
        'name': first_value(app, *APP_NAME_KEYS),
        'version': first_value(app, *APP_VERSION_KEYS),
        'vendor': first_value(app, *APP_VENDOR_KEYS),
        'installed_on': first_value(app, *APP_INSTALLED_ON_KEYS),
        'application_package': first_value(app, 'Application Package', 'ApplicationPackage', 'Package', 'PackageName'),
        'application_type': first_value(app, 'Application Type', 'ApplicationType', 'Type'),
        'user_name': first_value(app, 'UserName', 'Username', 'User Name', 'User'),
        'raw': app,
    }


def embedded_device_apps(device):
    raw = (device or {}).get('raw') or {}
    candidates = []
    if isinstance(raw, dict):
        candidates.extend([
            raw.get('ApplicationDetails'),
            raw.get('DeviceApplistDetails'),
            raw.get('InstalledApplications'),
            raw.get('Applications'),
        ])
    candidates.extend([
        (device or {}).get('ApplicationDetails'),
        (device or {}).get('DeviceApplistDetails'),
        (device or {}).get('InstalledApplications'),
        (device or {}).get('Applications'),
    ])

    for candidate in candidates:
        if isinstance(candidate, list):
            return candidate
        if isinstance(candidate, str) and candidate.strip():
            try:
                import json
                parsed = json.loads(candidate)
            except ValueError:
                continue
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict):
                for value in parsed.values():
                    if isinstance(value, list):
                        return value
    return []


def normalize_match_value(value):
    return ''.join(ch for ch in str(value or '').lower() if ch.isalnum())


def normalized_match_variants(value):
    normalized = normalize_match_value(value)
    if not normalized:
        return set()
    return {normalized, normalized.replace('o', '0'), normalized.replace('0', 'o')}


def normalize_header(value):
    return ' '.join(str(value or '').strip().lower().split())


def normalize_asset_upload_status(status_value, attribute_values=None):
    attribute_values = attribute_values or {}
    availability_status = (
        attribute_values.get('Availability Status')
        or attribute_values.get('availability status')
        or attribute_values.get('10')
    )
    for value in (availability_status, status_value):
        normalized = normalize_header(value)
        if not normalized:
            continue
        if normalized in ASSET_STATUS_UPLOAD_ALIASES:
            return ASSET_STATUS_UPLOAD_ALIASES[normalized]
    return 'available'


def xlsx_cell_ref_col(cell_ref):
    letters = ''.join(ch for ch in cell_ref if ch.isalpha())
    index = 0
    for char in letters:
        index = index * 26 + (ord(char.upper()) - ord('A') + 1)
    return index - 1


def read_xlsx_workbook(file_obj):
    workbook = zipfile.ZipFile(BytesIO(file_obj.read()))
    shared_strings = []
    if 'xl/sharedStrings.xml' in workbook.namelist():
        shared_root = ElementTree.fromstring(workbook.read('xl/sharedStrings.xml'))
        for item in shared_root.findall('a:si', XLSX_NS):
            shared_strings.append(''.join(text.text or '' for text in item.findall('.//a:t', XLSX_NS)))

    workbook_root = ElementTree.fromstring(workbook.read('xl/workbook.xml'))
    rels_root = ElementTree.fromstring(workbook.read('xl/_rels/workbook.xml.rels'))
    rel_map = {rel.attrib['Id']: rel.attrib['Target'] for rel in rels_root}
    parsed_sheets = []

    for sheet in workbook_root.findall('a:sheets/a:sheet', XLSX_NS):
        relation_id = sheet.attrib[f'{{{REL_NS}}}id']
        target = rel_map[relation_id]
        sheet_path = target.lstrip('/') if target.startswith('/xl/') else posixpath.normpath(posixpath.join('xl', target))
        sheet_root = ElementTree.fromstring(workbook.read(sheet_path))

        rows = []
        for row in sheet_root.findall('a:sheetData/a:row', XLSX_NS):
            cells = {}
            max_col = -1
            for sequential_col, cell in enumerate(row.findall('a:c', XLSX_NS)):
                col = xlsx_cell_ref_col(cell.attrib['r']) if 'r' in cell.attrib else sequential_col
                max_col = max(max_col, col)
                value_node = cell.find('a:v', XLSX_NS)
                value = '' if value_node is None else value_node.text or ''
                if cell.attrib.get('t') == 's' and value:
                    value = shared_strings[int(value)]
                elif cell.attrib.get('t') == 'inlineStr':
                    value = ''.join(text.text or '' for text in cell.findall('.//a:t', XLSX_NS))
                cells[col] = value
            if max_col >= 0:
                rows.append([cells.get(index, '') for index in range(max_col + 1)])
        parsed_sheets.append((sheet.attrib.get('name', ''), rows))

    return parsed_sheets


def read_xlsx_rows(file_obj, sheet_name=None):
    sheets = read_xlsx_workbook(file_obj)
    if sheet_name:
        normalized_sheet_name = normalize_header(sheet_name)
        for name, rows in sheets:
            if normalize_header(name) == normalized_sheet_name:
                return rows
    return sheets[0][1] if sheets else []


def xlsx_column_letter(index):
    index += 1
    letters = []
    while index:
        index, remainder = divmod(index - 1, 26)
        letters.append(chr(65 + remainder))
    return ''.join(reversed(letters))


def xlsx_cell(row_number, col_number, value):
    ref = f'{xlsx_column_letter(col_number)}{row_number}'
    text = '' if value is None else str(value)
    cell = ElementTree.Element('c', {'r': ref, 't': 'inlineStr'})
    is_node = ElementTree.SubElement(cell, 'is')
    t_node = ElementTree.SubElement(is_node, 't')
    if text.startswith(' ') or text.endswith(' '):
        t_node.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
    t_node.text = text
    return cell


def xlsx_sheet_xml(rows):
    ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    worksheet = ElementTree.Element('worksheet', {'xmlns': ns})
    sheet_data = ElementTree.SubElement(worksheet, 'sheetData')
    for row_number, row in enumerate(rows, start=1):
        row_node = ElementTree.SubElement(sheet_data, 'row', {'r': str(row_number)})
        for col_number, value in enumerate(row):
            row_node.append(xlsx_cell(row_number, col_number, value))
    return ElementTree.tostring(worksheet, encoding='utf-8', xml_declaration=True)


def build_xlsx_workbook(sheets):
    buffer = BytesIO()
    root_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>
'''
    workbook = ElementTree.Element(
        'workbook',
        {'xmlns': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main', 'xmlns:r': REL_NS},
    )
    sheets_node = ElementTree.SubElement(workbook, 'sheets')
    workbook_rels = ElementTree.Element(
        'Relationships',
        {'xmlns': 'http://schemas.openxmlformats.org/package/2006/relationships'},
    )
    sheet_overrides = ''.join(
        f'  <Override PartName="/xl/worksheets/sheet{index}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>\n'
        for index, _ in enumerate(sheets, start=1)
    )
    content_types = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
{sheet_overrides}</Types>
'''

    for index, (sheet_name, rows) in enumerate(sheets, start=1):
        ElementTree.SubElement(
            sheets_node,
            'sheet',
            {'name': sheet_name, 'sheetId': str(index), f'{{{REL_NS}}}id': f'rId{index}'},
        )
        ElementTree.SubElement(
            workbook_rels,
            'Relationship',
            {
                'Id': f'rId{index}',
                'Type': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet',
                'Target': f'worksheets/sheet{index}.xml',
            },
        )

    styles = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="1"><font><sz val="11"/><color theme="1"/><name val="Calibri"/><family val="2"/></font></fonts>
  <fills count="1"><fill><patternFill patternType="none"/></fill></fills>
  <borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs>
</styleSheet>
'''

    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml', content_types)
        archive.writestr('_rels/.rels', root_rels)
        archive.writestr('xl/workbook.xml', ElementTree.tostring(workbook, encoding='utf-8', xml_declaration=True))
        archive.writestr('xl/_rels/workbook.xml.rels', ElementTree.tostring(workbook_rels, encoding='utf-8', xml_declaration=True))
        archive.writestr('xl/styles.xml', styles)
        for index, (_, rows) in enumerate(sheets, start=1):
            archive.writestr(f'xl/worksheets/sheet{index}.xml', xlsx_sheet_xml(rows))
    buffer.seek(0)
    return buffer.getvalue()


def normalize_asset_header(value):
    return normalize_header(value).strip(' -')


def asset_template_metadata(asset_types):
    attributes = list(
        AssetAttribute.objects.prefetch_related('asset_types')
        .filter(models.Q(is_common=True) | models.Q(asset_types__in=asset_types))
        .distinct()
        .order_by('name')
    )
    relevant_attributes = [
        attr for attr in attributes if normalize_asset_header(attr.name) not in {normalize_asset_header(h) for h in ASSET_TEMPLATE_BASE_HEADERS}
    ]
    dynamic_headers = []
    seen = set()
    for attr in relevant_attributes:
        header = attr.name.strip()
        normalized = normalize_asset_header(header)
        if normalized in seen:
            continue
        seen.add(normalized)
        dynamic_headers.append(header)
    return dynamic_headers, relevant_attributes


def build_asset_template(asset_types):
    dynamic_headers, attributes = asset_template_metadata(asset_types)
    asset_type_names = ', '.join(asset_types.values_list('name', flat=True)) or 'All asset types'
    sheets = [
        (
            'Instructions',
            [
                ['Bulk Asset Upload Template'],
                [],
                ['Use one row per asset.'],
                ['Download the template, fill in the values, and upload the same file back here.'],
                ['Asset Type must match an existing asset type name exactly.'],
                ['Leave attribute columns blank when they are not used for that row.'],
            ],
        ),
        (
            'Asset Upload',
            [ASSET_TEMPLATE_BASE_HEADERS + dynamic_headers],
        ),
        (
            'Attribute Reference',
            [
                ['Asset Type', 'Attribute', 'Field Type', 'Options', 'Common'],
                *[
                    [
                        ', '.join(
                            sorted(
                                {
                                    'Common'
                                    if attr.is_common
                                    else org_type.name
                                    for org_type in attr.asset_types.all()
                                }
                            )
                        )
                        or 'Common',
                        attr.name,
                        attr.field_type,
                        ', '.join(attr.options or []) if isinstance(attr.options, list) else '',
                        'Yes' if attr.is_common else 'No',
                    ]
                    for attr in attributes
                ],
            ],
        ),
    ]
    return build_xlsx_workbook(sheets), asset_type_names, dynamic_headers


def parse_asset_bulk_upload(file_obj):
    sheets = read_xlsx_workbook(file_obj)
    if not sheets:
        raise ValueError('The uploaded workbook is empty.')

    rows = []
    normalized_upload_sheet = normalize_header('Asset Upload')
    for sheet_name, sheet_rows in sheets:
        if normalize_header(sheet_name) == normalized_upload_sheet:
            rows = sheet_rows
            break

    candidate_sheets = [rows] if rows else []
    candidate_sheets.extend(sheet_rows for _, sheet_rows in sheets if sheet_rows is not rows)

    header_index = None
    mapping = {}
    normalized_base_headers = {normalize_asset_header(header): header for header in ASSET_TEMPLATE_BASE_HEADERS}
    for sheet_rows in candidate_sheets:
        for index, row in enumerate(sheet_rows[:20]):
            candidate = {
                normalize_asset_header(cell): idx
                for idx, cell in enumerate(row)
                if normalize_asset_header(cell) in normalized_base_headers
            }
            if 'asset type' in candidate and 'asset id' in candidate:
                rows = sheet_rows
                header_index = index
                mapping = candidate
                headers = row
                break
        if header_index is not None:
            break

    if header_index is None:
        raise ValueError('Could not find the Asset Type and Asset ID columns in the workbook.')

    headers = rows[header_index]
    header_lookup = {normalize_asset_header(header): index for index, header in enumerate(headers)}
    base_lookup = {normalize_asset_header(header): header for header in ASSET_TEMPLATE_BASE_HEADERS}

    parsed_rows = []
    errors = []
    dynamic_headers = [
        header
        for header in headers
        if normalize_asset_header(header) not in base_lookup and normalize_asset_header(header)
    ]
    dynamic_header_lookup = {normalize_asset_header(header): header for header in dynamic_headers}
    asset_type_lookup = {
        normalize_match_value(asset_type.name): asset_type
        for asset_type in AssetType.objects.all()
    }

    def cell_value(row, header_name):
        index = header_lookup.get(normalize_asset_header(header_name))
        if index is None or index >= len(row):
            return ''
        return str(row[index] or '').strip()

    for row_number, row in enumerate(rows[header_index + 1:], start=header_index + 2):
        if not any(str(value or '').strip() for value in row):
            continue

        asset_type_name = cell_value(row, 'Asset Type')
        asset_id = cell_value(row, 'Asset ID')
        if not asset_type_name or not asset_id:
            errors.append(f'Row {row_number}: Asset Type and Asset ID are required.')
            continue

        asset_type = asset_type_lookup.get(normalize_match_value(asset_type_name))
        if not asset_type:
            errors.append(f'Row {row_number}: Unknown asset type "{asset_type_name}".')
            continue

        attribute_values = {}
        for header in dynamic_headers:
            index = header_lookup.get(normalize_asset_header(header))
            if index is None or index >= len(row):
                continue
            value = str(row[index] or '').strip()
            if value == '':
                continue
            attribute_values[header] = value

        payload = {
            'asset_type': asset_type.name,
            'asset_id': asset_id,
            'serial_number': cell_value(row, 'Serial Number'),
            'vendor': cell_value(row, 'Vendor'),
            'purchase_date': cell_value(row, 'Purchase Date') or None,
            'purchase_cost': cell_value(row, 'Purchase Cost') or None,
            'warranty_expiry': cell_value(row, 'Warranty Expiry') or None,
            'status': normalize_asset_upload_status(cell_value(row, 'Status'), attribute_values),
            'notes': cell_value(row, 'Notes'),
            'attribute_values': attribute_values,
            'row_number': row_number,
        }
        parsed_rows.append(payload)

    if errors:
        raise ValueError(' ; '.join(errors))

    return parsed_rows


def report_column_map(headers):
    normalized_headers = [normalize_header(header).strip(' -') for header in headers]
    mapping = {}
    for field, aliases in REPORT_HEADER_ALIASES.items():
        for index, header in enumerate(normalized_headers):
            if header in aliases:
                mapping[field] = index
                break
    return mapping


def parse_installed_app_report(file_obj):
    rows = read_xlsx_rows(file_obj)
    if not rows:
        return []

    header_index = None
    mapping = {}
    for index, row in enumerate(rows[:20]):
        candidate = report_column_map(row)
        if 'device_name' in candidate and 'application_name' in candidate:
            header_index = index
            mapping = candidate
            break

    if header_index is None:
        raise ValueError('Could not find Device Name and Application Name columns in the report.')

    parsed = []
    for row in rows[header_index + 1:]:
        if not any(str(value or '').strip() for value in row):
            continue
        device_name = str(row[mapping['device_name']] if mapping['device_name'] < len(row) else '').strip()
        application_name = str(row[mapping['application_name']] if mapping['application_name'] < len(row) else '').strip()
        if not device_name or not application_name or set(device_name) == {'-'}:
            continue

        def mapped_value(field):
            index = mapping.get(field)
            if index is None or index >= len(row):
                return ''
            return str(row[index] or '').strip()

        parsed.append({
            'device_name': device_name,
            'normalized_device_name': normalize_match_value(device_name),
            'application_package': mapped_value('application_package'),
            'application_name': application_name,
            'application_type': mapped_value('application_type'),
            'user_name': mapped_value('user_name'),
            'application_version': mapped_value('application_version'),
            'signature_key_hash': mapped_value('signature_key_hash'),
        })
    return parsed


def imported_apps_for_device(*device_names):
    normalized_names = {
        variant
        for name in device_names
        for variant in normalized_match_variants(name)
    }
    if not normalized_names:
        return []
    return list(
        InstalledApplication.objects
        .filter(normalized_device_name__in=normalized_names)
        .order_by('application_name')
        .values(
            'application_name',
            'application_package',
            'application_type',
            'user_name',
            'application_version',
            'signature_key_hash',
            'report_import__file_name',
            'report_import__imported_at',
        )
    )


def normalize_imported_app(app):
    return {
        'name': app.get('application_name') or app.get('application_package') or '',
        'version': app.get('application_version') or '',
        'vendor': app.get('user_name') or '',
        'installed_on': '',
        'application_package': app.get('application_package') or '',
        'application_type': app.get('application_type') or '',
        'user_name': app.get('user_name') or '',
        'source': app.get('report_import__file_name') or 'Uploaded SureMDM report',
        'imported_at': app.get('report_import__imported_at'),
        'raw': app,
    }


def first_attribute_value(attributes, named_attributes, *keys):
    for key in keys:
        value = attributes.get(key)
        if value not in (None, ''):
            return value
        value = named_attributes.get(key)
        if value not in (None, ''):
            return value
    normalized = {
        normalize_match_value(key): value
        for key, value in {**attributes, **named_attributes}.items()
        if value not in (None, '')
    }
    for key in keys:
        value = normalized.get(normalize_match_value(key))
        if value not in (None, ''):
            return value
    return ''


def find_matching_mdm_device(asset, attributes, named_attributes, client):
    from apps.integrations.views import normalize_devices_with_groups

    asset_candidates = [
        asset.asset_id,
        asset.serial_number,
        first_attribute_value(attributes, named_attributes, 'suremdm_device_id', 'DeviceID', 'MDM Device ID'),
        first_attribute_value(attributes, named_attributes, *ASSET_SYSTEM_TAG_KEYS),
        first_attribute_value(attributes, named_attributes, 'device_name', 'Device Name', 'hostname', 'Host Name'),
    ]
    normalized_asset_candidates = {
        variant
        for candidate in asset_candidates
        for variant in normalized_match_variants(candidate)
    }
    if not normalized_asset_candidates:
        return None

    devices = normalize_devices_with_groups(client, limit=1000)
    for device in devices:
        device_candidates = [
            device.get('system_tag'),
            device.get('name'),
            device.get('serial_number'),
            device.get('suremdm_device_id'),
        ]
        normalized_device_candidates = {
            variant
            for candidate in device_candidates
            for variant in normalized_match_variants(candidate)
        }
        if normalized_asset_candidates & normalized_device_candidates:
            return device
    return None


class AssetTypeViewSet(viewsets.ModelViewSet):
    """
    CRUD for asset types.
    Write: IT specialist or super_admin. Read: all authenticated.
    """

    queryset = AssetType.objects.all()
    serializer_class = AssetTypeSerializer
    pagination_class = None

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsITSpecialistOrSuperAdmin()]
        return [IsAuthenticated()]


class AssetAttributeViewSet(viewsets.ModelViewSet):
    """
    CRUD for asset attributes.
    Write: IT specialist or super_admin. Read: all authenticated.
    """

    queryset = AssetAttribute.objects.prefetch_related('asset_types').all()
    serializer_class = AssetAttributeSerializer
    pagination_class = None

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsITSpecialistOrSuperAdmin()]
        return [IsAuthenticated()]


class AssetViewSet(viewsets.ModelViewSet):
    """
    CRUD for assets.
    Write: IT specialist or super_admin. Read: all authenticated.
    dashboard_stats action: IT/HR/super_admin.
    """

    queryset = Asset.objects.select_related('asset_type', 'organisation', 'location', 'location__organisation').all()

    def get_queryset(self):
        queryset = super().get_queryset()
        status = self.request.query_params.get('status')
        source = self.request.query_params.get('source')
        organisation_id = self.request.query_params.get('organisation_id')
        location_id = self.request.query_params.get('location_id')

        if status:
            queryset = queryset.filter(status=status)
        if organisation_id:
            queryset = queryset.filter(organisation_id=organisation_id)
        if location_id:
            queryset = queryset.filter(location_id=location_id)
        if source == 'portal':
            queryset = queryset.exclude(vendor='SureMDM').exclude(asset_id__startswith='SUREMDM-')

        return queryset

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return AssetCreateSerializer
        return AssetSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsITSpecialistOrSuperAdmin()]
        if self.action == 'upload_installed_app_report':
            return [IsITSpecialistOrSuperAdmin()]
        if self.action in ('bulk_template', 'bulk_upload'):
            return [IsITSpecialistOrSuperAdmin()]
        if self.action == 'dashboard_stats':
            return [IsITOrHROrSuperAdmin()]
        return [IsAuthenticated()]

    @action(detail=False, methods=['get'], url_path='bulk-template')
    def bulk_template(self, request):
        asset_type_ids = [
            value
            for value in request.query_params.get('asset_type_ids', '').split(',')
            if value.strip().isdigit()
        ]
        asset_types = AssetType.objects.filter(id__in=asset_type_ids).order_by('name')
        if not asset_type_ids:
            asset_types = AssetType.objects.all().order_by('name')

        workbook_bytes, asset_type_names, dynamic_headers = build_asset_template(asset_types)
        filename = 'asset-bulk-upload-template.xlsx'
        if asset_type_names:
            filename = f"asset-bulk-upload-template-{asset_type_names.replace(', ', '-').replace('/', '-')}.xlsx"
        response = HttpResponse(workbook_bytes, content_type=XLSX_MIME_TYPE)
        response['Content-Disposition'] = f"attachment; filename*=UTF-8''{quote(filename)}"
        response['X-Template-Asset-Types'] = asset_type_names
        response['X-Template-Attribute-Count'] = str(len(dynamic_headers))
        return response

    @action(detail=False, methods=['post'], url_path='bulk-upload', parser_classes=[MultiPartParser])
    def bulk_upload(self, request):
        upload_file = request.FILES.get('file')
        if not upload_file:
            return Response({'detail': 'Upload an .xlsx template file.'}, status=drf_status.HTTP_400_BAD_REQUEST)
        if not upload_file.name.lower().endswith('.xlsx'):
            return Response({'detail': 'Only .xlsx files are supported.'}, status=drf_status.HTTP_400_BAD_REQUEST)

        try:
            rows = parse_asset_bulk_upload(upload_file)
        except (zipfile.BadZipFile, ElementTree.ParseError, KeyError, ValueError) as exc:
            return Response({'detail': str(exc)}, status=drf_status.HTTP_400_BAD_REQUEST)

        if not rows:
            return Response({'detail': 'No asset rows were found in the uploaded workbook.'}, status=drf_status.HTTP_400_BAD_REQUEST)

        created = 0
        updated = 0
        row_errors = []

        with transaction.atomic():
            for row in rows:
                row_number = row.pop('row_number')
                attribute_values = row.pop('attribute_values', {})
                asset_type_name = row['asset_type']
                asset_type, _ = AssetType.objects.get_or_create(
                    name=asset_type_name,
                    defaults={'asset_type': 'hardware'},
                )

                serializer = AssetCreateSerializer(data={**row, 'asset_type': asset_type.name, 'attribute_values': attribute_values})
                if not serializer.is_valid():
                    row_errors.append(f"Row {row_number}: {serializer.errors}")
                    continue

                asset_id = serializer.validated_data['asset_id']
                instance = Asset.objects.filter(asset_id=asset_id).first()
                if instance:
                    for attr, value in serializer.validated_data.items():
                        if attr == 'asset_type':
                            instance.asset_type = asset_type
                        else:
                            setattr(instance, attr, value)
                    instance.save()
                    updated += 1
                else:
                    serializer.save()
                    created += 1

            if row_errors:
                transaction.set_rollback(True)
                return Response(
                    {
                        'detail': 'Some rows could not be imported.',
                        'errors': row_errors,
                        'created': created,
                        'updated': updated,
                    },
                    status=drf_status.HTTP_400_BAD_REQUEST,
                )

        return Response({'detail': 'Bulk asset upload completed.', 'created': created, 'updated': updated})

    @action(detail=False, methods=['get'], url_path='dashboard-stats')
    def dashboard_stats(self, request):
        """
        Returns a summary of asset counts by status and type,
        top 5 asset types, and a software licence seat summary.
        """
        assets_qs = Asset.objects.exclude(vendor='SureMDM').exclude(asset_id__startswith='SUREMDM-')
        organisation_id = request.query_params.get('organisation_id')
        if organisation_id:
            assets_qs = assets_qs.filter(organisation_id=organisation_id)
        total = assets_qs.count()

        status_counts = {
            'available': assets_qs.filter(status='available').count(),
            'assigned': assets_qs.filter(status='assigned').count(),
            'maintenance': assets_qs.filter(status='maintenance').count(),
            'retired': assets_qs.filter(status='retired').count(),
        }

        # Count per asset type (name)
        assets_by_type = (
            assets_qs.values('asset_type__name')
            .annotate(count=Count('id'))
            .order_by('asset_type__name')
        )
        assets_by_type_list = [
            {'asset_type': row['asset_type__name'], 'count': row['count']}
            for row in assets_by_type
        ]

        top_5_types = sorted(assets_by_type_list, key=lambda x: x['count'], reverse=True)[:5]

        # Software licence summary
        licenses_qs = SoftwareLicense.objects.all()
        if organisation_id:
            licenses_qs = licenses_qs.filter(organisation_id=organisation_id)
        total_seats = licenses_qs.aggregate(total=Sum('total_seats'))['total'] or 0
        available_seats = licenses_qs.aggregate(avail=Sum('available_seats'))['avail'] or 0
        used_seats = total_seats - available_seats

        return Response(
            {
                'total_assets': total,
                'status_counts': status_counts,
                'assets_by_type': assets_by_type_list,
                'top_5_asset_types': top_5_types,
                'software_licenses': {
                    'total_licenses': licenses_qs.count(),
                    'total_seats': total_seats,
                    'used_seats': used_seats,
                    'available_seats': available_seats,
                },
            }
        )

    @action(
        detail=False,
        methods=['post'],
        url_path='installed-app-report/upload',
        parser_classes=[MultiPartParser],
    )
    def upload_installed_app_report(self, request):
        report_file = request.FILES.get('file')
        if not report_file:
            return Response({'detail': 'Upload an .xlsx report file.'}, status=drf_status.HTTP_400_BAD_REQUEST)
        if not report_file.name.lower().endswith('.xlsx'):
            return Response({'detail': 'Only .xlsx SureMDM reports are supported.'}, status=drf_status.HTTP_400_BAD_REQUEST)

        try:
            app_rows = parse_installed_app_report(report_file)
        except (zipfile.BadZipFile, ElementTree.ParseError, KeyError, ValueError) as exc:
            return Response({'detail': str(exc)}, status=drf_status.HTTP_400_BAD_REQUEST)

        if not app_rows:
            return Response({'detail': 'No installed applications were found in the report.'}, status=drf_status.HTTP_400_BAD_REQUEST)

        device_names = {row['device_name'] for row in app_rows}
        normalized_device_names = {row['normalized_device_name'] for row in app_rows}
        with transaction.atomic():
            report_import = InstalledAppReportImport.objects.create(
                file_name=report_file.name,
                imported_by=request.user if request.user.is_authenticated else None,
                device_count=len(device_names),
                app_count=len(app_rows),
            )
            InstalledApplication.objects.filter(
                normalized_device_name__in=normalized_device_names
            ).delete()
            InstalledApplication.objects.bulk_create([
                InstalledApplication(report_import=report_import, **row)
                for row in app_rows
            ], batch_size=1000)

        return Response({
            'id': report_import.id,
            'file_name': report_import.file_name,
            'device_count': report_import.device_count,
            'app_count': report_import.app_count,
        })

    @action(detail=True, methods=['get'], url_path='device-dashboard')
    def device_dashboard(self, request, pk=None):
        asset = self.get_object()
        asset_data = AssetSerializer(asset).data
        attributes = asset.attribute_values or {}
        named_attributes = asset_data.get('attribute_values_with_names') or {}
        device_id = (
            attributes.get('suremdm_device_id')
            or named_attributes.get('suremdm_device_id')
            or attributes.get('DeviceID')
            or named_attributes.get('DeviceID')
        )

        installed_apps = []
        mdm_error = ''
        matched_device = None
        try:
            from apps.integrations.views import get_client, get_connection
            from apps.integrations.suremdm import SureMDMError

            connection = get_connection()
            if connection and connection.is_active:
                client = get_client(connection)
                matched_device = find_matching_mdm_device(asset, attributes, named_attributes, client)
                if matched_device and not device_id:
                    device_id = matched_device.get('suremdm_device_id')
                if device_id:
                    raw_apps = client.installed_apps(device_id)
                    installed_apps = [normalize_installed_app(app) for app in raw_apps]
                    if not installed_apps and matched_device:
                        installed_apps = [
                            normalize_installed_app(app)
                            for app in embedded_device_apps(matched_device)
                        ]
                elif matched_device:
                    mdm_error = 'Matched the SureMDM device, but it has no MDM device ID for the installed app report.'
                else:
                    mdm_error = 'No matching SureMDM device was found for this asset system tag.'
            else:
                mdm_error = 'SureMDM is not configured.'
        except SureMDMError as exc:
            mdm_error = str(exc)

        device_name = (
            (matched_device or {}).get('name')
            or attributes.get('device_name')
            or named_attributes.get('device_name')
            or asset.notes
        )
        serial_number = (matched_device or {}).get('serial_number') or asset.serial_number
        platform = (matched_device or {}).get('platform') or attributes.get('platform') or named_attributes.get('platform')
        model = (matched_device or {}).get('model') or attributes.get('model') or named_attributes.get('model')
        category = (matched_device or {}).get('category') or attributes.get('category') or named_attributes.get('category')
        last_seen = (matched_device or {}).get('last_seen') or attributes.get('last_seen') or named_attributes.get('last_seen')
        system_tag = (
            (matched_device or {}).get('system_tag')
            or first_attribute_value(attributes, named_attributes, *ASSET_SYSTEM_TAG_KEYS)
            or asset.asset_id
        )
        processor = (
            (matched_device or {}).get('processor')
            or first_attribute_value(attributes, named_attributes, 'processor', 'Processor', 'CPU')
        )
        ram = (
            (matched_device or {}).get('ram')
            or first_attribute_value(attributes, named_attributes, 'ram', 'RAM', 'Memory')
        )
        storage = (
            (matched_device or {}).get('storage')
            or first_attribute_value(attributes, named_attributes, 'storage', 'Storage', 'Disk')
        )
        manufacturer = (
            (matched_device or {}).get('manufacturer')
            or first_attribute_value(attributes, named_attributes, 'manufacturer', 'Manufacturer', 'Make')
        )
        installed_apps_source = 'suremdm_api'
        if not installed_apps:
            imported_apps = imported_apps_for_device(
                system_tag,
                device_name,
                serial_number,
                asset.asset_id,
                attributes.get('device_name'),
                named_attributes.get('device_name'),
            )
            if imported_apps:
                installed_apps = [normalize_imported_app(app) for app in imported_apps]
                installed_apps_source = 'uploaded_report'
                mdm_error = ''

        from apps.allocation.models import AssetAllocation
        active_allocation = AssetAllocation.objects.filter(asset=asset, status='active').select_related('employee').first()
        assigned_user_name = active_allocation.employee.full_name if active_allocation else None

        return Response(
            {
                'asset': asset_data,
                'device': {
                    'device_id': device_id,
                    'name': device_name,
                    'serial_number': serial_number,
                    'system_tag': system_tag,
                    'platform': platform,
                    'model': model,
                    'category': category,
                    'last_seen': last_seen,
                    'processor': processor,
                    'ram': ram,
                    'storage': storage,
                    'manufacturer': manufacturer,
                    'mdm_matched': bool(matched_device or device_id),
                    'assigned_user_name': assigned_user_name,
                },
                'installed_apps': installed_apps,
                'installed_apps_source': installed_apps_source,
                'installed_apps_error': mdm_error,
            }
        )


class AssetChoicesViewSet(viewsets.ViewSet):
    """
    Returns admin-defined choice lists for Asset forms.
    asset-types: all AssetType records (admin creates/manages via /inventory/asset-types/).
    status-choices: Asset.STATUS_CHOICES as value/label pairs.
    """
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'], url_path='asset-type-list')
    def asset_type_list(self, request):
        from .serializers import AssetTypeSerializer
        qs = AssetType.objects.all().order_by('name')
        return Response(AssetTypeSerializer(qs, many=True).data)

    @action(detail=False, methods=['get'], url_path='status-choices')
    def status_choices(self, request):
        return Response([
            {'value': value, 'label': label}
            for value, label in Asset.STATUS_CHOICES
        ])

    @action(detail=False, methods=['get'], url_path='license-type-choices')
    def license_type_choices(self, request):
        return Response([
            {'value': value, 'label': label}
            for value, label in SoftwareLicense.LICENSE_TYPE_CHOICES
        ])


class SoftwareLicenseViewSet(viewsets.ModelViewSet):
    """
    CRUD for software licences.
    Write: IT specialist or super_admin. Read: all authenticated.
    """

    queryset = SoftwareLicense.objects.all()
    serializer_class = SoftwareLicenseSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        organisation_id = self.request.query_params.get('organisation_id')
        if organisation_id:
            queryset = queryset.filter(organisation_id=organisation_id)
        return queryset

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsITSpecialistOrSuperAdmin()]
        return [IsAuthenticated()]
