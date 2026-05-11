from django.contrib import admin
from .models import NewJoinerRequest


@admin.register(NewJoinerRequest)
class NewJoinerRequestAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'employee_id', 'designation', 'core_process', 'date_of_joining', 'status')
    list_filter = ('status', 'core_process')
    search_fields = ('full_name', 'employee_id', 'personal_email')
    readonly_fields = ('created_at', 'updated_at', 'confirmed_at')
