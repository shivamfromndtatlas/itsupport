from django.contrib import admin

from .models import SureMDMConnection


@admin.register(SureMDMConnection)
class SureMDMConnectionAdmin(admin.ModelAdmin):
    list_display = ('base_url', 'username', 'is_active', 'last_test_status', 'last_tested_at', 'last_synced_at')
    readonly_fields = ('created_at', 'updated_at', 'last_tested_at', 'last_test_status', 'last_test_message', 'last_synced_at')
