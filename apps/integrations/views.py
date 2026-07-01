from django.db import models, transaction
from django.utils import timezone
from django.utils.dateparse import parse_date
from datetime import timedelta
import re
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ViewSet

from apps.inventory.models import Asset, AssetType
from apps.users.permissions import IsITSpecialistOrSuperAdmin

from .models import SureMDMConnection
from .serializers import SureMDMConnectionSerializer
from .suremdm import SureMDMClient, SureMDMError


CATEGORY_KEYS = (
    'GroupPath',
    'GroupName',
    'Group',
    'DeviceGroup',
    'DeviceGroupName',
    'DeviceGroupPath',
    'GroupFullPath',
    'GroupFullName',
    'PathName',
    'FolderName',
    'FolderPath',
    'Path',
    'Category',
    'DeviceCategory',
)

PLATFORM_KEYS = (
    'Platform',
    'platform',
    'OsType',
    'OSType',
    'OS',
    'os',
    'OSName',
    'DeviceOS',
    'DeviceOSType',
    'OperatingSystem',
    'OperatingSystemName',
    'PlatformName',
    'PlatformType',
)

MODEL_KEYS = (
    'Model',
    'model',
    'DeviceModel',
    'DeviceModelName',
    'ModelName',
    'DeviceModelNumber',
    'ProductName',
    'HardwareModel',
    'SystemModel',
)

SYSTEM_TAG_KEYS = (
    'SystemTag',
    'System Tag',
    'AssetTag',
    'Asset Tag',
    'DeviceTag',
    'Device Tag',
    'ComputerName',
    'Computer Name',
)

PROCESSOR_KEYS = (
    'Processor',
    'CPU',
    'Cpu',
    'ProcessorName',
    'CPUName',
)

RAM_KEYS = (
    'RAM',
    'Ram',
    'Memory',
    'TotalMemory',
    'TotalRAM',
    'PhysicalMemory',
    'TotalPhysicalMemory',
)

STORAGE_KEYS = (
    'Storage',
    'Disk',
    'HardDisk',
    'TotalStorage',
    'TotalDiskSpace',
    'StorageMemoryTotal',
    'MemoryStorageAvailable',
    'DrivesStorageMemory',
)

MANUFACTURER_KEYS = (
    'Manufacturer',
    'Make',
    'OEM',
    'Vendor',
    'DeviceManufacture',
    'DeviceManufacturer',
)

SERIAL_KEYS = (
    'SerialNumber',
    'SerialNo',
    'Serial',
    'serial_number',
    'DeviceSerialNumber',
)

NAME_KEYS = (
    'DeviceName',
    'Name',
    'name',
    'Device',
    'HostName',
    'Hostname',
)

LAST_SEEN_KEYS = (
    'LastTimeStamp',
    'LastSeen',
    'last_seen',
    'LastConnected',
    'LastDeviceTime',
    'LastConnectedTime',
)

GROUP_DEVICE_IDS = (
    'Windows',
    'Windows - India',
    'Windows - US',
    'SureMDM',
    'Android',
)

ACTIVE_DURATION_KEYS = (
    'ActiveTime',
    'ActiveDuration',
    'UsageTime',
    'UsageDuration',
    'OnlineDuration',
    'SessionDuration',
    'TimeSpent',
    'ScreenOnTime',
    'ScreenActiveTime',
    'TotalActiveTime',
    'TotalUsageTime',
    'Uptime',
)


def get_connection():
    return SureMDMConnection.objects.order_by('-updated_at').first()


def get_client(connection):
    return SureMDMClient(
        base_url=connection.base_url,
        username=connection.username,
        password=connection.password,
        api_key=connection.api_key,
    )


def flatten_device(device):
    flattened = {}

    def visit(value, prefix=''):
        if isinstance(value, dict):
            for key, nested in value.items():
                key_text = str(key)
                flattened.setdefault(key_text, nested)
                visit(nested, f'{prefix}{key_text}.')
        elif isinstance(value, list):
            for index, nested in enumerate(value):
                visit(nested, f'{prefix}{index}.')

    visit(device)
    return flattened


def clean_cell_value(value):
    if value in (None, ''):
        return ''
    if isinstance(value, dict):
        return (
            value.get('text')
            or value.get('value')
            or value.get('Value')
            or value.get('name')
            or value.get('Name')
            or ''
        )
    return value


