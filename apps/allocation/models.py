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
    employee = models.ForeignKey(
        'employees.Employee',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='license_allocations',
    )
    asset = models.ForeignKey(
        'inventory.Asset',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='license_allocations',
    )
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
        constraints = [
            models.CheckConstraint(
                name='license_allocation_employee_xor_asset',
                condition=(
                    models.Q(employee__isnull=False, asset__isnull=True)
                    | models.Q(employee__isnull=True, asset__isnull=False)
                ),
            ),
        ]

    def __str__(self):
        target = self.employee.full_name if self.employee_id else getattr(self.asset, 'asset_id', 'unassigned')
        return f'{self.license.software_name} -> {target}'

    def clean(self):
        super().clean()

        if bool(self.employee_id) == bool(self.asset_id):
            raise ValidationError('A licence allocation must be linked to either an employee or an asset, not both.')

        license_org_ids = set(self.license.organisations.values_list('id', flat=True))
        if not license_org_ids:
            return

        if self.employee_id:
            if not self.employee.organisations.filter(id__in=license_org_ids).exists():
                raise ValidationError('This employee does not belong to any of the licence organisations.')
        elif self.asset_id:
            asset_org_id = getattr(self.asset, 'organisation_id', None)
            if asset_org_id and asset_org_id not in license_org_ids:
                raise ValidationError('This asset does not belong to any of the licence organisations.')
