from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST

from documents.models import LandDocument
from .models import DuplicateCandidate
from .services import find_duplicates


@login_required
def list_view(request):
    candidates = (
        DuplicateCandidate.objects
        .filter(document__owner=request.user)
        .select_related('document', 'matched_document')
        .order_by('-similarity')
    )
    pending = candidates.filter(reviewed=False).count()
    total_count = candidates.count()
    return render(request, 'duplicates/list.html', {
        'candidates': candidates,
        'pending_count': pending,
        'total_count': total_count,
        'reviewed_count': total_count - pending,
    })


@login_required
@require_POST
def review(request, pk):
    candidate = get_object_or_404(
        DuplicateCandidate, pk=pk, document__owner=request.user
    )
    candidate.reviewed = not candidate.reviewed
    candidate.save(update_fields=['reviewed'])
    messages.success(
        request,
        'Duplicate marked as reviewed.' if candidate.reviewed else 'Duplicate reopened.',
    )
    return redirect('duplicates:list')


@login_required
@require_POST
def scan(request):
    docs = list(LandDocument.objects.filter(owner=request.user))
    found = 0
    for document in docs:
        found += len(find_duplicates(document))
    messages.success(request, f'Duplicate scan finished: {found} candidate(s) found.')
    return redirect('duplicates:list')