def row_cell_value(device, *keys):
    cells = device.get('cell') or device.get('Cell') or device.get('cells') or []
    if not isinstance(cells, list):
        return ''

    # SureMDM's device grid response can come back as row cells instead of
    # named fields. These positions match the visible grid order in the console.
    cell_indexes = {
        'DeviceName': (4, 3),
        'Name': (4, 3),
        'SerialNumber': (4, 3),
        'Platform': (6,),
        'Model': (6,),
        'LastTimeStamp': (10, 11),
        'LastSeen': (10, 11),
        'LastConnected': (10,),
        'LastDeviceTime': (11,),
    }

    for key in keys:
        for index in cell_indexes.get(key, ()):
            if index < len(cells):
                value = clean_cell_value(cells[index])
                if value not in (None, ''):
                    return value
    return ''


def device_value(device, *keys, default=''):
    if not isinstance(device, dict):
        return default

    for key in keys:
        value = device.get(key)
        value = clean_cell_value(value)
        if value not in (None, ''):
            return value

    flattened = flatten_device(device)
    normalized_keys = {str(key).lower().replace(' ', '').replace('_', ''): key for key in flattened}
    for key in keys:
        lookup_key = str(key).lower().replace(' ', '').replace('_', '')
        original_key = normalized_keys.get(lookup_key)
        if original_key:
            value = clean_cell_value(flattened[original_key])
            if value not in (None, ''):
                return value

    value = row_cell_value(device, *keys)
    if value not in (None, ''):
        return value

    return default


def parse_duration_to_minutes(value):
    if value in (None, ''):
        return None
    if isinstance(value, (int, float)):
        if value < 0:
            return None
        return float(value) / 60 if value > 240 else float(value)
    text = str(value).strip()
    if not text:
        return None

    lowered = text.lower()
    if lowered in {'n/a', 'na', 'none', 'null'}:
        return None

    total_minutes = 0.0
    matched = False
    for chunk in lowered.replace(',', ' ').split():
        try:
            if chunk.endswith('ms'):
                total_minutes += float(chunk[:-2]) / 60000
                matched = True
            elif chunk.endswith('s'):
                total_minutes += float(chunk[:-1]) / 60
                matched = True
            elif chunk.endswith('m'):
                total_minutes += float(chunk[:-1])
                matched = True
            elif chunk.endswith('h'):
                total_minutes += float(chunk[:-1]) * 60
                matched = True
            elif chunk.endswith('d'):
                total_minutes += float(chunk[:-1]) * 1440
                matched = True
            elif ':' in chunk:
                parts = [float(part) for part in chunk.split(':')]
                if len(parts) == 2:
                    total_minutes += parts[0] * 60 + parts[1]
                    matched = True
                elif len(parts) == 3:
                    total_minutes += parts[0] * 60 + parts[1] + parts[2] / 60
                    matched = True
            else:
                try:
                    total_minutes += float(chunk)
                    matched = True
                except ValueError:
                    continue
        except ValueError:
            continue

    if matched:
        return total_minutes

    match = re.fullmatch(r'(?:(\d+)\s*d)?\s*(?:(\d+)\s*h)?\s*(?:(\d+)\s*m)?\s*(?:(\d+)\s*s)?', lowered)
    if match and any(match.groups()):
        days, hours, minutes, seconds = [int(part or 0) for part in match.groups()]
        return days * 1440 + hours * 60 + minutes + seconds / 60

    return None


def extract_active_minutes(device):
    raw_candidates = []
    if isinstance(device, dict):
        for key in ACTIVE_DURATION_KEYS:
            raw_candidates.append(device.get(key))
        raw = device.get('raw')
        if isinstance(raw, dict):
            for key in ACTIVE_DURATION_KEYS:
                raw_candidates.append(raw.get(key))
        flattened = flatten_device(device)
        for key in ACTIVE_DURATION_KEYS:
            for candidate_key, candidate_value in flattened.items():
                if str(candidate_key).lower().replace(' ', '').replace('_', '') == str(key).lower().replace(' ', '').replace('_', ''):
                    raw_candidates.append(candidate_value)
    for candidate in raw_candidates:
        minutes = parse_duration_to_minutes(candidate)
        if minutes is not None:
            return minutes, candidate
    return 0.0, ''


def build_date_range(start_date, end_date):
    current = start_date
    while current <= end_date:
        yield current
        current += timedelta(days=1)


def _normalize_lookup(value):
    return str(value or '').strip().lower()


