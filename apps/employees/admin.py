from django.contrib import admin
from .models import Employee


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('employee_id', 'full_name', 'official_email', 'core_process_code', 'core_process_name', 'designation', 'status')
    list_filter = ('status', 'core_process_code')
    search_fields = ('employee_id', 'full_name', 'official_email')
    ordering = ('full_name',)
    readonly_fields = ('created_at', 'updated_at')
