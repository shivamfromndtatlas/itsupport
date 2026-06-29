from django.core.exceptions import ValidationError
from django.db import models
import uuid


class AssetAllocation(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('recovered', 'Recovered'),
    ]

    asset = models.ForeignKey('inventory.Asset', on_delete=models.CASCADE, related_name='allocations')
    employee = models.ForeignKey('employees.Employee', on_delete=models.CASCADE, related_name='asset_allocations')
    assigned_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, related_name='asset_assignments')
    assigned_date = models.DateField()
    recovered_date = models.DateField(null=True, blank=True)
    recovered_by = models.ForeignKey(
        'users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='asset_recoveries'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    notes = models.TextField(blank=True)
    qr_code = models.ImageField(upload_to='qr_codes/', blank=True)
    qr_uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'asset_allocations'
        ordering = ['-assigned_date']

    def __str__(self):
        return f'{self.asset.asset_id} -> {self.employee.full_name}'

    def clean(self):
        super().clean()
        asset_org_id = getattr(self.asset, 'organisation_id', None)
        if asset_org_id and not self.employee.organisations.filter(id=asset_org_id).exists():
            raise ValidationError('This employee does not belong to the asset organisation.')


class LicenseAllocation(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('revoked', 'Revoked'),
    ]

    license = models.ForeignKey('inventory.SoftwareLicense', on_delete=models.CASCADE, related_name='allocations')
    employee = models.ForeignKey('employees.Employee', on_delete=models.CASCADE, related_name='license_allocations')
    assigned_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, related_name='license_assignments')
    assigned_date = models.DateField()
    revoked_date = models.DateField(null=True, blank=True)
    revoked_by = models.ForeignKey(
        'users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='license_revocations'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'license_allocations'
        ordering = ['-assigned_date']

    def __str__(self):
        return f'{self.license.software_name} -> {self.employee.full_name}'

    def clean(self):
        super().clean()
        license_org_id = getattr(self.license, 'organisation_id', None)
        if license_org_id and not self.employee.organisations.filter(id=license_org_id).exists():
            raise ValidationError('This employee does not belong to the licence organisation.')
