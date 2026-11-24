from django.contrib.auth import get_user_model
from .models import Notification


def notify(user, message):
    """Create an in-app notification for a user."""
    if not user or not getattr(user, 'is_authenticated', False):
        return None
    return Notification.objects.create(user=user, message=message[:255])


def notify_staff(message):
    User = get_user_model()
    for user in User.objects.filter(is_staff=True):
        notify(user, message)
