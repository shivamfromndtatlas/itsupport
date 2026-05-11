from django.contrib import admin
from .models import Employee


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('employee_id', 'full_name', 'official_email', 'core_process', 'designation', 'is_active')
    list_filter = ('is_active', 'core_process')
    search_fields = ('employee_id', 'full_name', 'official_email')
    ordering = ('full_name',)
    readonly_fields = ('created_at', 'updated_at')
