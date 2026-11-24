from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('email', 'full_name', 'role', 'is_staff', 'is_active')
    list_filter = ('role', 'is_staff', 'is_active')
    search_fields = ('email', 'full_name')
    ordering = ('email',)
    fieldsets = UserAdmin.fieldsets + (
        ('BhoomiAI', {'fields': ('full_name', 'role', 'theme_preference')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('BhoomiAI', {'fields': ('email', 'full_name', 'role')}),
    )
