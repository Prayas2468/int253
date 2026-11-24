from datetime import datetime

from django.http import JsonResponse
from django.shortcuts import render
from django.db.models import Count

from documents.models import LandDocument
from duplicates.models import DuplicateCandidate
from notifications.models import Notification


def home(request):
    sample_records = (
        LandDocument.objects
        .filter(status='done')
        .only('id', 'original_name', 'survey_number', 'district', 'status', 'confidence')
        .order_by('-uploaded_at')[:3]
    )
    total_documents = LandDocument.objects.count()
    districts = LandDocument.objects.exclude(district='').values('district').distinct().count()

    response = render(request, 'core/home.html', {
        'sample_records': sample_records,
        'total_documents': total_documents,
        'districts_covered': districts,
    })
    if not request.COOKIES.get('last_visit'):
        response.set_cookie(
            'last_visit',
            datetime.now().isoformat(),
            max_age=30 * 24 * 60 * 60,
            httponly=True,
            samesite='Lax',
        )
    return response


def health(request):
    return JsonResponse({'status': 'ok', 'service': 'BhoomiAI'})


def live(request):
    """Small JSON endpoint polled by the UI for live counters."""
    if not request.user.is_authenticated:
        return JsonResponse({'authenticated': False, 'unread': 0})

    docs = LandDocument.objects.filter(owner=request.user)
    duplicates = DuplicateCandidate.objects.filter(
        document__owner=request.user, reviewed=False
    )
    selected_state = request.GET.get('state', '').strip()
    if selected_state:
        docs = docs.filter(state=selected_state)
        duplicates = duplicates.filter(document__state=selected_state)

    return JsonResponse({
        'authenticated': True,
        'unread': Notification.objects.filter(user=request.user, read=False).count(),
        'total': docs.count(),
        'validated': docs.filter(status='done').count(),
        'pending': docs.filter(status__in=['pending', 'processing']).count(),
        'duplicates': duplicates.count(),
    })
