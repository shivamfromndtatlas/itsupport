from django.db import models


class TrellixConnection(models.Model):
    base_url = models.URLField(default='https://api.manage.trellix.com')
    auth_url = models.URLField(default='https://iam.cloud.trellix.com/iam/v1.0/token')
    tenant_name = models.CharField(max_length=200, blank=True)
    tenant_id = models.CharField(max_length=100, blank=True)
    client_id = models.CharField(max_length=200, blank=True)
    client_secret = models.CharField(max_length=500, blank=True)
    api_key = models.CharField(max_length=500, blank=True)
    scope = models.CharField(max_length=500, blank=True, default='epo.device.r')
    is_active = models.BooleanField(default=True)
    last_tested_at = models.DateTimeField(null=True, blank=True)
    last_test_status = models.CharField(max_length=20, blank=True)
    last_test_message = models.TextField(blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'trellix_connections'

    def __str__(self):
        return f'Trellix ({self.tenant_name or self.base_url})'


class SynthesiaConnection(models.Model):
    name = models.CharField(max_length=200, blank=True, help_text='Label for this Synthesia workspace, e.g. ATLAS.')
    base_url = models.URLField(default='https://api.synthesia.io/v2')
    api_key = models.CharField(max_length=500, blank=True)
    is_active = models.BooleanField(default=True)
    last_tested_at = models.DateTimeField(null=True, blank=True)
    last_test_status = models.CharField(max_length=20, blank=True)
    last_test_message = models.TextField(blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    # Synthesia's API exposes no plan/subscription endpoint, so these are
    # entered and kept up to date by hand rather than synced.
    plan_name = models.CharField(max_length=200, blank=True)
    billing_period = models.CharField(
        max_length=10,
        choices=[('monthly', 'Monthly'), ('annual', 'Annual')],
        default='annual',
    )
    credit_allowance = models.PositiveIntegerField(null=True, blank=True)
    billing_cycle_renews_on = models.DateField(null=True, blank=True)
    # True credit-consumption data lives behind Synthesia's Audit Logs API,
    # which is an Enterprise-only feature (confirmed against this Creator-plan
    # key: the endpoint itself responds, but there's no API route on this tier
    # to look up the workspaceId it requires). So this is copied by hand from
    # the "Usage" panel on the Synthesia dashboard rather than computed from
    # video durations, which undercounts real usage (dubbing, re-renders,
    # personalization, etc. all draw from the same credit pool).
    credits_used_override = models.PositiveIntegerField(null=True, blank=True)
    credits_used_override_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'synthesia_connections'

    def __str__(self):
        return f'Synthesia ({self.name or self.base_url})'


class SynthesiaInvoice(models.Model):
    # There's no Synthesia billing/invoice API either, so these are logged
    # by hand from the invoice emails Synthesia sends.
    connection = models.ForeignKey(SynthesiaConnection, on_delete=models.CASCADE, related_name='invoices')
    payment_date = models.DateField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=8, default='USD')
    invoice_number = models.CharField(max_length=100, blank=True)
    invoice_file = models.FileField(upload_to='synthesia_invoices/')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'synthesia_invoices'
        ordering = ['-payment_date', '-created_at']

    def __str__(self):
        return f'{self.payment_date} - {self.amount} {self.currency}'


class TeamViewerConnection(models.Model):
    name = models.CharField(max_length=200, blank=True, help_text='Label for this TeamViewer token, e.g. which account it belongs to.')
    base_url = models.URLField(default='https://webapi.teamviewer.com/api/v1')
    api_token = models.CharField(max_length=500, blank=True)
    is_active = models.BooleanField(default=True)
    last_tested_at = models.DateTimeField(null=True, blank=True)
    last_test_status = models.CharField(max_length=20, blank=True)
    last_test_message = models.TextField(blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'teamviewer_connections'

    def __str__(self):
        return f'TeamViewer ({self.name or self.base_url})'


class SureMDMConnection(models.Model):
    base_url = models.URLField(default='https://suremdm.42gears.com/api')
    username = models.CharField(max_length=200, blank=True)
    password = models.CharField(max_length=500, blank=True)
    api_key = models.CharField(max_length=500, blank=True)
    is_active = models.BooleanField(default=True)
    last_tested_at = models.DateTimeField(null=True, blank=True)
    last_test_status = models.CharField(max_length=20, blank=True)
    last_test_message = models.TextField(blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'suremdm_connections'

    def __str__(self):
        return f'SureMDM ({self.base_url})'