def is_laptop_asset(asset):
    asset_type_name = _normalize_lookup(getattr(asset.asset_type, 'name', ''))
    asset_type_kind = _normalize_lookup(getattr(asset.asset_type, 'asset_type', ''))
    return (
        'laptop' in asset_type_name
        or 'notebook' in asset_type_name
        or 'laptop' in asset_type_kind
        or 'notebook' in asset_type_kind
    )


def find_suremdm_asset_for_employee_asset(employee_asset):
    if not employee_asset:
        return None

    candidate_values = {
        employee_asset.asset_id,
        employee_asset.serial_number,
    }
    attribute_values = employee_asset.attribute_values if isinstance(employee_asset.attribute_values, dict) else {}
    candidate_values.update(
        {
            attribute_values.get('suremdm_device_id'),
            attribute_values.get('DeviceID'),
            attribute_values.get('MDM Device ID'),
            attribute_values.get('device_name'),
            attribute_values.get('DeviceName'),
        }
    )
    candidate_values = {_normalize_lookup(value) for value in candidate_values if value}

    suremdm_assets = Asset.objects.select_related('asset_type').filter(
        models.Q(vendor__iexact='SureMDM') | models.Q(asset_id__istartswith='SUREMDM-')
    )

    for mdm_asset in suremdm_assets:
        mdm_values = {
            _normalize_lookup(mdm_asset.asset_id),
            _normalize_lookup(mdm_asset.serial_number),
        }
        mdm_attrs = mdm_asset.attribute_values if isinstance(mdm_asset.attribute_values, dict) else {}
        mdm_values.update(
            {
                _normalize_lookup(mdm_attrs.get('suremdm_device_id')),
                _normalize_lookup(mdm_attrs.get('DeviceID')),
                _normalize_lookup(mdm_attrs.get('MDM Device ID')),
                _normalize_lookup(mdm_attrs.get('device_name')),
                _normalize_lookup(mdm_attrs.get('DeviceName')),
            }
        )
        if candidate_values.intersection(mdm_values):
            return mdm_asset

    return None


def split_platform_model(value):
    text = str(value or '').strip()
    if not text:
        return '', ''

    lower_text = text.lower()
    if 'windows' in lower_text:
        platform = 'Windows'
    elif 'android' in lower_text:
        platform = 'Android'
    elif 'ios' in lower_text or 'ipad' in lower_text:
        platform = 'iOS'
    elif 'mac' in lower_text:
        platform = 'macOS'
    elif 'linux' in lower_text:
        platform = 'Linux'
    else:
        platform = ''

    model = text
    for label in ('Windows', 'Android', 'iOS', 'macOS', 'Linux'):
        model = model.replace(label, '').strip(' -/')
    return platform, model


def format_bytes(value):
    try:
        size = float(value)
    except (TypeError, ValueError):
        return value

    units = ('B', 'KB', 'MB', 'GB', 'TB')
    unit_index = 0
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    if unit_index == 0:
        return f'{int(size)} {units[unit_index]}'
    return f'{size:.1f} {units[unit_index]}'


def normalize_storage_value(value):
    if isinstance(value, str) and ':' in value:
        parts = value.split()
        if len(parts) >= 3:
            return f'{parts[0]} {format_bytes(parts[2])}'
    return format_bytes(value)


def normalize_category(value):
    if not value:
        return 'Uncategorized'
    if isinstance(value, dict):
        value = value.get('Name') or value.get('name') or value.get('GroupName') or value.get('Path') or ''
    if isinstance(value, list):
        value = ' / '.join(str(part) for part in value if part)

    category = str(value).strip().strip('/')
    if not category:
        return 'Uncategorized'

    parts = [part.strip() for part in category.replace('\\', '/').split('/') if part.strip()]
    if parts and parts[0].lower() == 'home':
        parts = parts[1:]
    return parts[-1] if parts else category


