"""Overview dashboard for the land-acquisition delay prediction platform."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from notifications.models import Notification
from predictions import services
from predictions.models import LandAcquisitionProject, ModelVersion


@login_required
def dashboard_home(request):
    context = services.dashboard_context(request)
    context['unread_notifications'] = Notification.objects.filter(
        user=request.user, read=False
    ).count()
    context['active_model'] = ModelVersion.objects.filter(is_active=True).first()
    context['project_options'] = (
        LandAcquisitionProject.objects.filter(archived=False)
        .order_by('project_name')
        .values_list('pk', 'project_name')[:300]
    )
    return render(request, 'dashboard/dashboard.html', context)
