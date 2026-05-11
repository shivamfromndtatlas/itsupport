from django.contrib import admin
from .models import AssetAllocation, LicenseAllocation


@admin.register(AssetAllocation)
class AssetAllocationAdmin(admin.ModelAdmin):
    list_display = ('asset', 'employee', 'assigned_by', 'assigned_date', 'status', 'recovered_date')
    list_filter = ('status',)
    search_fields = ('asset__asset_id', 'employee__full_name', 'employee__employee_id')
    readonly_fields = ('qr_uuid', 'qr_code', 'created_at')


@admin.register(LicenseAllocation)
class LicenseAllocationAdmin(admin.ModelAdmin):
    list_display = ('license', 'employee', 'assigned_by', 'assigned_date', 'status', 'revoked_date')
    list_filter = ('status',)
    search_fields = ('license__software_name', 'employee__full_name', 'employee__employee_id')
    readonly_fields = ('created_at',)
