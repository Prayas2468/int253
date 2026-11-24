from django.contrib import admin

from .models import ExtractedField, LandDocument


class ExtractedFieldInline(admin.TabularInline):
    model = ExtractedField
    extra = 1
    fields = ('field_name', 'field_value', 'confidence', 'is_valid')


@admin.register(LandDocument)
class LandDocumentAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'original_name',
        'owner',
        'survey_number',
        'district',
        'state',
        'status',
        'confidence',
        'uploaded_at',
    )
    list_filter = ('status', 'state', 'district')
    search_fields = (
        'original_name',
        'survey_number',
        'district',
        'state',
        'owner_name',
        'owner__email',
    )
    list_select_related = ('owner',)
    date_hierarchy = 'uploaded_at'
    ordering = ('-uploaded_at',)
    list_per_page = 25
    inlines = [ExtractedFieldInline]


@admin.register(ExtractedField)
class ExtractedFieldAdmin(admin.ModelAdmin):
    list_display = ('id', 'document', 'field_name', 'field_value', 'confidence', 'is_valid')
    list_filter = ('field_name', 'is_valid')
    search_fields = ('field_name', 'field_value', 'document__original_name')
    list_select_related = ('document',)
