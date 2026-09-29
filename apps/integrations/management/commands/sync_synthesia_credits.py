from django.core.management.base import BaseCommand

from apps.integrations.synthesia import SynthesiaError
from apps.integrations.views import get_synthesia_connection, sync_synthesia_credits


class Command(BaseCommand):
    help = (
        'Recomputes the estimated Synthesia credits used in the current billing '
        'cycle from video durations (2 credits/sec) and stores it on the '
        'connection. Synthesia exposes no credit-balance API on non-Enterprise '
        'plans, so this estimate is the automatic stand-in for the figure that '
        'was previously copied by hand from the Synthesia dashboard "Usage" '
        'panel. Intended to run on a recurring schedule (e.g. Windows Task '
        'Scheduler) so the Sure MDM page stays current on its own.'
    )

    def handle(self, *args, **options):
        connection = get_synthesia_connection()
        if not connection or not connection.is_active:
            self.stdout.write(self.style.WARNING('Synthesia is not configured; skipping sync.'))
            return
        if not connection.api_key:
            self.stdout.write(self.style.WARNING('Synthesia API key is missing; skipping sync.'))
            return

        try:
            estimated_credits_used, cycle_started_on = sync_synthesia_credits(connection)
        except SynthesiaError as exc:
            self.stderr.write(self.style.ERROR(f'Could not reach Synthesia: {exc}'))
            return

        if cycle_started_on is None:
            self.stdout.write(self.style.WARNING(
                'No Synthesia invoice is logged yet, so the billing-cycle start is unknown '
                'and credits used cannot be estimated. Add an invoice under Invoice History, '
                'then run this again.'
            ))
            return

        self.stdout.write(self.style.SUCCESS(
            f'Synced Synthesia credits: ~{estimated_credits_used} credits used since '
            f'{cycle_started_on:%Y-%m-%d} (billing-cycle start).'
        ))
