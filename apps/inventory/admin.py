from django.contrib import admin
from .models import AssetType, AssetAttribute, Asset, SoftwareLicense


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
