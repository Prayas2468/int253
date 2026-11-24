from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'message', 'read', 'created_at')
    list_filter = ('read', 'created_at')
    search_fields = ('user__email', 'message')
    list_select_related = ('user',)
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    actions = ('mark_as_read', 'mark_as_unread')

    @admin.action(description='Mark selected notifications as read')
    def mark_as_read(self, request, queryset):
        updated = queryset.update(read=True)
        self.message_user(request, f'{updated} notification(s) marked as read.')

    @admin.action(description='Mark selected notifications as unread')
    def mark_as_unread(self, request, queryset):
        updated = queryset.update(read=False)
        self.message_user(request, f'{updated} notification(s) marked as unread.')
