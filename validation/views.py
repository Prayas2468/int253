from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST

from documents.models import LandDocument
from .models import ValidationResult
from .services import validate_document, validation_summary, ensure_default_rules


@login_required
def results_list(request):
    ensure_default_rules()
    docs = (
        LandDocument.objects
        .filter(owner=request.user)
        .prefetch_related('validations__rule')
        .order_by('-uploaded_at')
    )

    documents = []
    totals = {'passed': 0, 'failed': 0, 'checks': 0}
    for doc in docs:
        results = list(doc.validations.all())
        if not results:
            continue
        summary = validation_summary(doc)
        totals['passed'] += summary['passed']
        totals['failed'] += summary['failed']
        totals['checks'] += summary['total']
        documents.append({'document': doc, 'results': results, 'summary': summary})

    overall = round((totals['passed'] / totals['checks']) * 100) if totals['checks'] else 0
    return render(request, 'validation/results.html', {
        'documents': documents,
        'totals': totals,
        'overall_percent': overall,
    })


@login_required
@require_POST
def run_validation(request, pk):
    document = get_object_or_404(LandDocument, pk=pk, owner=request.user)
    results = validate_document(document)
    passed = sum(1 for result in results if result.passed)
    messages.success(
        request,
        f'Validation re-run for {document.original_name}: {passed}/{len(results)} checks passed.',
    )
    return redirect('validation:list')


@login_required
@require_POST
def run_all(request):
    docs = LandDocument.objects.filter(owner=request.user)
    checked = 0
    for document in docs:
        validate_document(document)
        checked += 1
    messages.success(request, f'Validation completed for {checked} document(s).')
    return redirect('validation:list')
