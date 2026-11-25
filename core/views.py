from datetime import datetime

from django.http import JsonResponse
from django.shortcuts import render

from notifications.models import Notification
from predictions import ml, services
from predictions.models import ModelVersion, ProjectPrediction


def home(request):
    context = services.dashboard_context(request)
    metrics = ml.read_metrics()
    selected = metrics.get('selected', '')
    selected_metrics = metrics.get('algorithms', {}).get(selected, {})

    context.update({
        'selected_algorithm': selected,
        'selected_metrics': selected_metrics,
        'prediction_count': ProjectPrediction.objects.count(),
        'model_version': ModelVersion.objects.filter(is_active=True).first(),
        'dataset_rows': metrics.get('dataset', {}).get('rows', 0),
        'dataset_delay_rate': metrics.get('dataset', {}).get('delay_rate', 0),
        'sample_projects': (
            services.annotated_projects()
            .order_by('-latest_probability', '-updated_at')[:6]
        ),
    })

    response = render(request, 'core/home.html', context)
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
    return JsonResponse({'status': 'ok', 'service': 'BhoomiAI', 'project': 'Land Acquisition Delay Prediction'})


def live(request):
    """Small JSON endpoint polled by the UI for live counters."""
    if not request.user.is_authenticated:
        return JsonResponse({'authenticated': False, 'unread': 0})

    projects = services.annotated_projects()
    return JsonResponse({
        'authenticated': True,
        'unread': Notification.objects.filter(user=request.user, read=False).count(),
        'total': projects.count(),
        'predictions': ProjectPrediction.objects.count(),
        'high_risk': projects.filter(latest_risk='High').count(),
        'pending': projects.filter(latest_risk='Medium').count(),
        'duplicates': 0,
        'on_track': projects.filter(latest_risk='Low').count(),
    })
