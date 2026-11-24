"""Report generation: CSV, Excel and PDF exports with real document data."""

import csv
import io

from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count
from django.http import HttpResponse
from django.shortcuts import render

from documents.models import LandDocument
from validation.models import ValidationResult

try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    HAS_OPENPYXL = True
except Exception:  # pragma: no cover
    HAS_OPENPYXL = False

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    HAS_REPORTLAB = True
except Exception:  # pragma: no cover
    HAS_REPORTLAB = False


HEADERS = [
    'ID', 'File', 'Survey No', 'District', 'Area', 'Owner',
    'Status', 'Confidence (%)', 'Uploaded',
]


def _documents(user):
    qs = LandDocument.objects.all() if user.is_staff else LandDocument.objects.filter(owner=user)
    return qs.select_related('owner').order_by('-uploaded_at')


def _rows(user):
    rows = []
    for doc in _documents(user):
        rows.append([
            doc.pk,
            doc.original_name,
            doc.survey_number or '-',
            doc.district or '-',
            doc.area or '-',
            doc.owner_name or '-',
            doc.get_status_display(),
            f'{doc.confidence:.1f}',
            doc.uploaded_at.strftime('%Y-%m-%d %H:%M'),
        ])
    return rows


@login_required
def index(request):
    qs = _documents(request.user)
    total = qs.count()
    by_status = {row['status']: row['count'] for row in qs.values('status').annotate(count=Count('id'))}
    validated = by_status.get('done', 0)
    checks = ValidationResult.objects.filter(document__in=qs)
    passed = checks.filter(passed=True).count()
    failed = checks.filter(passed=False).count()
    pass_rate = round((passed / (passed + failed)) * 100) if (passed + failed) else 0
    return render(request, 'reports/index.html', {
        'total': total,
        'validated': validated,
        'pending': by_status.get('pending', 0) + by_status.get('processing', 0),
        'failed_docs': by_status.get('failed', 0),
        'pass_rate': pass_rate,
        'avg_confidence': round(qs.aggregate(avg=Avg('confidence'))['avg'] or 0, 1),
        'recent_documents': qs[:8],
        'excel_available': HAS_OPENPYXL,
        'pdf_available': HAS_REPORTLAB,
    })


@login_required
def csv_export(request):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(HEADERS)
    writer.writerows(_rows(request.user))
    response = HttpResponse('\ufeff' + buffer.getvalue(), content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="bhoomiai-report.csv"'
    return response


@login_required
def excel_export(request):
    if not HAS_OPENPYXL:
        response = csv_export(request)
        response['Content-Disposition'] = 'attachment; filename="bhoomiai-report.csv"'
        return response

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = 'Land Records'
    sheet.append(HEADERS)
    header_fill = PatternFill('solid', fgColor='17365D')
    for cell in sheet[1]:
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = header_fill
    for row in _rows(request.user):
        sheet.append(row)
    widths = [6, 32, 16, 18, 14, 22, 12, 16, 20]
    for index, width in enumerate(widths, start=1):
        sheet.column_dimensions[chr(64 + index)].width = width
    sheet.freeze_panes = 'A2'

    buffer = io.BytesIO()
    workbook.save(buffer)
    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = 'attachment; filename="bhoomiai-report.xlsx"'
    return response


@login_required
def pdf_export(request):
    if not HAS_REPORTLAB:
        return csv_export(request)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=28,
        rightMargin=28,
        topMargin=32,
        bottomMargin=28,
        title='BhoomiAI Report',
    )
    styles = getSampleStyleSheet()
    elements = [
        Paragraph('BhoomiAI - Land Record Report', styles['Title']),
        Spacer(1, 10),
        Paragraph(
            f'Generated for {request.user.get_username()} on '
            f'{__import__("datetime").datetime.now():%d %b %Y %H:%M}',
            styles['Normal'],
        ),
        Spacer(1, 16),
    ]

    rows = _rows(request.user)
    if rows:
        table_data = [HEADERS] + rows
        table = Table(table_data, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#17365D')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#C9D3DF')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F3F6FA')]),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(table)
    else:
        elements.append(Paragraph('No documents available yet.', styles['Normal']))

    doc.build(elements)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="bhoomiai-report.pdf"'
    return response