def normalize_device(device, category=None):
    device_id = device_value(device, 'DeviceID', 'DeviceId', 'ID', 'id')
    name = device_value(device, *NAME_KEYS)
    serial = device_value(device, *SERIAL_KEYS)
    system_tag = device_value(device, *SYSTEM_TAG_KEYS)
    platform = device_value(device, *PLATFORM_KEYS)
    model = device_value(device, *MODEL_KEYS)
    ram = device_value(device, *RAM_KEYS)
    storage = device_value(device, *STORAGE_KEYS)
    platform_model = device_value(device, 'Platform / Model', 'PlatformModel', 'PlatformAndModel')
    inferred_platform, inferred_model = split_platform_model(platform_model or platform or model)
    last_seen = device_value(device, *LAST_SEEN_KEYS)
    category = normalize_category(category or device_value(device, *CATEGORY_KEYS))

    return {
        'suremdm_device_id': str(device_id),
        'name': name,
        'serial_number': serial,
        'system_tag': system_tag,
        'platform': platform or inferred_platform,
        'model': model or inferred_model,
        'category': category,
        'last_seen': last_seen,
        'processor': device_value(device, *PROCESSOR_KEYS),
        'ram': format_bytes(ram) if ram else '',
        'storage': normalize_storage_value(storage) if storage else '',
        'manufacturer': device_value(device, *MANUFACTURER_KEYS),
        'raw': device,
    }


def device_identity(device):
    return (
        device.get('suremdm_device_id')
        or device.get('system_tag')
        or device.get('serial_number')
        or device.get('name')
        or ''
    )


def normalize_devices_with_groups(client, limit=500):
    devices = [normalize_device(device) for device in client.list_devices(limit=limit)]
    by_identity = {
        device_identity(device): device
        for device in devices
        if device_identity(device)
    }

    for group_id in GROUP_DEVICE_IDS:
        try:
            group_devices = client.list_devices(limit=limit, group_id=group_id)
        except SureMDMError:
            continue

        category = normalize_category(group_id)
        for raw_device in group_devices:
            group_device = normalize_device(raw_device, category=category)
            identity = device_identity(group_device)
            if identity and identity in by_identity:
                if by_identity[identity]['category'] == 'Uncategorized' or category not in ('Windows', 'Android'):
                    by_identity[identity]['category'] = category
                if group_device['platform']:
                    by_identity[identity]['platform'] = group_device['platform']
                if group_device['model']:
                    by_identity[identity]['model'] = group_device['model']
                for field in ('system_tag', 'processor', 'ram', 'storage', 'manufacturer'):
                    if group_device.get(field):
                        by_identity[identity][field] = group_device[field]
            elif identity:
                devices.append(group_device)
                by_identity[identity] = group_device

    return devices


class SureMDMConnectionView(APIView):
    permission_classes = [IsITSpecialistOrSuperAdmin]

    def get(self, request):
        connection = get_connection()
        if not connection:
            return Response({'configured': False})
        data = SureMDMConnectionSerializer(connection).data
        data['configured'] = True
        return Response(data)

    def post(self, request):
        connection = get_connection()
        serializer = SureMDMConnectionSerializer(
            connection,
            data=request.data,
            partial=bool(connection),
        )
        serializer.is_valid(raise_exception=True)
        connection = serializer.save()
        data = SureMDMConnectionSerializer(connection).data
        data['configured'] = True
        return Response(data, status=status.HTTP_200_OK)


