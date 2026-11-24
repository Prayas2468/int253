from django.contrib import admin

from .models import ValidationResult, ValidationRule


@admin.register(ValidationRule)
class ValidationRuleAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'active')
    list_filter = ('active',)
    search_fields = ('name', 'description')
    ordering = ('name',)


@admin.register(ValidationResult)
class ValidationResultAdmin(admin.ModelAdmin):
    list_display = ('id', 'document', 'rule', 'passed', 'checked_at')
    list_filter = ('passed', 'rule')
    search_fields = ('document__original_name', 'rule__name', 'message')
    list_select_related = ('document', 'rule')
    date_hierarchy = 'checked_at'
    ordering = ('-checked_at',)
