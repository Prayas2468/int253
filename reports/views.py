"""Report generation for the land-acquisition delay prediction platform.

Every export reads live database rows or the persisted model metrics; no figures
are hardcoded. CSV is always available, PDF uses reportlab and Excel uses openpyxl
when those packages are installed.
"""

import csv
import io

from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from predictions import ml, services
from predictions.models import LandAcquisitionProject, MitigationPlan, ModelVersion, ProjectPrediction

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


def _csv_response(filename, headers, rows):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    writer.writerows(rows)
    response = HttpResponse('\ufeff' + buffer.getvalue(), content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def _pdf_response(filename, title, subtitle, headers, rows, max_rows=600):
    if not HAS_REPORTLAB:
        return _csv_response(filename.replace('.pdf', '.csv'), headers, rows)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=24,
        rightMargin=24,
        topMargin=28,
        bottomMargin=24,
        title=title,
    )
    styles = getSampleStyleSheet()
    elements = [
        Paragraph(title, styles['Title']),
        Spacer(1, 6),
        Paragraph(subtitle, styles['Normal']),
        Spacer(1, 12),
    ]

    table_rows = rows[:max_rows]
    if table_rows:
        data = [headers] + [[str(cell) for cell in row] for row in table_rows]
        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1D4ED8')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 7),
            ('GRID', (0, 0), (-1, -1), 0.35, colors.HexColor('#CBD5E1')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F1F5F9')]),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(table)
        if len(rows) > max_rows:
            elements.append(Spacer(1, 8))
            elements.append(Paragraph(
                f'Showing the first {max_rows} of {len(rows)} rows. Use the CSV export for the full dataset.',
                styles['Normal'],
            ))
    else:
        elements.append(Paragraph('No records available for this report.', styles['Normal']))

    doc.build(elements)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ---------------------------------------------------------------------------
# Row builders
# ---------------------------------------------------------------------------

PROJECT_HEADERS = [
    'Project ID', 'Name', 'State', 'District', 'Type', 'Land area (ac)',
    'Total parcels', 'Acquired parcels', 'Acquisition %', 'Compensation %',
    'Approval', 'Clearance', 'Legal cases', 'Risk level', 'Delay probability', 'Status',
]


def _project_rows(queryset=None):
    queryset = queryset or services.annotated_projects()
    rows = []
    for project in queryset.order_by('project_id'):
        rows.append([
            project.project_id,
            project.project_name,
            project.state,
            project.district,
            project.project_type,
            round(project.land_area_acres, 1),
            project.total_land_parcels,
            project.acquired_land_parcels,
            project.acquisition_progress,
            round(project.compensation_completion_percentage, 1),
            project.get_approval_status_display(),
            project.get_environmental_clearance_status_display(),
            project.legal_case_count,
            project.risk_level,
            round((project.latest_probability or 0) * 100, 1),
            project.get_status_display(),
        ])
    return rows


PREDICTION_HEADERS = [
    'Prediction ID', 'Project ID', 'Project name', 'State', 'District',
    'Delay probability (%)', 'Risk level', 'Delay days', 'Estimated end',
    'Model', 'Model version', 'Predicted at',
]


def _prediction_rows(queryset=None):
    queryset = queryset or ProjectPrediction.objects.select_related('project', 'model_version')
    rows = []
    for item in queryset.order_by('-created_at'):
        rows.append([
            item.pk,
            item.project.project_id,
            item.project.project_name,
            item.project.state,
            item.project.district,
            item.probability_percent,
            item.risk_level,
            round(item.predicted_delay_days or 0, 1),
            item.estimated_completion_date.isoformat() if item.estimated_completion_date else '',
            item.model_version.algorithm if item.model_version else '',
            item.model_version.version if item.model_version else '',
            item.created_at.strftime('%Y-%m-%d %H:%M'),
        ])
    return rows


RISK_HEADERS = ['State', 'Projects', 'High risk', 'Medium risk', 'Low risk', 'Avg delay probability (%)']


def _risk_rows():
    context = services.risk_analytics_context(None)
    return [
        [row['state'], row['total'], row['high'], row['medium'], row['low'], row['avg_probability']]
        for row in context['state_risk']
    ]


MODEL_HEADERS = ['Algorithm', 'Accuracy', 'Precision', 'Recall', 'F1', 'ROC-AUC', 'True negative', 'False positive', 'False negative', 'True positive']


def _model_rows():
    metrics = ml.read_metrics()
    rows = []
    for name, values in metrics.get('algorithms', {}).items():
        matrix = values.get('confusion_matrix', [[0, 0], [0, 0]])
        rows.append([
            name, values.get('accuracy'), values.get('precision'), values.get('recall'),
            values.get('f1'), values.get('roc_auc'),
            matrix[0][0], matrix[0][1], matrix[1][0], matrix[1][1],
        ])
    return rows


MITIGATION_HEADERS = ['Project ID', 'Project name', 'Risk area', 'Plan', 'Priority', 'Status', 'Source', 'Created']


def _mitigation_rows():
    rows = []
    for plan in MitigationPlan.objects.select_related('project').order_by('-created_at'):
        rows.append([
            plan.project.project_id, plan.project.project_name, plan.risk_area,
            plan.title, plan.priority, plan.get_status_display(),
            'System suggested' if plan.generated_by_system else 'User created',
            plan.created_at.strftime('%Y-%m-%d %H:%M'),
        ])
    return rows


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

@login_required
def index(request):
    projects = services.annotated_projects()
    total = projects.count()
    risks = {
        'high': projects.filter(latest_risk='High').count(),
        'medium': projects.filter(latest_risk='Medium').count(),
        'low': projects.filter(latest_risk='Low').count(),
    }
    metrics = ml.read_metrics()
    selected = metrics.get('selected', '')
    selected_metrics = metrics.get('algorithms', {}).get(selected, {})
    return render(request, 'reports/index.html', {
        'total_projects': total,
        'high_risk': risks['high'],
        'medium_risk': risks['medium'],
        'low_risk': risks['low'],
        'prediction_count': ProjectPrediction.objects.count(),
        'mitigation_count': MitigationPlan.objects.count(),
        'model_ready': ml.model_ready(),
        'selected_algorithm': selected,
        'selected_metrics': selected_metrics,
        'model_versions': ModelVersion.objects.count(),
        'excel_available': HAS_OPENPYXL,
        'pdf_available': HAS_REPORTLAB,
        'recent_predictions': ProjectPrediction.objects.select_related('project')[:8],
        'generated_at': timezone.now(),
    })


@login_required
def projects_csv(request):
    return _csv_response('bhoomiai-projects.csv', PROJECT_HEADERS, _project_rows())


@login_required
def projects_pdf(request):
    return _pdf_response(
        'bhoomiai-projects.pdf',
        'Land Acquisition Project Register',
        'Predictive Analytics System for Early Detection of Land Acquisition Delays · synthetic dataset',
        PROJECT_HEADERS,
        _project_rows(),
    )


@login_required
def monitoring_csv(request):
    return _csv_response('bhoomiai-monitoring.csv', PROJECT_HEADERS, _project_rows())


@login_required
def monitoring_pdf(request):
    return _pdf_response(
        'bhoomiai-monitoring.pdf',
        'Project Monitoring Report',
        'Acquisition progress, compensation completion and model-generated risk levels',
        PROJECT_HEADERS,
        _project_rows(),
    )


@login_required
def predictions_csv(request):
    return _csv_response('bhoomiai-predictions.csv', PREDICTION_HEADERS, _prediction_rows())


@login_required
def predictions_pdf(request):
    return _pdf_response(
        'bhoomiai-predictions.pdf',
        'Prediction History Report',
        'Stored machine-learning predictions with probability, risk band and delay estimate',
        PREDICTION_HEADERS,
        _prediction_rows(),
    )


@login_required
def risk_csv(request):
    return _csv_response('bhoomiai-risk-analysis.csv', RISK_HEADERS, _risk_rows())


@login_required
def risk_pdf(request):
    return _pdf_response(
        'bhoomiai-risk-analysis.pdf',
        'Risk Analysis Report',
        'State-level delay-risk distribution from the latest stored prediction per project',
        RISK_HEADERS,
        _risk_rows(),
    )


@login_required
def model_csv(request):
    return _csv_response('bhoomiai-model-evaluation.csv', MODEL_HEADERS, _model_rows())


@login_required
def model_pdf(request):
    metrics = ml.read_metrics()
    dataset = metrics.get('dataset', {})
    subtitle = (
        f"Dataset rows: {dataset.get('rows', 0)} · delay rate {dataset.get('delay_rate', 0)} · "
        f"selected model: {metrics.get('selected', 'not trained')}"
    )
    return _pdf_response(
        'bhoomiai-model-evaluation.pdf',
        'Model Evaluation Report',
        subtitle,
        MODEL_HEADERS,
        _model_rows(),
    )


@login_required
def mitigation_csv(request):
    return _csv_response('bhoomiai-mitigation-plans.csv', MITIGATION_HEADERS, _mitigation_rows())


@login_required
def excel_export(request):
    rows = _project_rows()
    if not HAS_OPENPYXL:
        return projects_csv(request)

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = 'Projects'
    sheet.append(PROJECT_HEADERS)
    header_fill = PatternFill('solid', fgColor='1D4ED8')
    for cell in sheet[1]:
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = header_fill
    for row in rows:
        sheet.append(row)
    widths = [16, 34, 16, 16, 20, 14, 14, 15, 15, 16, 16, 18, 12, 12, 16, 14]
    for index, width in enumerate(widths, start=1):
        sheet.column_dimensions[chr(64 + index)].width = width
    sheet.freeze_panes = 'A2'
    buffer = io.BytesIO()
    workbook.save(buffer)
    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = 'attachment; filename="bhoomiai-projects.xlsx"'
    return response


# Legacy route aliases kept so older links continue to work.
@login_required
def csv_export(request):
    return projects_csv(request)


@login_required
def pdf_export(request):
    return projects_pdf(request)
