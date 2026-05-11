from django.db import models


class AssetType(models.Model):
    TYPE_CHOICES = [('hardware', 'Hardware'), ('software', 'Software')]
    name = models.CharField(max_length=100)
    asset_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'asset_types'

    def __str__(self):
        return f'{self.name} ({self.asset_type})'


class AssetAttribute(models.Model):
    FIELD_TYPE_CHOICES = [
        ('text', 'Text'),
        ('number', 'Number'),
        ('date', 'Date'),
        ('boolean', 'Boolean'),
        ('select', 'Select'),
    ]

    name = models.CharField(max_length=100)
    field_type = models.CharField(max_length=20, choices=FIELD_TYPE_CHOICES, default='text')
    options = models.JSONField(default=list, blank=True)
    asset_types = models.ManyToManyField(AssetType, related_name='attributes', blank=True)
    is_common = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'asset_attributes'

    def __str__(self):
        return self.name


class Asset(models.Model):
    STATUS_CHOICES = [
        ('available', 'Available'),
        ('assigned', 'Assigned'),
        ('maintenance', 'Under Maintenance'),
        ('retired', 'Retired'),
    ]

    asset_id = models.CharField(max_length=100, unique=True)
    asset_type = models.ForeignKey(AssetType, on_delete=models.CASCADE, related_name='assets')
    serial_number = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    purchase_date = models.DateField(null=True, blank=True)
    purchase_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    warranty_expiry = models.DateField(null=True, blank=True)
    vendor = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    attribute_values = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'assets'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.asset_id} - {self.asset_type.name}'


class SoftwareLicense(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('revoked', 'Revoked'),
    ]
    LICENSE_TYPE_CHOICES = [
        ('perpetual', 'Perpetual'),
        ('subscription', 'Subscription'),
        ('trial', 'Trial'),
        ('open_source', 'Open Source'),
    ]

    software_name = models.CharField(max_length=200)
    license_key = models.CharField(max_length=500, blank=True)
    vendor = models.CharField(max_length=200, blank=True)
    total_seats = models.PositiveIntegerField(default=1)
    available_seats = models.PositiveIntegerField(default=1)
    expiry_date = models.DateField(null=True, blank=True)
    purchase_date = models.DateField(null=True, blank=True)
    cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    license_type = models.CharField(max_length=20, choices=LICENSE_TYPE_CHOICES, default='perpetual')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    attribute_values = models.JSONField(default=dict)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'software_licenses'
        ordering = ['software_name']

    def __str__(self):
        return f'{self.software_name} ({self.available_seats}/{self.total_seats} seats)'
