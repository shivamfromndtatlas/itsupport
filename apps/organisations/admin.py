from django.contrib import admin

from .models import Organisation


@admin.register(Organisation)
class OrganisationAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_base', 'city', 'country', 'created_at')
    list_filter = ('is_base', 'city', 'country')
    search_fields = ('name', 'city', 'country')
