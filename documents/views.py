from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.views.decorators.http import require_POST
from .models import LandDocument, ExtractedField
from .forms import DocumentUploadForm
from ocr_engine.services import OCREngine
from validation.services import validate_document, validation_summary
from duplicates.services import find_duplicates
from notifications.services import notify


@login_required
def document_list(request):
    docs = LandDocument.objects.filter(owner=request.user)
    query = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()
    if query:
        docs = docs.filter(original_name__icontains=query) | docs.filter(survey_number__icontains=query)
    if status in dict(LandDocument.STATUS_CHOICES):
        docs = docs.filter(status=status)
    docs = docs.distinct()
    return render(request, 'documents/list.html', {
        'object_list': docs,
        'query': query,
        'status_filter': status,
        'status_choices': LandDocument.STATUS_CHOICES,
        'total_count': docs.count(),
    })


@login_required
def document_upload(request):
    if request.method == 'POST':
        form = DocumentUploadForm(request.POST, request.FILES)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.owner = request.user
            if not doc.original_name:
                doc.original_name = request.FILES['file'].name
            if not doc.state and doc.district:
                from .services import infer_state
                doc.state = infer_state(doc.district)
            doc.save()
            notify(request.user, f'Document "{doc.original_name}" uploaded. Run OCR to extract fields.')
            messages.success(request, 'Document uploaded. Run OCR to extract its fields.')
            return redirect('documents:detail', pk=doc.pk)
        messages.error(request, 'Please correct the errors below and try again.')
    else:
        form = DocumentUploadForm()
    return render(request, 'documents/upload.html', {'form': form})


@login_required
def document_detail(request, pk):
    doc = get_object_or_404(LandDocument, pk=pk, owner=request.user)
    fields = doc.fields.all()
    validations = doc.validations.select_related('rule')
    duplicates = doc.duplicates.select_related('matched_document')
    return render(request, 'documents/detail.html', {
        'document': doc,
        'fields': fields,
        'validations': validations,
        'summary': validation_summary(doc),
        'duplicates': duplicates,
    })


@login_required
def document_delete(request, pk):
    doc = get_object_or_404(LandDocument, pk=pk, owner=request.user)
    if request.method == 'POST':
        name = doc.original_name
        doc.delete()
        notify(request.user, f'Document "{name}" deleted.')
        messages.success(request, 'Document deleted.')
        return redirect('documents:list')
    return render(request, 'documents/confirm_delete.html', {'document': doc})


@login_required
@require_POST
def run_ocr(request, pk):
    doc = get_object_or_404(LandDocument, pk=pk, owner=request.user)
    engine = OCREngine()
    extracted = engine.process(doc.file.path)

    doc.fields.all().delete()
    detected = 0
    for item in extracted:
        ExtractedField.objects.create(
            document=doc,
            field_name=item.get('name') or 'Unknown',
            field_value=item.get('value') or 'Not detected',
            confidence=item.get('confidence', 0.0),
            is_valid=item.get('is_valid', False),
        )
        if item.get('value') and item.get('value') != 'Not detected':
            detected += 1

    values = {
        item['name']: item['value']
        for item in extracted
        if item.get('value') and item.get('value') != 'Not detected'
    }
    doc.survey_number = values.get('Survey Number', doc.survey_number)
    doc.district = values.get('District', doc.district)
    doc.area = values.get('Area', doc.area)
    doc.owner_name = values.get('Owner Name', doc.owner_name)
    if doc.district and not doc.state:
        from .services import infer_state
        doc.state = infer_state(doc.district)
    doc.confidence = engine.confidence
    doc.processed_at = timezone.now()
    doc.status = 'done' if detected else 'failed'
    doc.save()

    validate_document(doc)
    duplicates = find_duplicates(doc)

    if detected:
        message = (
            f'OCR finished for "{doc.original_name}": {detected} field(s) extracted '
            f'at {doc.confidence:.1f}% confidence.'
        )
        if duplicates:
            message += f' {len(duplicates)} possible duplicate(s) found.'
        messages.success(request, message)
    else:
        messages.warning(
            request,
            'OCR ran but no fields could be read. Try a clearer scan, or enter the fields manually.',
        )
    notify(request.user, f'OCR completed for "{doc.original_name}".')
    return redirect('documents:detail', pk=doc.pk)
