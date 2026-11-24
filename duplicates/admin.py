from django.contrib import admin

from .models import DuplicateCandidate


@admin.register(DuplicateCandidate)
class DuplicateCandidateAdmin(admin.ModelAdmin):
    list_display = ('id', 'document', 'matched_document', 'similarity', 'reviewed', 'created_at')
    list_filter = ('reviewed',)
    search_fields = (
        'document__original_name',
        'matched_document__original_name',
        'document__survey_number',
    )
    list_select_related = ('document', 'matched_document')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