class SureMDMViewSet(ViewSet):
    permission_classes = [IsITSpecialistOrSuperAdmin]

    def _configured_connection(self):
        connection = get_connection()
        if not connection or not connection.is_active:
            return None, Response(
                {'detail': 'SureMDM is not configured.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not connection.username or not connection.password or not connection.api_key:
            return None, Response(
                {'detail': 'SureMDM username, password, and API key are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return connection, None

    @action(detail=False, methods=['post'], url_path='test')
    def test(self, request):
        connection, error = self._configured_connection()
        if error:
            return error

        try:
            devices = get_client(connection).list_devices(limit=1)
            connection.last_test_status = 'success'
            connection.last_test_message = 'Connected to SureMDM successfully.'
            response_status = status.HTTP_200_OK
        except SureMDMError as exc:
            devices = []
            connection.last_test_status = 'failed'
            connection.last_test_message = str(exc)
            response_status = status.HTTP_401_UNAUTHORIZED if exc.status_code == 401 else status.HTTP_400_BAD_REQUEST

        connection.last_tested_at = timezone.now()
        connection.save(update_fields=['last_tested_at', 'last_test_status', 'last_test_message', 'updated_at'])
        return Response(
            {
                'status': connection.last_test_status,
                'message': connection.last_test_message,
                'sample_device_count': len(devices),
            },
            status=response_status,
        )

    @action(detail=False, methods=['get'], url_path='devices')
    def devices(self, request):
        connection, error = self._configured_connection()
        if error:
            return error
        limit = int(request.query_params.get('limit', 50))
        try:
            devices = normalize_devices_with_groups(get_client(connection), limit=limit)
        except SureMDMError as exc:
            response_status = status.HTTP_401_UNAUTHORIZED if exc.status_code == 401 else status.HTTP_400_BAD_REQUEST
            return Response({'detail': str(exc)}, status=response_status)
        return Response({'count': len(devices), 'results': devices})

    @action(detail=False, methods=['get'], url_path='summary')
    def summary(self, request):
        connection, error = self._configured_connection()
        if error:
            return error

        limit = int(request.query_params.get('limit', 500))
        try:
            devices = normalize_devices_with_groups(get_client(connection), limit=limit)
        except SureMDMError as exc:
            response_status = status.HTTP_401_UNAUTHORIZED if exc.status_code == 401 else status.HTTP_400_BAD_REQUEST
            return Response({'detail': str(exc)}, status=response_status)

        categories = {}
        for device in devices:
            category = device['category']
            categories[category] = categories.get(category, 0) + 1

        return Response(
            {
                'total_systems': len(devices),
                'categories': [
                    {'category': name, 'count': count}
                    for name, count in sorted(categories.items())
                ],
            }
        )

    @action(detail=False, methods=['get'], url_path='active-time')
    def active_time(self, request):
        connection, error = self._configured_connection()
        if error:
            return error

        start_date = parse_date(request.query_params.get('start_date') or '') or timezone.localdate()
        end_date = parse_date(request.query_params.get('end_date') or '') or start_date
        if end_date < start_date:
            return Response({'detail': 'end_date must be on or after start_date.'}, status=status.HTTP_400_BAD_REQUEST)

        employee_id = request.query_params.get('employee_id')
        asset_id = request.query_params.get('asset_id')

        limit = int(request.query_params.get('limit', 500))
        try:
            devices = normalize_devices_with_groups(get_client(connection), limit=limit)
        except SureMDMError as exc:
            response_status = status.HTTP_401_UNAUTHORIZED if exc.status_code == 401 else status.HTTP_400_BAD_REQUEST
            return Response({'detail': str(exc)}, status=response_status)

        selected_device_ids = set()
        selected_employee = None
        selected_asset = None
        resolved_mdm_asset = None
        if employee_id:
            from apps.employees.models import Employee

            employee = Employee.objects.prefetch_related('asset_allocations__asset').filter(pk=employee_id).first()
            if employee:
                selected_employee = {
                    'id': employee.id,
                    'employee_id': employee.employee_id,
                    'full_name': employee.full_name,
                }
                active_allocations = [allocation for allocation in employee.asset_allocations.all() if allocation.status == 'active']
                active_allocation = next(
                    (
                        allocation
                        for allocation in active_allocations
                        if allocation.asset and is_laptop_asset(allocation.asset)
                    ),
                    None,
                ) or (active_allocations[0] if active_allocations else None)
                if active_allocation and active_allocation.asset:
                    asset = active_allocation.asset
                    resolved_mdm_asset = find_suremdm_asset_for_employee_asset(asset)
                    selected_asset = {
                        'id': asset.id,
                        'asset_id': asset.asset_id,
                        'asset_type': asset.asset_type.name if asset.asset_type_id else '',
                        'serial_number': asset.serial_number,
                    }
                    if resolved_mdm_asset:
                        selected_asset = {
                            'id': resolved_mdm_asset.id,
                            'asset_id': resolved_mdm_asset.asset_id,
                            'asset_type': resolved_mdm_asset.asset_type.name if resolved_mdm_asset.asset_type_id else '',
                            'serial_number': resolved_mdm_asset.serial_number,
                        }
                    selected_device_ids.update(
                        filter(
                            None,
                            {
                                resolved_mdm_asset.asset_id if resolved_mdm_asset else '',
                                resolved_mdm_asset.serial_number if resolved_mdm_asset else '',
                                resolved_mdm_asset.attribute_values.get('suremdm_device_id')
                                if resolved_mdm_asset and isinstance(resolved_mdm_asset.attribute_values, dict)
                                else '',
                                resolved_mdm_asset.attribute_values.get('device_name')
                                if resolved_mdm_asset and isinstance(resolved_mdm_asset.attribute_values, dict)
                                else '',
                                asset.asset_id,
                                asset.serial_number,
                                active_allocation.asset.attribute_values.get('suremdm_device_id')
                                if isinstance(active_allocation.asset.attribute_values, dict)
                                else '',
                                active_allocation.asset.attribute_values.get('device_name')
                                if isinstance(active_allocation.asset.attribute_values, dict)
                                else '',
                            },
                        )
                    )

        if asset_id:
            selected_device_ids.add(asset_id)

        if selected_device_ids:
            devices = [
                device for device in devices
                if str(device.get('suremdm_device_id')) in {str(value) for value in selected_device_ids}
                or str(device.get('serial_number')) in {str(value) for value in selected_device_ids}
                or str(device.get('name')) in {str(value) for value in selected_device_ids}
            ]

        if selected_employee and not selected_asset:
            devices = []

        results = []
        total_minutes = 0.0
        for day in build_date_range(start_date, end_date):
            for device in devices[:1]:
                minutes, source_value = extract_active_minutes(device)
                total_minutes += minutes
                active_from = f'{day.isoformat()}T09:00:00'
                active_to = device['last_seen'] or f'{day.isoformat()}T18:00:00'
                results.append(
                    {
                        'date': day.isoformat(),
                        'device_id': device['suremdm_device_id'],
                        'suremdm_device_id': device['suremdm_device_id'],
                        'asset_id': selected_asset['asset_id'] if selected_asset else '',
                        'name': device['name'],
                        'serial_number': device['serial_number'],
                        'platform': device['platform'],
                        'model': device['model'],
                        'category': device['category'],
                        'active_from': active_from,
                        'logged_off_at': active_to,
                        'active_minutes': round(minutes, 2),
                        'active_hours': round(minutes / 60, 2),
                        'activity_source': 'api_field' if source_value else 'last_seen_only',
                        'raw_activity_value': source_value,
                    }
                )

        if not results and selected_employee and selected_asset:
            results.append(
                {
                    'date': start_date.isoformat(),
                    'device_id': selected_asset['asset_id'],
                    'suremdm_device_id': selected_asset['asset_id'],
                    'asset_id': selected_asset['asset_id'],
                    'name': selected_asset['asset_id'],
                    'serial_number': selected_asset.get('serial_number', ''),
                    'platform': '',
                    'model': '',
                    'category': 'Uncategorized',
                    'active_from': '',
                    'logged_off_at': '',
                    'active_minutes': 0.0,
                    'active_hours': 0.0,
                    'activity_source': 'asset_lookup_only',
                    'raw_activity_value': '',
                }
            )

        return Response(
            {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'total_devices': len(results),
                'total_active_minutes': round(total_minutes, 2),
                'selected_employee': selected_employee,
                'selected_asset': selected_asset,
                'results': results,
            }
        )

    @action(detail=False, methods=['post'], url_path='sync-assets')
    def sync_assets(self, request):
        connection, error = self._configured_connection()
        if error:
            return error

        try:
            devices = normalize_devices_with_groups(get_client(connection), limit=500)
        except SureMDMError as exc:
            response_status = status.HTTP_401_UNAUTHORIZED if exc.status_code == 401 else status.HTTP_400_BAD_REQUEST
            return Response({'detail': str(exc)}, status=response_status)
        asset_type, _ = AssetType.objects.get_or_create(
            name='SureMDM Device',
            defaults={'asset_type': 'hardware', 'description': 'Devices synced from SureMDM'},
        )

        created = 0
        updated = 0
        with transaction.atomic():
            for device in devices:
                external_id = device['suremdm_device_id'] or device['serial_number'] or device['name']
                if not external_id:
                    continue

                asset_id = f'SUREMDM-{external_id}'
                defaults = {
                    'asset_type': asset_type,
                    'serial_number': device['serial_number'],
                    'vendor': 'SureMDM',
                    'status': 'available',
                    'notes': device['name'],
                    'attribute_values': {
                        'suremdm_device_id': device['suremdm_device_id'],
                        'device_name': device['name'],
                        'system_tag': device['system_tag'],
                        'platform': device['platform'],
                        'model': device['model'],
                        'category': device['category'],
                        'last_seen': device['last_seen'],
                        'processor': device['processor'],
                        'ram': device['ram'],
                        'storage': device['storage'],
                        'manufacturer': device['manufacturer'],
                    },
                }
                _, was_created = Asset.objects.update_or_create(asset_id=asset_id, defaults=defaults)
                created += 1 if was_created else 0
                updated += 0 if was_created else 1

            connection.last_synced_at = timezone.now()
            connection.save(update_fields=['last_synced_at', 'updated_at'])

        return Response({'created': created, 'updated': updated, 'total': created + updated})
