from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import render
from django.utils import timezone

from documents.models import LandDocument
from documents.services import STATE_COORDS
from duplicates.models import DuplicateCandidate
from notifications.models import Notification
from validation.models import ValidationResult


def _daily_counts(queryset, days=30, field='uploaded_at'):
    today = timezone.localdate()
    start = today - timedelta(days=days - 1)
    counts = {
        row[f'{field}__date']: row['count']
        for row in queryset.filter(**{f'{field}__date__gte': start})
        .values(f'{field}__date')
        .annotate(count=Count('id'))
    }
    labels, values = [], []
    for offset in range(days):
        day = start + timedelta(days=offset)
        labels.append(day.strftime('%d %b'))
        values.append(counts.get(day, 0))
    return labels, values


def _trend(queryset, field='uploaded_at'):
    """Percent change between the last 7 days and the previous 7 days."""
    today = timezone.localdate()
    recent_start = today - timedelta(days=6)
    previous_start = today - timedelta(days=13)
    recent = queryset.filter(**{
        f'{field}__date__gte': recent_start,
        f'{field}__date__lte': today,
    }).count()
    previous = queryset.filter(**{
        f'{field}__date__gte': previous_start,
        f'{field}__date__lt': recent_start,
    }).count()
    if previous == 0:
        return 100 if recent else 0
    return round(((recent - previous) / previous) * 100)


@login_required
def dashboard_home(request):
    all_docs = LandDocument.objects.filter(owner=request.user)

    selected_state = request.GET.get('state', '').strip()
    docs = all_docs
    if selected_state:
        docs = docs.filter(state=selected_state)

    total = docs.count()
    done = docs.filter(status='done').count()
    pending = docs.filter(status__in=['pending', 'processing']).count()
    failed = docs.filter(status='failed').count()

    duplicates = DuplicateCandidate.objects.filter(
        document__owner=request.user, reviewed=False
    )
    if selected_state:
        duplicates = duplicates.filter(document__state=selected_state)
    duplicates_count = duplicates.count()

    labels, uploads = _daily_counts(docs, 30)
    _, done_series = _daily_counts(docs.filter(status='done'), 30)
    _, pending_series = _daily_counts(docs.filter(status__in=['pending', 'processing']), 30)

    duplicate_source = DuplicateCandidate.objects.filter(document__owner=request.user)
    if selected_state:
        duplicate_source = duplicate_source.filter(document__state=selected_state)
    _, duplicate_series = _daily_counts(duplicate_source, 30, field='created_at')

    unread_notifications = Notification.objects.filter(
        user=request.user, read=False
    ).count()

    status_counts = {
        row['status']: row['count']
        for row in docs.values('status').annotate(count=Count('id'))
    }
    status_labels = ['Pending', 'Processing', 'Done', 'Failed']
    status_values = [
        status_counts.get('pending', 0),
        status_counts.get('processing', 0),
        status_counts.get('done', 0),
        status_counts.get('failed', 0),
    ]

    district_rows = (
        docs.exclude(district='')
        .values('district')
        .annotate(count=Count('id'))
        .order_by('-count')[:5]
    )
    district_labels = [row['district'] for row in district_rows] or ['No data']
    district_values = [row['count'] for row in district_rows] or [0]

    # Map bubbles use the unfiltered set so users can switch states.
    state_rows = (
        all_docs.exclude(state='')
        .values('state')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    map_points = []
    for row in state_rows:
        coords = STATE_COORDS.get(row['state'])
        if coords:
            map_points.append({
                'state': row['state'],
                'count': row['count'],
                'lat': coords[0],
                'lng': coords[1],
            })
    available_states = [row['state'] for row in state_rows]

    checks = ValidationResult.objects.filter(document__in=docs)
    passed_checks = checks.filter(passed=True).count()
    failed_checks = checks.filter(passed=False).count()
    pass_rate = round((passed_checks / (passed_checks + failed_checks)) * 100) if (passed_checks + failed_checks) else 0

    # Workflow progress: upload -> OCR -> validation -> approval -> report.
    workflow = [
        {'key': 'upload', 'label': 'Upload', 'count': total, 'icon': 'icon-upload'},
        {'key': 'ocr', 'label': 'OCR', 'count': docs.exclude(processed_at=None).count(), 'icon': 'icon-ocr'},
        {'key': 'validate', 'label': 'Validate', 'count': docs.filter(validations__isnull=False).distinct().count(), 'icon': 'icon-validate'},
        {'key': 'approve', 'label': 'Approve', 'count': done, 'icon': 'icon-check'},
        {'key': 'report', 'label': 'Report', 'count': done, 'icon': 'icon-report'},
    ]
    for step in workflow:
        step['percent'] = round((step['count'] / total) * 100) if total else 0

    chart_data = {
        'uploads': {'labels': labels, 'values': uploads},
        'status': {'labels': status_labels, 'values': status_values},
        'districts': {'labels': district_labels, 'values': district_values},
    }

    recent_documents = docs.select_related('owner')[:5]

    return render(request, 'dashboard/dashboard.html', {
        'total_documents': total,
        'validated_count': done,
        'pending_count': pending,
        'failed_count': failed,
        'duplicates_count': duplicates_count,
        'pass_rate': pass_rate,
        'recent_documents': recent_documents,
        'chart_data': chart_data,
        'map_points': map_points,
        'available_states': available_states,
        'selected_state': selected_state,
        'workflow': workflow,
        'spark_total': uploads[-7:],
        'spark_done': done_series[-7:],
        'spark_pending': pending_series[-7:],
        'spark_duplicates': duplicate_series[-7:],
        'trend_total': _trend(docs),
        'trend_validated': _trend(docs.filter(status='done')),
        'trend_pending': _trend(docs.filter(status__in=['pending', 'processing'])),
        'trend_duplicates': _trend(
            DuplicateCandidate.objects.filter(document__owner=request.user),
            field='created_at',
        ),
        'unread_notifications': unread_notifications,
    })
