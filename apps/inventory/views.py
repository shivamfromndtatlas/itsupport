import posixpath
import zipfile
from io import BytesIO
from xml.etree import ElementTree

from django.db import transaction
from django.db.models import Count, Sum
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


def xlsx_cell_ref_col(cell_ref):
    letters = ''.join(ch for ch in cell_ref if ch.isalpha())
    index = 0
    for char in letters:
        index = index * 26 + (ord(char.upper()) - ord('A') + 1)
    return index - 1


def read_xlsx_rows(file_obj):
    workbook = zipfile.ZipFile(BytesIO(file_obj.read()))
    shared_strings = []
    if 'xl/sharedStrings.xml' in workbook.namelist():
        shared_root = ElementTree.fromstring(workbook.read('xl/sharedStrings.xml'))
        for item in shared_root.findall('a:si', XLSX_NS):
            shared_strings.append(''.join(text.text or '' for text in item.findall('.//a:t', XLSX_NS)))

    workbook_root = ElementTree.fromstring(workbook.read('xl/workbook.xml'))
    rels_root = ElementTree.fromstring(workbook.read('xl/_rels/workbook.xml.rels'))
    rel_map = {rel.attrib['Id']: rel.attrib['Target'] for rel in rels_root}
    first_sheet = workbook_root.find('a:sheets/a:sheet', XLSX_NS)
    if first_sheet is None:
        return []

    relation_id = first_sheet.attrib[f'{{{REL_NS}}}id']
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
    return rows


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

    queryset = Asset.objects.select_related('asset_type').all()

    def get_queryset(self):
        queryset = super().get_queryset()
        status = self.request.query_params.get('status')
        source = self.request.query_params.get('source')

        if status:
            queryset = queryset.filter(status=status)
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
        if self.action == 'dashboard_stats':
            return [IsITOrHROrSuperAdmin()]
        return [IsAuthenticated()]

    @action(detail=False, methods=['get'], url_path='dashboard-stats')
    def dashboard_stats(self, request):
        """
        Returns a summary of asset counts by status and type,
        top 5 asset types, and a software licence seat summary.
        """
        assets_qs = Asset.objects.exclude(vendor='SureMDM').exclude(asset_id__startswith='SUREMDM-')
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

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsITSpecialistOrSuperAdmin()]
        return [IsAuthenticated()]
