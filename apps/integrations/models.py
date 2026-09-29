from django.db import models


class TrellixConnection(models.Model):
    base_url = models.URLField(default='https://api.manage.trellix.com')
    auth_url = models.URLField(default='https://iam.cloud.trellix.com/iam/v1.0/token')
    tenant_name = models.CharField(max_length=200, blank=True)
    tenant_id = models.CharField(max_length=100, blank=True)
    client_id = models.CharField(max_length=200, blank=True)
    client_secret = models.CharField(max_length=500, blank=True)
    api_key = models.CharField(max_length=500, blank=True)
    scope = models.CharField(max_length=500, blank=True, default='epo.device.r epo.evt.r')
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
    # to look up the workspaceId it requires). As a self-updating stand-in,
    # `sync_synthesia_credits` recomputes an estimate on a schedule from video
    # durations (2 credits/sec) for everything created in the current billing
    # cycle. It's a floor: dubbing, re-renders and personalization all draw
    # from the same credit pool but never show up in the videos list.
    credits_used_estimated = models.PositiveIntegerField(null=True, blank=True)
    credits_used_synced_at = models.DateTimeField(null=True, blank=True)
    # Optional manual correction. When set, it wins over the auto estimate
    # above; copied by hand from the "Usage" panel on the Synthesia dashboard
    # when a pinpoint figure is needed. Clear it to fall back to the estimate.
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


class DellSupportConnection(models.Model):
    """
    Credentials for the Dell TechDirect / Dell APIs OAuth2 client used to look up
    a Dell asset's warranty entitlements and original shipped configuration by
    service tag. Dell's public support pages block automated access, so this is
    the supported path. Register at techdirect.dell.com -> APIs.
    """

    base_url = models.URLField(
        default='https://apigtwb2c.us.dell.com',
        help_text='Dell API gateway. US: apigtwb2c.us.dell.com, EU: apigtwb2c.eu.dell.com',
    )
    client_id = models.CharField(max_length=200, blank=True)
    client_secret = models.CharField(max_length=500, blank=True)
    is_active = models.BooleanField(default=True)
    # Cached OAuth2 bearer token (client_credentials grant, ~1h lifetime).
    access_token = models.CharField(max_length=2000, blank=True)
    token_expires_at = models.DateTimeField(null=True, blank=True)
    last_tested_at = models.DateTimeField(null=True, blank=True)
    last_test_status = models.CharField(max_length=20, blank=True)
    last_test_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'dell_support_connections'

    def __str__(self):
        return f'Dell TechDirect ({self.base_url})'


class GoogleWorkspaceConnection(models.Model):
    """
    One row per Google Workspace domain the portal reads the directory of.

    Access is a service account with domain-wide delegation: the account signs a
    JWT that names ``admin_email`` as the ``sub`` to impersonate, and Google
    hands back a short-lived read-only Admin SDK Directory token. Each domain
    gets its own row because two domains may belong to two separate Workspace
    accounts, and delegation is granted per account.
    """

    domain = models.CharField(max_length=253, unique=True, help_text='Primary or secondary domain, e.g. example.com.')
    label = models.CharField(max_length=200, blank=True)
    admin_email = models.EmailField(help_text='Super admin the service account impersonates.')
    service_account_json = models.TextField(blank=True)
    # Denormalised from the key so the UI can show which client ID to
    # authorise in the Admin console (it asks for the numeric ID, not the
    # email) without ever exposing the private key.
    service_account_email = models.CharField(max_length=255, blank=True)
    service_account_client_id = models.CharField(max_length=64, blank=True)
    is_active = models.BooleanField(default=True)
    last_tested_at = models.DateTimeField(null=True, blank=True)
    last_test_status = models.CharField(max_length=20, blank=True)
    last_test_message = models.TextField(blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'google_workspace_connections'
        ordering = ['domain']

    def __str__(self):
        return f'Google Workspace ({self.domain})'


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
