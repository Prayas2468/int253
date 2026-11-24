from .models import Notification


def notifications(request):
    """Expose unread notification data to every template."""
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {
            'unread_notifications': 0,
            'recent_notifications': [],
        }

    qs = Notification.objects.filter(user=request.user)
    return {
        'unread_notifications': qs.filter(read=False).count(),
        'recent_notifications': list(qs[:5]),
    }
