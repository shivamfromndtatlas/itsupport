from django.db import transaction
from django.utils import timezone
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
