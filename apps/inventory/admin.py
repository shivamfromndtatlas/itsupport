from django.contrib import admin
from .models import (
    AssetType,
    AssetAttribute,
    Asset,
    InstalledApplication,
    InstalledAppReportImport,
    SoftwareLicense,
)


@admin.register(AssetType)
class AssetTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'asset_type', 'created_at')
    list_filter = ('asset_type',)
    search_fields = ('name',)


@admin.register(AssetAttribute)
class AssetAttributeAdmin(admin.ModelAdmin):
    list_display = ('name', 'field_type', 'is_common', 'created_at')
    list_filter = ('field_type', 'is_common')
    search_fields = ('name',)
    filter_horizontal = ('asset_types',)


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ('asset_id', 'asset_type', 'serial_number', 'status', 'vendor', 'purchase_date')
    list_filter = ('status', 'asset_type')
    search_fields = ('asset_id', 'serial_number', 'vendor')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(SoftwareLicense)
class SoftwareLicenseAdmin(admin.ModelAdmin):
    list_display = ('software_name', 'vendor', 'total_seats', 'available_seats', 'expiry_date', 'status')
    list_filter = ('status',)
    search_fields = ('software_name', 'vendor')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(InstalledAppReportImport)
class InstalledAppReportImportAdmin(admin.ModelAdmin):
    list_display = ('file_name', 'imported_by', 'device_count', 'app_count', 'imported_at')
    search_fields = ('file_name',)
    readonly_fields = ('imported_at',)


@admin.register(InstalledApplication)
class InstalledApplicationAdmin(admin.ModelAdmin):
    list_display = ('device_name', 'application_name', 'application_version', 'application_type', 'user_name')
    list_filter = ('application_type',)
    search_fields = ('device_name', 'application_name', 'application_package', 'application_version')
    readonly_fields = ('created_at',)
