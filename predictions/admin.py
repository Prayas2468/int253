from django.contrib import admin

from .models import (
    ActivityLog,
    LandAcquisitionProject,
    MitigationPlan,
    ModelVersion,
    PredictionFactor,
    ProjectPrediction,
)


class ProjectPredictionInline(admin.TabularInline):
    model = ProjectPrediction
    extra = 0
    fields = ('delay_probability', 'risk_level', 'predicted_delay_days', 'model_version', 'created_at')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)


@admin.register(LandAcquisitionProject)
class LandAcquisitionProjectAdmin(admin.ModelAdmin):
    list_display = (
        'project_id', 'project_name', 'state', 'district', 'project_type',
        'acquisition_progress', 'compensation_completion_percentage',
        'status', 'archived', 'is_synthetic',
    )
    list_filter = ('state', 'status', 'archived', 'is_synthetic', 'approval_status')
    search_fields = ('project_id', 'project_name', 'district', 'state')
    date_hierarchy = 'updated_at'
    ordering = ('-updated_at',)
    list_per_page = 30
    inlines = [ProjectPredictionInline]


@admin.register(ProjectPrediction)
class ProjectPredictionAdmin(admin.ModelAdmin):
    list_display = ('id', 'project', 'delay_probability', 'risk_level', 'predicted_delay_days', 'created_at')
    list_filter = ('risk_level', 'created_at')
    search_fields = ('project__project_id', 'project__project_name')
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'


@admin.register(PredictionFactor)
class PredictionFactorAdmin(admin.ModelAdmin):
    list_display = ('id', 'prediction', 'factor_name', 'impact', 'direction')
    list_filter = ('direction',)
    search_fields = ('factor_name', 'prediction__project__project_id')


@admin.register(ModelVersion)
class ModelVersionAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'algorithm', 'version', 'is_active', 'training_rows', 'trained_at')
    list_filter = ('is_active', 'algorithm')
    search_fields = ('name', 'version')


@admin.register(MitigationPlan)
class MitigationPlanAdmin(admin.ModelAdmin):
    list_display = ('id', 'project', 'risk_area', 'priority', 'status', 'generated_by_system', 'created_at')
    list_filter = ('status', 'priority', 'generated_by_system', 'risk_area')
    search_fields = ('title', 'project__project_id', 'project__project_name')
    date_hierarchy = 'created_at'


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'action', 'entity_type', 'entity_id', 'detail', 'created_at')
    list_filter = ('action', 'created_at')
    search_fields = ('detail', 'entity_id')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
