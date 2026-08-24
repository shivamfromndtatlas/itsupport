from django.db import models, transaction
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet, ViewSet

from apps.inventory.models import Asset, AssetType
from apps.users.permissions import IsITSpecialistOrSuperAdmin

from .models import SureMDMConnection, SynthesiaConnection, SynthesiaInvoice, TeamViewerConnection, TrellixConnection
from .serializers import (
    SureMDMConnectionSerializer,
    SynthesiaConnectionSerializer,
    SynthesiaInvoiceSerializer,
    TeamViewerConnectionSerializer,
    TrellixConnectionSerializer,
)
from .suremdm import SureMDMClient, SureMDMError
from .synthesia import SynthesiaClient, SynthesiaError
from .teamviewer import TeamViewerClient, TeamViewerError
from .trellix import TrellixClient, TrellixError


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


def parse_device_timestamp(value):
    if not value:
        return None
    if isinstance(value, (int, float)):
        try:
            # Support epoch values from MDM payloads.
            dt = datetime.fromtimestamp(float(value), tz=timezone.get_current_timezone())
        except (OverflowError, OSError, ValueError):
            return None
        return dt

    text = str(value).strip()
    if not text:
        return None

    dt = parse_datetime(text)
    if dt is None:
        normalized = text.replace('Z', '+00:00')
        candidate_formats = (
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d %I:%M:%S %p',
            '%d/%m/%Y %H:%M:%S',
            '%d/%m/%Y %I:%M:%S %p',
            '%d/%m/%Y, %I:%M:%S %p',
            '%d-%m-%Y %H:%M:%S',
            '%d-%m-%Y %I:%M:%S %p',
            '%m/%d/%Y %H:%M:%S',
            '%m/%d/%Y %I:%M:%S %p',
            '%b %d %Y %I:%M:%S %p',
            '%b %d, %Y %I:%M:%S %p',
            '%d %b %Y %I:%M:%S %p',
            '%Y/%m/%d %H:%M:%S',
        )
        dt = None
        for fmt in candidate_formats:
            try:
                dt = datetime.strptime(normalized, fmt)
                break
            except ValueError:
                continue
        if dt is None:
            return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def _normalize_lookup(value):
    return str(value or '').strip().lower()


