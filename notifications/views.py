from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from .models import Notification


@login_required
def notification_list(request):
    notes = Notification.objects.filter(user=request.user)
    return render(request, 'notifications/list.html', {
        'notifications': notes,
        'unread_count': notes.filter(read=False).count(),
    })


@login_required
@require_POST
def mark_read(request, pk):
    note = get_object_or_404(Notification, pk=pk, user=request.user)
    note.read = True
    note.save(update_fields=['read'])
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'ok': True, 'unread': Notification.objects.filter(user=request.user, read=False).count()})
    return redirect('notifications:list')


@login_required
@require_POST
def mark_all_read(request):
    updated = Notification.objects.filter(user=request.user, read=False).update(read=True)
    messages.success(request, f'{updated} notification(s) marked as read.')
    return redirect('notifications:list')


@login_required
def unread_count(request):
    qs = Notification.objects.filter(user=request.user)
    latest = list(qs.filter(read=False).values('id', 'message', 'created_at')[:5])
    return JsonResponse({
        'unread': qs.filter(read=False).count(),
        'latest': latest,
    })
