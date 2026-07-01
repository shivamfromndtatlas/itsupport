from django.contrib import admin

from .models import ActivityLog


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'user', 'action', 'method', 'path', 'status_code')
    list_filter = ('method', 'status_code', 'created_at')
    search_fields = ('user__full_name', 'user__email', 'action', 'path')
    readonly_fields = ('created_at',)