def format_suremdm_datetime(dt):
    return dt.astimezone(dt_timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')


DEVICE_LOG_ONLINE_MESSAGE = '1'
DEVICE_LOG_OFFLINE_MESSAGE = '0'


def fetch_device_online_intervals(client, device_id, range_start, range_end):
    """
    Pull real online/offline session events for a device from SureMDM's
    device activity log (POST /devicelog/) and pair them into intervals.

    SureMDM's basic device-list API carries no session/duration data at
    all, so this is the only source of truth for how long a device was
    actually online in a given window.
    """
    if not device_id:
        return []

    try:
        rows = client.device_log(
            device_id,
            format_suremdm_datetime(range_start),
            format_suremdm_datetime(range_end),
        )
    except SureMDMError:
        return []

    events = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        message = str(row.get('Message') or '').strip()
        if message not in (DEVICE_LOG_ONLINE_MESSAGE, DEVICE_LOG_OFFLINE_MESSAGE):
            continue
        event_time = parse_device_timestamp(row.get('Time'))
        if not event_time:
            continue
        events.append((event_time, message))
    events.sort(key=lambda item: item[0])

    intervals = []
    open_start = None
    for event_time, message in events:
        if message == DEVICE_LOG_ONLINE_MESSAGE:
            if open_start is None:
                open_start = event_time
        elif message == DEVICE_LOG_OFFLINE_MESSAGE and open_start is not None:
            if event_time > open_start:
                intervals.append({'start': open_start, 'end': event_time})
            open_start = None

    if open_start is not None:
        # Device is still online with no offline event yet in this window.
        still_online_until = min(timezone.now(), range_end)
        if still_online_until > open_start:
            intervals.append({'start': open_start, 'end': still_online_until})

    return intervals


def split_interval_by_local_day(start_dt, end_dt):
    """Split [start_dt, end_dt) into per-local-calendar-day chunks."""
    current = start_dt
    while current < end_dt:
        local_date = timezone.localtime(current).date()
        next_local_midnight = timezone.make_aware(
            datetime.combine(local_date + timedelta(days=1), datetime.min.time()),
            timezone.get_current_timezone(),
        )
        chunk_end = min(end_dt, next_local_midnight)
        if chunk_end > current:
            yield local_date, current, chunk_end
        current = chunk_end


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
        client = get_client(connection)
        try:
            devices = normalize_devices_with_groups(client, limit=limit)
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
                active_allocation = None
                laptop_allocations = [
                    allocation
                    for allocation in active_allocations
                    if allocation.asset and is_laptop_asset(allocation.asset)
                ]
                for allocation in laptop_allocations:
                    if find_suremdm_asset_for_employee_asset(allocation.asset):
                        active_allocation = allocation
                        break
                if active_allocation is None:
                    active_allocation = laptop_allocations[0] if laptop_allocations else (active_allocations[0] if active_allocations else None)
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

        range_start = timezone.make_aware(
            datetime.combine(start_date, datetime.min.time()), timezone.get_current_timezone()
        )
        range_end = timezone.make_aware(
            datetime.combine(end_date + timedelta(days=1), datetime.min.time()), timezone.get_current_timezone()
        )

        daily_sessions = {}
        for device in devices:
            intervals = fetch_device_online_intervals(client, device['suremdm_device_id'], range_start, range_end)
            for interval in intervals:
                for day, chunk_start, chunk_end in split_interval_by_local_day(interval['start'], interval['end']):
                    if day < start_date or day > end_date:
                        continue
                    minutes = (chunk_end - chunk_start).total_seconds() / 60
                    key = (day, device['suremdm_device_id'])
                    daily_sessions.setdefault(key, []).append(
                        {
                            'device': device,
                            'active_from': chunk_start,
                            'logged_off_at': chunk_end,
                            'active_minutes': minutes,
                        }
                    )

        results = []
        total_minutes = 0.0
        for (day, device_id), sessions in daily_sessions.items():
            sessions.sort(key=lambda session: session['active_from'])
            day_minutes = sum(session['active_minutes'] for session in sessions)
            for session in sessions:
                device = session['device']
                minutes = session['active_minutes']
                total_minutes += minutes
                results.append(
                    {
                        'date': day.isoformat(),
                        'device_id': device_id,
                        'suremdm_device_id': device_id,
                        'asset_id': selected_asset['asset_id'] if selected_asset else '',
                        'name': device['name'],
                        'serial_number': device['serial_number'],
                        'platform': device['platform'],
                        'model': device['model'],
                        'category': device['category'],
                        'active_from': session['active_from'].isoformat(),
                        'logged_off_at': session['logged_off_at'].isoformat(),
                        'active_minutes': round(minutes, 2),
                        'active_hours': round(minutes / 60, 2),
                        'day_active_minutes': round(day_minutes, 2),
                        'day_active_hours': round(day_minutes / 60, 2),
                        'activity_source': 'online_status_log',
                        'raw_activity_value': '',
                    }
                )

        results.sort(key=lambda row: (row['date'], row['active_from']), reverse=True)

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
                    'day_active_minutes': 0.0,
                    'day_active_hours': 0.0,
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



def get_teamviewer_connection():
    return TeamViewerConnection.objects.order_by('-updated_at').first()


def get_teamviewer_client(connection):
    return TeamViewerClient(base_url=connection.base_url, api_token=connection.api_token)


TEAMVIEWER_MANAGED_GROUPS_WARNING = (
    'This token cannot see TeamViewer Managed Groups (Remote Management devices), so only classic '
    'Computers & Contacts devices are listed. Grant it managed-group visibility in the TeamViewer '
    'Management Console to include managed devices here.'
)


def normalize_teamviewer_device(device):
    return {
        'teamviewer_device_id': str(device.get('device_id') or ''),
        'teamviewer_id': str(device.get('teamviewer_id') or device.get('remotecontrol_id') or ''),
        'name': device.get('alias') or '',
        'description': device.get('description') or '',
        'group_id': str(device.get('groupid') or ''),
        'online_state': device.get('online_state') or 'Unknown',
        'assigned_to': bool(device.get('assigned_to')),
        'last_seen': device.get('last_seen') or '',
        'supported_features': device.get('supported_features') or '',
        'source': 'classic' if device.get('remotecontrol_id') else 'managed',
        'raw': device,
    }


class TeamViewerConnectionView(APIView):
    permission_classes = [IsITSpecialistOrSuperAdmin]

    def get(self, request):
        connection = get_teamviewer_connection()
        if not connection:
            return Response({'configured': False})
        data = TeamViewerConnectionSerializer(connection).data
        data['configured'] = True
        return Response(data)

    def post(self, request):
        connection = get_teamviewer_connection()
        serializer = TeamViewerConnectionSerializer(
            connection,
            data=request.data,
            partial=bool(connection),
        )
        serializer.is_valid(raise_exception=True)
        connection = serializer.save()
        data = TeamViewerConnectionSerializer(connection).data
        data['configured'] = True
        return Response(data, status=status.HTTP_200_OK)


class TeamViewerViewSet(ViewSet):
    permission_classes = [IsITSpecialistOrSuperAdmin]

    def _configured_connection(self):
        connection = get_teamviewer_connection()
        if not connection or not connection.is_active:
            return None, Response(
                {'detail': 'TeamViewer is not configured.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not connection.api_token:
            return None, Response(
                {'detail': 'TeamViewer API token is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return connection, None

    @action(detail=False, methods=['post'], url_path='test')
    def test(self, request):
        connection, error = self._configured_connection()
        if error:
            return error

        try:
            client = get_teamviewer_client(connection)
            token_valid = client.ping()
            connection.last_test_status = 'success' if token_valid else 'failed'
            message = (
                'Connected to TeamViewer successfully.'
                if token_valid
                else 'TeamViewer reported this token as invalid.'
            )
            if token_valid:
                try:
                    client.list_managed_groups()
                except TeamViewerError:
                    message = f'{message} {TEAMVIEWER_MANAGED_GROUPS_WARNING}'
            connection.last_test_message = message
            response_status = status.HTTP_200_OK if token_valid else status.HTTP_401_UNAUTHORIZED
        except TeamViewerError as exc:
            connection.last_test_status = 'failed'
            connection.last_test_message = str(exc)
            response_status = status.HTTP_401_UNAUTHORIZED if exc.status_code == 401 else status.HTTP_400_BAD_REQUEST

        connection.last_tested_at = timezone.now()
        connection.save(update_fields=['last_tested_at', 'last_test_status', 'last_test_message', 'updated_at'])
        return Response(
            {'status': connection.last_test_status, 'message': connection.last_test_message},
            status=response_status,
        )

    @action(detail=False, methods=['get'], url_path='devices')
    def devices(self, request):
        connection, error = self._configured_connection()
        if error:
            return error
        limit = int(request.query_params.get('limit', 200))
        try:
            raw_devices, managed_groups_error = get_teamviewer_client(connection).list_devices(limit=limit)
        except TeamViewerError as exc:
            response_status = status.HTTP_401_UNAUTHORIZED if exc.status_code == 401 else status.HTTP_400_BAD_REQUEST
            return Response({'detail': str(exc)}, status=response_status)
        devices = [normalize_teamviewer_device(device) for device in raw_devices]
        payload = {'count': len(devices), 'results': devices}
        if managed_groups_error:
            payload['managed_groups_warning'] = TEAMVIEWER_MANAGED_GROUPS_WARNING
        return Response(payload)

    @action(detail=False, methods=['get'], url_path='summary')
    def summary(self, request):
        connection, error = self._configured_connection()
        if error:
            return error
        try:
            raw_devices, managed_groups_error = get_teamviewer_client(connection).list_devices()
        except TeamViewerError as exc:
            response_status = status.HTTP_401_UNAUTHORIZED if exc.status_code == 401 else status.HTTP_400_BAD_REQUEST
            return Response({'detail': str(exc)}, status=response_status)
        devices = [normalize_teamviewer_device(device) for device in raw_devices]

        online_counts = {}
        source_counts = {}
        for device in devices:
            state = device['online_state']
            online_counts[state] = online_counts.get(state, 0) + 1
            source_counts[device['source']] = source_counts.get(device['source'], 0) + 1

        payload = {
            'total_devices': len(devices),
            'online_states': [
                {'online_state': name, 'count': count}
                for name, count in sorted(online_counts.items())
            ],
            'sources': [
                {'source': name, 'count': count}
                for name, count in sorted(source_counts.items())
            ],
        }
        if managed_groups_error:
            payload['managed_groups_warning'] = TEAMVIEWER_MANAGED_GROUPS_WARNING
        return Response(payload)


# Synthesia bills 2 credits per second of finished video (per Synthesia's
# published credit-usage rate), and the API doesn't return a per-video
# credit figure directly, so it's derived from `duration` on each video.
SYNTHESIA_CREDITS_PER_SECOND = 2


def get_synthesia_connection():
    return SynthesiaConnection.objects.order_by('-updated_at').first()


def get_synthesia_client(connection):
    return SynthesiaClient(base_url=connection.base_url, api_key=connection.api_key)


def format_synthesia_duration(seconds):
    if seconds is None:
        return ''
    total_seconds = int(round(seconds))
    minutes, secs = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f'{hours}:{minutes:02d}:{secs:02d}'
    return f'{minutes}:{secs:02d}'


def parse_synthesia_duration_seconds(value):
    if value in (None, ''):
        return None
    text = str(value).strip()
    parts = text.split(':')
    try:
        if len(parts) == 3:
            hours, minutes, seconds = parts
        elif len(parts) == 2:
            hours, (minutes, seconds) = '0', parts
        else:
            return float(text)
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    except (TypeError, ValueError):
        return None


def normalize_synthesia_video(video):
    duration_seconds = parse_synthesia_duration_seconds(video.get('duration'))

    credits_used = round(duration_seconds * SYNTHESIA_CREDITS_PER_SECOND) if duration_seconds is not None else None

    created_at = video.get('createdAt')
    last_updated_at = video.get('lastUpdatedAt')

    return {
        'video_id': video.get('id'),
        'title': video.get('title') or 'Untitled video',
        'description': video.get('description') or '',
        'status': video.get('status') or '',
        'visibility': video.get('visibility') or '',
        'duration_seconds': duration_seconds,
        'duration_display': format_synthesia_duration(duration_seconds),
        'credits_used': credits_used,
        'created_at': datetime.fromtimestamp(created_at, tz=dt_timezone.utc).isoformat() if created_at else '',
        'last_updated_at': datetime.fromtimestamp(last_updated_at, tz=dt_timezone.utc).isoformat() if last_updated_at else '',
        'is_test': bool(video.get('test')),
        'download_url': video.get('download') or '',
        'thumbnail_url': (video.get('thumbnail') or {}).get('image') or '',
        'raw': video,
    }


class SynthesiaConnectionView(APIView):
    permission_classes = [IsITSpecialistOrSuperAdmin]

    def get(self, request):
        connection = get_synthesia_connection()
        if not connection:
            return Response({'configured': False})
        data = SynthesiaConnectionSerializer(connection).data
        data['configured'] = True
        return Response(data)

    def post(self, request):
        connection = get_synthesia_connection()
        serializer = SynthesiaConnectionSerializer(
            connection,
            data=request.data,
            partial=bool(connection),
        )
        serializer.is_valid(raise_exception=True)
        connection = serializer.save()
        data = SynthesiaConnectionSerializer(connection).data
        data['configured'] = True
        return Response(data, status=status.HTTP_200_OK)


class SynthesiaViewSet(ViewSet):
    permission_classes = [IsITSpecialistOrSuperAdmin]

    def _configured_connection(self):
        connection = get_synthesia_connection()
        if not connection or not connection.is_active:
            return None, Response(
                {'detail': 'Synthesia is not configured.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not connection.api_key:
            return None, Response(
                {'detail': 'Synthesia API key is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return connection, None

    @action(detail=False, methods=['post'], url_path='test')
    def test(self, request):
        connection, error = self._configured_connection()
        if error:
            return error

        try:
            videos, _ = get_synthesia_client(connection).list_videos(limit=1)
            connection.last_test_status = 'success'
            connection.last_test_message = 'Connected to Synthesia successfully.'
            response_status = status.HTTP_200_OK
        except SynthesiaError as exc:
            videos = []
            connection.last_test_status = 'failed'
            connection.last_test_message = str(exc)
            response_status = status.HTTP_401_UNAUTHORIZED if exc.status_code == 401 else status.HTTP_400_BAD_REQUEST

        connection.last_tested_at = timezone.now()
        connection.save(update_fields=['last_tested_at', 'last_test_status', 'last_test_message', 'updated_at'])
        return Response(
            {
                'status': connection.last_test_status,
                'message': connection.last_test_message,
                'sample_video_count': len(videos),
            },
            status=response_status,
        )

    @action(detail=False, methods=['get'], url_path='videos')
    def videos(self, request):
        connection, error = self._configured_connection()
        if error:
            return error
        limit = int(request.query_params.get('limit', 500))
        try:
            videos = [
                normalize_synthesia_video(video)
                for video in get_synthesia_client(connection).list_all_videos(max_videos=limit)
            ]
        except SynthesiaError as exc:
            response_status = status.HTTP_401_UNAUTHORIZED if exc.status_code == 401 else status.HTTP_400_BAD_REQUEST
            return Response({'detail': str(exc)}, status=response_status)

        connection.last_synced_at = timezone.now()
        connection.save(update_fields=['last_synced_at', 'updated_at'])
        return Response({'count': len(videos), 'results': videos})

    @action(detail=False, methods=['get'], url_path='summary')
    def summary(self, request):
        connection, error = self._configured_connection()
        if error:
            return error
        limit = int(request.query_params.get('limit', 500))
        try:
            videos = [
                normalize_synthesia_video(video)
                for video in get_synthesia_client(connection).list_all_videos(max_videos=limit)
            ]
        except SynthesiaError as exc:
            response_status = status.HTTP_401_UNAUTHORIZED if exc.status_code == 401 else status.HTTP_400_BAD_REQUEST
            return Response({'detail': str(exc)}, status=response_status)

        published = [video for video in videos if video['status'] == 'complete']
        total_credits = sum(video['credits_used'] or 0 for video in videos)
        total_duration_seconds = sum(video['duration_seconds'] or 0 for video in videos)

        status_counts = {}
        for video in videos:
            key = video['status'] or 'unknown'
            status_counts[key] = status_counts.get(key, 0) + 1

        # The current billing cycle's start isn't tracked separately - the
        # most recent logged invoice's payment date is the actual ground
        # truth for when the current plan period began.
        latest_invoice = connection.invoices.order_by('-payment_date').first()
        cycle_started_on = latest_invoice.payment_date if latest_invoice else None
        # This is a floor, not the true figure: it only sums credits for
        # videos visible through this API key, but Synthesia bills credits
        # against a shared pool that also covers dubbing, personalization,
        # and re-renders, none of which show up in the videos list. Use
        # connection.credits_used_override (copied by hand from the
        # Synthesia dashboard) as the real number whenever it's set.
        estimated_credits_used_this_cycle = None
        videos_edited_this_cycle = []
        if cycle_started_on:
            cycle_start_iso = cycle_started_on.isoformat()
            estimated_credits_used_this_cycle = sum(
                video['credits_used'] or 0
                for video in videos
                if video['created_at'] and video['created_at'][:10] >= cycle_start_iso
            )
            # Editing an existing video (e.g. re-rendering a changed scene)
            # consumes credits again without touching createdAt, so it's
            # invisible to the sum above. Surfacing these separately at
            # least explains where some of the gap to the real dashboard
            # figure is likely coming from, even though the exact partial-
            # render cost isn't available without Synthesia's audit logs.
            videos_edited_this_cycle = [
                {
                    'video_id': video['video_id'],
                    'title': video['title'],
                    'last_updated_at': video['last_updated_at'],
                    'duration_display': video['duration_display'],
                    'credits_used': video['credits_used'],
                }
                for video in videos
                if video['last_updated_at']
                and video['last_updated_at'][:10] >= cycle_start_iso
                and not (video['created_at'] and video['created_at'][:10] >= cycle_start_iso)
            ]

        credits_used_this_cycle = (
            connection.credits_used_override
            if connection.credits_used_override is not None
            else estimated_credits_used_this_cycle
        )
        credits_remaining = None
        if connection.credit_allowance is not None and credits_used_this_cycle is not None:
            credits_remaining = connection.credit_allowance - credits_used_this_cycle

        return Response(
            {
                'total_videos': len(videos),
                'published_videos': len(published),
                'total_credits_used': total_credits,
                'total_duration_seconds': round(total_duration_seconds, 2),
                'total_duration_display': format_synthesia_duration(total_duration_seconds),
                'status_counts': [
                    {'status': name, 'count': count}
                    for name, count in sorted(status_counts.items())
                ],
                'plan_name': connection.plan_name,
                'billing_period': connection.billing_period,
                'credit_allowance': connection.credit_allowance,
                'billing_cycle_renews_on': connection.billing_cycle_renews_on,
                'billing_cycle_started_on': cycle_started_on,
                'credits_used_this_cycle': credits_used_this_cycle,
                'credits_used_is_estimate': connection.credits_used_override is None,
                'estimated_credits_used_this_cycle': estimated_credits_used_this_cycle,
                'videos_edited_this_cycle': videos_edited_this_cycle,
                'credits_used_override_at': connection.credits_used_override_at,
                'credits_remaining': credits_remaining,
            }
        )


class SynthesiaInvoiceViewSet(ModelViewSet):
    permission_classes = [IsITSpecialistOrSuperAdmin]
    serializer_class = SynthesiaInvoiceSerializer
    queryset = SynthesiaInvoice.objects.all()

    def get_queryset(self):
        connection = get_synthesia_connection()
        if not connection:
            return SynthesiaInvoice.objects.none()
        return SynthesiaInvoice.objects.filter(connection=connection)

    def perform_create(self, serializer):
        connection = get_synthesia_connection()
        if not connection:
            raise DRFValidationError('Synthesia is not configured.')
        serializer.save(connection=connection)


TRELLIX_ID_KEYS = ('deviceId', 'DeviceId', 'systemId', 'SystemId', 'id', 'ID')
TRELLIX_NAME_KEYS = ('deviceName', 'DeviceName', 'systemName', 'SystemName', 'hostName', 'HostName', 'name', 'Name')
TRELLIX_SERIAL_KEYS = ('serialNumber', 'SerialNumber', 'serial', 'Serial')
TRELLIX_PLATFORM_KEYS = ('platform', 'Platform', 'osType', 'OSType', 'os', 'OS', 'operatingSystem')
TRELLIX_OS_VERSION_KEYS = ('osVersion', 'OSVersion', 'version', 'Version')
TRELLIX_IP_KEYS = ('ipAddress', 'IPAddress', 'ip', 'IP')
TRELLIX_AGENT_VERSION_KEYS = ('agentVersion', 'AgentVersion', 'productVersion', 'ProductVersion')
TRELLIX_LAST_COMM_KEYS = ('lastCommunication', 'LastCommunication', 'lastContact', 'LastContact', 'lastSeen', 'LastSeen')
TRELLIX_THREAT_STATUS_KEYS = ('threatStatus', 'ThreatStatus', 'protectionStatus', 'ProtectionStatus', 'status', 'Status')

TRELLIX_EVENT_ID_KEYS = ('eventId', 'EventId', 'id', 'ID')
TRELLIX_THREAT_NAME_KEYS = ('threatName', 'ThreatName', 'malwareName', 'MalwareName', 'detectionName', 'DetectionName')
TRELLIX_THREAT_TYPE_KEYS = ('threatType', 'ThreatType', 'category', 'Category')
TRELLIX_SEVERITY_KEYS = ('severity', 'Severity', 'threatSeverity', 'ThreatSeverity')
TRELLIX_ACTION_KEYS = ('actionTaken', 'ActionTaken', 'action', 'Action')
TRELLIX_DETECTED_AT_KEYS = ('detectedAt', 'DetectedAt', 'eventTime', 'EventTime', 'timestamp', 'Timestamp')


def get_trellix_connection():
    return TrellixConnection.objects.order_by('-updated_at').first()


def get_trellix_client(connection):
    return TrellixClient(
        base_url=connection.base_url,
        auth_url=connection.auth_url,
        client_id=connection.client_id,
        client_secret=connection.client_secret,
        api_key=connection.api_key,
        tenant_id=connection.tenant_id,
        scope=connection.scope,
    )


def normalize_trellix_device(device):
    device_id = device_value(device, *TRELLIX_ID_KEYS)
    return {
        'trellix_device_id': str(device_id),
        'name': device_value(device, *TRELLIX_NAME_KEYS),
        'serial_number': device_value(device, *TRELLIX_SERIAL_KEYS),
        'platform': device_value(device, *TRELLIX_PLATFORM_KEYS),
        'os_version': device_value(device, *TRELLIX_OS_VERSION_KEYS),
        'ip_address': device_value(device, *TRELLIX_IP_KEYS),
        'agent_version': device_value(device, *TRELLIX_AGENT_VERSION_KEYS),
        'last_communication': device_value(device, *TRELLIX_LAST_COMM_KEYS),
        'threat_status': device_value(device, *TRELLIX_THREAT_STATUS_KEYS) or 'Unknown',
        'raw': device,
    }


def normalize_trellix_threat_event(event):
    return {
        'event_id': str(device_value(event, *TRELLIX_EVENT_ID_KEYS)),
        'device_name': device_value(event, *TRELLIX_NAME_KEYS),
        'threat_name': device_value(event, *TRELLIX_THREAT_NAME_KEYS),
        'threat_type': device_value(event, *TRELLIX_THREAT_TYPE_KEYS),
        'severity': device_value(event, *TRELLIX_SEVERITY_KEYS),
        'action_taken': device_value(event, *TRELLIX_ACTION_KEYS),
        'detected_at': device_value(event, *TRELLIX_DETECTED_AT_KEYS),
        'raw': event,
    }


class TrellixConnectionView(APIView):
    permission_classes = [IsITSpecialistOrSuperAdmin]

    def get(self, request):
        connection = get_trellix_connection()
        if not connection:
            return Response({'configured': False})
        data = TrellixConnectionSerializer(connection).data
        data['configured'] = True
        return Response(data)

    def post(self, request):
        connection = get_trellix_connection()
        serializer = TrellixConnectionSerializer(
            connection,
            data=request.data,
            partial=bool(connection),
        )
        serializer.is_valid(raise_exception=True)
        connection = serializer.save()
        data = TrellixConnectionSerializer(connection).data
        data['configured'] = True
        return Response(data, status=status.HTTP_200_OK)


class TrellixViewSet(ViewSet):
    permission_classes = [IsITSpecialistOrSuperAdmin]

    def _configured_connection(self):
        connection = get_trellix_connection()
        if not connection or not connection.is_active:
            return None, Response(
                {'detail': 'Trellix is not configured.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not connection.client_id or not connection.client_secret or not connection.api_key:
            return None, Response(
                {'detail': 'Trellix Client ID, Client Secret, and API key are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return connection, None

    @action(detail=False, methods=['post'], url_path='test')
    def test(self, request):
        connection, error = self._configured_connection()
        if error:
            return error

        try:
            devices = get_trellix_client(connection).list_devices(limit=1)
            connection.last_test_status = 'success'
            connection.last_test_message = 'Connected to Trellix successfully.'
            response_status = status.HTTP_200_OK
        except TrellixError as exc:
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
            devices = [
                normalize_trellix_device(device)
                for device in get_trellix_client(connection).list_devices(limit=limit)
            ]
        except TrellixError as exc:
            response_status = status.HTTP_401_UNAUTHORIZED if exc.status_code == 401 else status.HTTP_400_BAD_REQUEST
            return Response({'detail': str(exc)}, status=response_status)
        return Response({'count': len(devices), 'results': devices})

    @action(detail=False, methods=['get'], url_path='threats')
    def threats(self, request):
        connection, error = self._configured_connection()
        if error:
            return error
        limit = int(request.query_params.get('limit', 100))
        from_date = request.query_params.get('start_date') or None
        to_date = request.query_params.get('end_date') or None
        try:
            events = [
                normalize_trellix_threat_event(event)
                for event in get_trellix_client(connection).list_threat_events(
                    limit=limit, from_date=from_date, to_date=to_date
                )
            ]
        except TrellixError as exc:
            response_status = status.HTTP_401_UNAUTHORIZED if exc.status_code == 401 else status.HTTP_400_BAD_REQUEST
            return Response({'detail': str(exc)}, status=response_status)
        return Response({'count': len(events), 'results': events})

    @action(detail=False, methods=['post'], url_path='sync-assets')
    def sync_assets(self, request):
        connection, error = self._configured_connection()
        if error:
            return error

        try:
            devices = [
                normalize_trellix_device(device)
                for device in get_trellix_client(connection).list_devices(limit=500)
            ]
        except TrellixError as exc:
            response_status = status.HTTP_401_UNAUTHORIZED if exc.status_code == 401 else status.HTTP_400_BAD_REQUEST
            return Response({'detail': str(exc)}, status=response_status)

        asset_type, _ = AssetType.objects.get_or_create(
            name='Trellix Endpoint',
            defaults={'asset_type': 'hardware', 'description': 'Endpoints synced from Trellix'},
        )

        created = 0
        updated = 0
        with transaction.atomic():
            for device in devices:
                external_id = device['trellix_device_id'] or device['serial_number'] or device['name']
                if not external_id:
                    continue

                asset_id = f'TRELLIX-{external_id}'
                defaults = {
                    'asset_type': asset_type,
                    'serial_number': device['serial_number'],
                    'vendor': 'Trellix',
                    'status': 'available',
                    'notes': device['name'],
                    'attribute_values': {
                        'trellix_device_id': device['trellix_device_id'],
                        'device_name': device['name'],
                        'platform': device['platform'],
                        'os_version': device['os_version'],
                        'ip_address': device['ip_address'],
                        'agent_version': device['agent_version'],
                        'last_communication': device['last_communication'],
                        'threat_status': device['threat_status'],
                    },
                }
                _, was_created = Asset.objects.update_or_create(asset_id=asset_id, defaults=defaults)
                created += 1 if was_created else 0
                updated += 0 if was_created else 1

            connection.last_synced_at = timezone.now()
            connection.save(update_fields=['last_synced_at', 'updated_at'])

        return Response({'created': created, 'updated': updated, 'total': created + updated})
