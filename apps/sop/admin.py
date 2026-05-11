from django.contrib import admin
from .models import SOPCategory, SOP, SOPStep, SOPChecklistItem, SOPExecution, SOPStepCompletion


class SOPChecklistItemInline(admin.TabularInline):
    model = SOPChecklistItem
    extra = 1


class SOPStepInline(admin.TabularInline):
    model = SOPStep
    extra = 1


@admin.register(SOPCategory)
class SOPCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'created_at')
    search_fields = ('name',)


@admin.register(SOP)
class SOPAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'is_active', 'created_by', 'created_at')
    list_filter = ('is_active', 'category')
    search_fields = ('name',)
    inlines = [SOPStepInline]
    readonly_fields = ('created_at', 'updated_at')


@admin.register(SOPStep)
class SOPStepAdmin(admin.ModelAdmin):
    list_display = ('sop', 'step_number', 'title', 'step_type', 'is_required')
    list_filter = ('step_type', 'sop')
    inlines = [SOPChecklistItemInline]


@admin.register(SOPExecution)
class SOPExecutionAdmin(admin.ModelAdmin):
    list_display = ('sop', 'status', 'current_step', 'started_by', 'started_at')
    list_filter = ('status',)
    readonly_fields = ('started_at', 'completed_at')


@admin.register(SOPStepCompletion)
class SOPStepCompletionAdmin(admin.ModelAdmin):
    list_display = ('execution', 'step', 'completed_by', 'completed_at')
    readonly_fields = ('completed_at',)
