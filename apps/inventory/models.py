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


class AssetTypeAttributeRequirement(models.Model):
    REQUIREMENT_CHOICES = [
        ('mandatory', 'Mandatory'),
        ('optional', 'Optional'),
        ('hidden', 'Hidden'),
    ]

    asset_type = models.ForeignKey(AssetType, on_delete=models.CASCADE, related_name='attribute_requirements')
    attribute = models.ForeignKey(AssetAttribute, on_delete=models.CASCADE, related_name='type_requirements')
    requirement = models.CharField(max_length=20, choices=REQUIREMENT_CHOICES, default='optional')
    notes = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'asset_type_attribute_requirements'
        unique_together = ('asset_type', 'attribute')
        ordering = ['asset_type__name', 'attribute__name']

    def __str__(self):
        return f'{self.asset_type.name} - {self.attribute.name}: {self.requirement}'


class Asset(models.Model):
    STATUS_CHOICES = [
        ('available', 'Available'),
        ('assigned', 'Assigned'),
        ('maintenance', 'Under Maintenance'),
        ('retired', 'Retired'),
    ]

    asset_id = models.CharField(max_length=100, unique=True)
    organisation = models.ForeignKey(
        'organisations.Organisation',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assets',
    )
    location = models.ForeignKey(
        'organisations.OrganisationLocation',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assets',
    )
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

    def save(self, *args, **kwargs):
        # 1. Handle Django's update_fields to include synced fields
        if 'update_fields' in kwargs and kwargs['update_fields'] is not None:
            update_fields = list(kwargs['update_fields'])
            if 'status' in update_fields and 'attribute_values' not in update_fields:
                update_fields.append('attribute_values')
            if 'attribute_values' in update_fields and 'status' not in update_fields:
                update_fields.append('status')
            kwargs['update_fields'] = update_fields

        # Ensure attribute_values is a dict
        if self.attribute_values is None:
            self.attribute_values = {}

        # 2. Sync from attribute_values to core status
        # Check ID "10" first, then key name "Availability Status"
        avail_status = self.attribute_values.get("10") or self.attribute_values.get("Availability Status")
        if avail_status:
            status_map = {
                'In Stock': 'available',
                'Reserved Stock': 'available',
                'Issued': 'assigned',
                'Under Repair': 'maintenance',
                'Retired': 'retired'
            }
            mapped_status = status_map.get(avail_status)
            if mapped_status:
                self.status = mapped_status
                # Keep both keys in sync in attribute_values
                self.attribute_values["10"] = avail_status
                self.attribute_values["Availability Status"] = avail_status

        # 3. Sync from core status to attribute_values
        core_to_avail = {
            'available': 'In Stock',
            'assigned': 'Issued',
            'maintenance': 'Under Repair',
            'retired': 'Retired'
        }
        if self.status:
            current_avail = self.attribute_values.get("10") or self.attribute_values.get("Availability Status")
            # If core status is available, current_avail could be In Stock or Reserved Stock
            if self.status == 'available' and current_avail in ('In Stock', 'Reserved Stock'):
                pass
            else:
                expected_avail = core_to_avail.get(self.status)
                if expected_avail and current_avail != expected_avail:
                    self.attribute_values["10"] = expected_avail
                    self.attribute_values["Availability Status"] = expected_avail

        super().save(*args, **kwargs)



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
    organisation = models.ForeignKey(
        'organisations.Organisation',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='software_licenses',
    )
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


class InstalledAppReportImport(models.Model):
    file_name = models.CharField(max_length=255)
    imported_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='installed_app_report_imports',
    )
    imported_at = models.DateTimeField(auto_now_add=True)
    device_count = models.PositiveIntegerField(default=0)
    app_count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'installed_app_report_imports'
        ordering = ['-imported_at']

    def __str__(self):
        return f'{self.file_name} ({self.app_count} apps)'


class InstalledApplication(models.Model):
    report_import = models.ForeignKey(
        InstalledAppReportImport,
        on_delete=models.CASCADE,
        related_name='applications',
    )
    device_name = models.CharField(max_length=200)
    normalized_device_name = models.CharField(max_length=200, db_index=True)
    application_package = models.TextField(blank=True)
    application_name = models.TextField()
    application_type = models.CharField(max_length=100, blank=True)
    user_name = models.CharField(max_length=200, blank=True)
    application_version = models.CharField(max_length=200, blank=True)
    signature_key_hash = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'installed_applications'
        indexes = [
            models.Index(fields=['normalized_device_name']),
        ]
        ordering = ['application_name']

    def __str__(self):
        return f'{self.device_name} - {self.application_name}'
