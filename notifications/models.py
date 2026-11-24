from django.db import models
from django.conf import settings


class Notification(models.Model):
    """Simple user notification model.
    Stores a message and read status for a given user.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    message = models.CharField(max_length=255)
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'

    def __str__(self):
        status = 'Read' if self.read else 'Unread'
        return f"{self.user}: {self.message} ({status})"
