from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.integrations.suremdm import SureMDMError
from apps.integrations.views import get_client, get_connection, normalize_devices_with_groups
from apps.inventory.models import InstalledApplication, InstalledAppReportImport
from apps.inventory.views import (
    AUTO_SYNC_FILE_NAME_PREFIX,
    embedded_device_apps,
    normalize_installed_app,
    normalize_match_value,
)


class Command(BaseCommand):
    help = (
        'Pulls installed-application inventory from SureMDM for every known device and '
        'requests a fresh report from each device for the next run. Intended to run on a '
        'recurring schedule (e.g. Windows Task Scheduler) so the IT Assets device dashboard '
        'stays current without anyone downloading/uploading a SureMDM report by hand.'
    )

    def handle(self, *args, **options):
        connection = get_connection()
        if not connection or not connection.is_active:
            self.stdout.write(self.style.WARNING('SureMDM is not configured; skipping sync.'))
            return

        client = get_client(connection)
        try:
            devices = normalize_devices_with_groups(client, limit=1000)
        except SureMDMError as exc:
            self.stderr.write(self.style.ERROR(f'Could not reach SureMDM: {exc}'))
            return

        app_rows = []
        refreshed = 0
        for device in devices:
            device_id = device.get('suremdm_device_id')
            device_name = device.get('name') or device.get('system_tag') or device.get('serial_number')

            if device_name:
                raw_apps = embedded_device_apps(device)
                if not raw_apps and device_id:
                    try:
                        raw_apps = client.installed_apps(device_id)
                    except SureMDMError:
                        raw_apps = []

                normalized_device_name = normalize_match_value(device_name)
                for raw_app in raw_apps:
                    normalized = normalize_installed_app(raw_app)
                    if not normalized['name']:
                        continue
                    app_rows.append({
                        'device_name': device_name,
                        'normalized_device_name': normalized_device_name,
                        'application_package': normalized['application_package'],
                        'application_name': normalized['name'],
                        'application_type': normalized['application_type'],
                        'user_name': normalized['user_name'],
                        'application_version': normalized['version'],
                        'signature_key_hash': '',
                    })

            # Ask the device to report its app list again so the *next*
            # scheduled run has fresh data to harvest above.
            if device_id:
                try:
                    client.trigger_apps_refresh(device_id)
                    refreshed += 1
                except SureMDMError:
                    pass

        if app_rows:
            device_names = {row['device_name'] for row in app_rows}
            normalized_device_names = {row['normalized_device_name'] for row in app_rows}
            with transaction.atomic():
                report_import = InstalledAppReportImport.objects.create(
                    file_name=f'{AUTO_SYNC_FILE_NAME_PREFIX} {timezone.now():%Y-%m-%d %H:%M}',
                    imported_by=None,
                    device_count=len(device_names),
                    app_count=len(app_rows),
                )
                InstalledApplication.objects.filter(
                    normalized_device_name__in=normalized_device_names
                ).delete()
                InstalledApplication.objects.bulk_create(
                    [InstalledApplication(report_import=report_import, **row) for row in app_rows],
                    batch_size=1000,
                )
            self.stdout.write(self.style.SUCCESS(
                f'Synced {len(app_rows)} installed applications across {len(device_names)} devices; '
                f'requested a refresh from {refreshed} devices for the next run.'
            ))
        else:
            self.stdout.write(self.style.WARNING(
                f'No installed-application data was available from SureMDM yet; requested a refresh '
                f'from {refreshed} devices. Run again after they have had time to check in.'
            ))

        connection.last_synced_at = timezone.now()
        connection.save(update_fields=['last_synced_at', 'updated_at'])
