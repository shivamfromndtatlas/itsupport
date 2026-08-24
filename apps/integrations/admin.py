from django.contrib import admin

from .models import SureMDMConnection, SynthesiaConnection, SynthesiaInvoice, TeamViewerConnection, TrellixConnection


@admin.register(SynthesiaConnection)
class SynthesiaConnectionAdmin(admin.ModelAdmin):
    list_display = ('name', 'base_url', 'plan_name', 'is_active', 'last_test_status', 'last_tested_at', 'last_synced_at')
    readonly_fields = ('created_at', 'updated_at', 'last_tested_at', 'last_test_status', 'last_test_message', 'last_synced_at')


@admin.register(SynthesiaInvoice)
class SynthesiaInvoiceAdmin(admin.ModelAdmin):
    list_display = ('payment_date', 'amount', 'currency', 'invoice_number', 'connection')
    readonly_fields = ('created_at',)


@admin.register(SureMDMConnection)
class SureMDMConnectionAdmin(admin.ModelAdmin):
    list_display = ('base_url', 'username', 'is_active', 'last_test_status', 'last_tested_at', 'last_synced_at')
    readonly_fields = ('created_at', 'updated_at', 'last_tested_at', 'last_test_status', 'last_test_message', 'last_synced_at')


@admin.register(TrellixConnection)
class TrellixConnectionAdmin(admin.ModelAdmin):
    list_display = ('tenant_name', 'tenant_id', 'is_active', 'last_test_status', 'last_tested_at', 'last_synced_at')
    readonly_fields = ('created_at', 'updated_at', 'last_tested_at', 'last_test_status', 'last_test_message', 'last_synced_at')


@admin.register(TeamViewerConnection)
class TeamViewerConnectionAdmin(admin.ModelAdmin):
    list_display = ('name', 'base_url', 'is_active', 'last_test_status', 'last_tested_at', 'last_synced_at')
    readonly_fields = ('created_at', 'updated_at', 'last_tested_at', 'last_test_status', 'last_test_message', 'last_synced_at')
