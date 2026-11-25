"""Views for projects, predictions, analytics, mitigation and model pages."""

from __future__ import annotations

import csv
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import ml, services
from .forms import ImportForm, MonitoringFilterForm, PredictionForm, ProjectForm
from .models import (
    ActivityLog,
    LandAcquisitionProject,
    MitigationPlan,
    ModelVersion,
    ProjectPrediction,
)

PAGE_SIZE = 20


def _states():
    return list(
        LandAcquisitionProject.objects.filter(archived=False)
        .values_list('state', flat=True).distinct().order_by('state')
    )


def _filtered_projects(request):
    queryset = services.annotated_projects()
    form = MonitoringFilterForm(request.GET or None, states=_states())
    if form.is_valid():
        data = form.cleaned_data
        if data.get('q'):
            query = data['q']
            queryset = queryset.filter(
                Q(project_id__icontains=query)
                | Q(project_name__icontains=query)
                | Q(district__icontains=query)
                | Q(state__icontains=query)
            )
        if data.get('state'):
            queryset = queryset.filter(state=data['state'])
        if data.get('status'):
            queryset = queryset.filter(status=data['status'])
        if data.get('risk'):
            queryset = queryset.filter(latest_risk=data['risk'])
        sort = data.get('sort')
        ordering = {
            'risk': ('-latest_probability', '-updated_at'),
            'progress': ('acquisition_pct', '-updated_at'),
            'compensation': ('compensation_completion_percentage', '-updated_at'),
            'delay': ('-latest_delay_days', '-updated_at'),
            'name': ('project_name',),
        }.get(sort)
        if ordering:
            queryset = queryset.order_by(*ordering)
    return queryset, form


@login_required
def project_list(request):
    queryset, form = _filtered_projects(request)
    paginator = Paginator(queryset, PAGE_SIZE)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'predictions/project_list.html', {
        'page_obj': page,
        'projects': page.object_list,
        'filter_form': form,
        'total_count': queryset.count(),
        'states': _states(),
    })


@login_required
def project_create(request):
    if request.method == 'POST':
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save(commit=False)
            project.created_by = request.user
            project.is_synthetic = False
            project.save()
            services.log_activity(request.user, 'project_created', 'LandAcquisitionProject', project.pk, project.project_name)
            messages.success(request, f'Project {project.project_id} created.')
            return redirect('predictions:project_detail', pk=project.pk)
    else:
        form = ProjectForm()
    return render(request, 'predictions/project_form.html', {
        'form': form,
        'title': 'Add New Project',
        'subtitle': 'Create a land-acquisition project record. You can run a delay prediction immediately afterwards.',
        'states': _states(),
    })


@login_required
def project_detail(request, pk):
    project = get_object_or_404(LandAcquisitionProject, pk=pk)
    prediction = project.latest_prediction
    history = project.predictions.select_related('model_version').order_by('-created_at')[:10]
    plans = project.mitigation_plans.select_related('prediction').order_by('-created_at')[:10]
    return render(request, 'predictions/project_detail.html', {
        'project': project,
        'prediction': prediction,
        'factors': prediction.factors.all() if prediction else [],
        'history': history,
        'plans': plans,
        'risk_profile': project.risk_profile,
        'phase': project.current_phase,
    })


@login_required
def project_edit(request, pk):
    project = get_object_or_404(LandAcquisitionProject, pk=pk)
    if request.method == 'POST':
        form = ProjectForm(request.POST, instance=project)
        if form.is_valid():
            project = form.save()
            services.log_activity(request.user, 'project_updated', 'LandAcquisitionProject', project.pk, project.project_name)
            messages.success(request, 'Project updated.')
            return redirect('predictions:project_detail', pk=project.pk)
    else:
        form = ProjectForm(instance=project)
    return render(request, 'predictions/project_form.html', {
        'form': form,
        'project': project,
        'title': 'Edit Project',
        'subtitle': f'Update the current-state snapshot for {project.project_id}.',
        'states': _states(),
    })


@login_required
def project_delete(request, pk):
    project = get_object_or_404(LandAcquisitionProject, pk=pk)
    if request.method == 'POST':
        identifier = project.project_id
        project.delete()
        services.log_activity(request.user, 'project_deleted', 'LandAcquisitionProject', pk, identifier)
        messages.success(request, f'Project {identifier} deleted.')
        return redirect('predictions:project_list')
    return render(request, 'predictions/project_confirm_delete.html', {'project': project})


@login_required
@require_POST
def project_archive(request, pk):
    project = get_object_or_404(LandAcquisitionProject, pk=pk)
    project.archived = not project.archived
    project.save(update_fields=['archived', 'updated_at'])
    action = 'archived' if project.archived else 'restored'
    services.log_activity(request.user, f'project_{action}', 'LandAcquisitionProject', project.pk, project.project_name)
    messages.success(request, f'Project {project.project_id} {action}.')
    return redirect('predictions:project_detail', pk=project.pk)


@login_required
@require_POST
def project_predict(request, pk):
    project = get_object_or_404(LandAcquisitionProject, pk=pk)
    prediction = services.run_prediction(project, user=request.user)
    messages.success(
        request,
        f'Prediction complete: {prediction.probability_percent}% delay probability '
        f'({prediction.risk_level} risk).',
    )
    return redirect('predictions:project_detail', pk=project.pk)


@login_required
def predict_scenario(request):
    project = None
    project_id = request.GET.get('project') or request.POST.get('project')
    if project_id:
        project = LandAcquisitionProject.objects.filter(pk=project_id).first()

    initial = {}
    if project:
        for field in PredictionForm.PROJECT_FIELDS:
            initial[field] = getattr(project, field)
    else:
        initial = {
            'compensation_status': 'in_progress',
            'compensation_completion_percentage': 45,
            'approval_status': 'in_progress',
            'environmental_clearance_status': 'cleared',
            'rehabilitation_status': 'in_progress',
            'project_duration_months': 24,
            'elapsed_months': 10,
            'land_area_acres': 250,
            'total_land_parcels': 420,
            'acquired_land_parcels': 150,
            'project_budget': 180,
            'allocated_budget': 160,
            'ownership_disputes': 3,
            'legal_case_count': 2,
            'stakeholder_issues': 2,
            'start_date': date.today() - timedelta(days=304),
        }

    if request.method == 'POST':
        form = PredictionForm(request.POST)
        if form.is_valid():
            selected = form.cleaned_data.get('project')
            if selected:
                project = form.apply_to_project(selected)
                project.save()
                services.log_activity(
                    request.user, 'project_snapshot_updated', 'LandAcquisitionProject',
                    project.pk, project.project_name,
                )
            else:
                project = LandAcquisitionProject(
                    project_name=form.cleaned_data['project_name'],
                    state=form.cleaned_data['state'],
                    district=form.cleaned_data['district'],
                    project_type=form.cleaned_data['project_type'],
                    created_by=request.user,
                    is_synthetic=False,
                )
                form.apply_to_project(project)
                project.save()
                services.log_activity(
                    request.user, 'project_created', 'LandAcquisitionProject',
                    project.pk, project.project_name,
                )
            prediction = services.run_prediction(project, user=request.user)
            messages.success(request, 'Delay prediction generated and saved.')
            return redirect('predictions:prediction_detail', pk=prediction.pk)
    else:
        form = PredictionForm(initial=initial)

    return render(request, 'predictions/predict.html', {
        'form': form,
        'selected_project': project,
        'model_ready': ml.model_ready(),
    })


@login_required
def prediction_detail(request, pk):
    prediction = get_object_or_404(
        ProjectPrediction.objects.select_related('project', 'model_version'), pk=pk
    )
    return render(request, 'predictions/prediction_detail.html', {
        'prediction': prediction,
        'project': prediction.project,
        'factors': prediction.factors.all(),
        'plans': prediction.mitigation_plans.all(),
        'risk_profile': prediction.project.risk_profile,
    })


@login_required
def prediction_history(request):
    queryset = ProjectPrediction.objects.select_related('project', 'model_version', 'predicted_by')
    risk = request.GET.get('risk')
    if risk in {'Low', 'Medium', 'High'}:
        queryset = queryset.filter(risk_level=risk)
    query = request.GET.get('q', '').strip()
    if query:
        queryset = queryset.filter(
            Q(project__project_id__icontains=query)
            | Q(project__project_name__icontains=query)
            | Q(project__district__icontains=query)
        )
    paginator = Paginator(queryset, 25)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'predictions/prediction_history.html', {
        'page_obj': page,
        'predictions': page.object_list,
        'risk_filter': risk or '',
        'query': query,
        'total_count': queryset.count(),
    })


@login_required
def monitoring(request):
    queryset, form = _filtered_projects(request)
    paginator = Paginator(queryset, 25)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'predictions/monitoring.html', {
        'page_obj': page,
        'projects': page.object_list,
        'filter_form': form,
        'total_count': queryset.count(),
        'states': _states(),
    })


@login_required
def risk_analytics(request):
    return render(request, 'predictions/risk_analytics.html', services.risk_analytics_context(request))


@login_required
def mitigation_list(request):
    queryset = MitigationPlan.objects.select_related('project', 'prediction')
    status = request.GET.get('status')
    if status in dict(MitigationPlan.STATUS_CHOICES):
        queryset = queryset.filter(status=status)
    project_id = request.GET.get('project')
    if project_id:
        queryset = queryset.filter(project_id=project_id)
    paginator = Paginator(queryset, 25)
    page = paginator.get_page(request.GET.get('page'))
    counts = {
        key: MitigationPlan.objects.filter(status=key).count()
        for key, _label in MitigationPlan.STATUS_CHOICES
    }
    return render(request, 'predictions/mitigation_list.html', {
        'page_obj': page,
        'plans': page.object_list,
        'status_filter': status or '',
        'counts': counts,
        'total_count': queryset.count(),
    })


@login_required
@require_POST
def mitigation_update(request, pk):
    plan = get_object_or_404(MitigationPlan, pk=pk)
    new_status = request.POST.get('status')
    if new_status not in dict(MitigationPlan.STATUS_CHOICES):
        messages.error(request, 'Unknown mitigation status.')
        return redirect('predictions:mitigation_list')
    plan.status = new_status
    plan.completed_at = timezone.now() if new_status == 'completed' else None
    plan.save(update_fields=['status', 'completed_at', 'updated_at'])
    services.log_activity(request.user, 'mitigation_updated', 'MitigationPlan', plan.pk, f'{plan.title}: {new_status}')
    messages.success(request, f'Mitigation plan marked as {plan.get_status_display()}.')
    return redirect(request.POST.get('next') or 'predictions:mitigation_list')


@login_required
def model_performance(request):
    return render(request, 'predictions/model_performance.html', services.model_performance_context())


@login_required
@user_passes_test(lambda user: user.is_staff)
@require_POST
def train_model(request):
    try:
        model, metrics = services.train_and_register(user=request.user)
    except Exception as exc:  # surfaced to the UI rather than silently failing
        messages.error(request, f'Training failed: {exc}')
    else:
        messages.success(
            request,
            f'Trained {model.name} on {metrics["dataset"]["rows"]} rows. '
            f'ROC-AUC {metrics["algorithms"][metrics["selected"]]["roc_auc"]:.3f}.',
        )
    return redirect('predictions:model_performance')


@login_required
def data_import(request):
    form = ImportForm()
    if request.method == 'POST':
        if request.POST.get('action') == 'demo':
            try:
                result = services.reset_demo_data(user=request.user, rows=2400, predict=True)
            except Exception as exc:
                messages.error(request, f'Could not load demo dataset: {exc}')
            else:
                messages.success(
                    request,
                    f'Demo workspace rebuilt: {result["deleted"]} synthetic rows removed, '
                    f'{result["created"]} projects and {result["predictions"]} predictions created.',
                )
                return redirect('dashboard:home')
        else:
            form = ImportForm(request.POST, request.FILES)
            if form.is_valid():
                try:
                    imported = services.import_projects(request.FILES['file'], user=request.user)
                except Exception as exc:
                    messages.error(request, f'Import failed: {exc}')
                else:
                    predicted = 0
                    if form.cleaned_data.get('predict') and imported:
                        predicted = services.predict_many_projects(imported, user=request.user)
                    messages.success(
                        request,
                        f'Imported {len(imported)} projects'
                        + (f' and generated {predicted} predictions.' if predicted else '.'),
                    )
                    return redirect('predictions:project_list')
    from .synthetic import dataset_path
    import pandas as pd

    path = dataset_path()
    dataset_info = {'exists': path.exists(), 'path': str(path)}
    if path.exists():
        try:
            frame = pd.read_csv(path)
            dataset_info.update({
                'rows': len(frame),
                'delayed': int(frame['delay_status'].sum()) if 'delay_status' in frame else 0,
                'states': int(frame['state'].nunique()) if 'state' in frame else 0,
            })
        except Exception:
            pass
    return render(request, 'predictions/data_import.html', {
        'form': form,
        'dataset': dataset_info,
        'project_count': LandAcquisitionProject.objects.filter(archived=False).count(),
    })


@login_required
def csv_template(request):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="bhoomiai-project-template.csv"'
    writer = csv.writer(response)
    writer.writerow(ml.FEATURE_COLUMNS + ['project_name', 'start_date', 'is_synthetic'])
    writer.writerow([
        'Maharashtra', 'Pune', 'Highway Expansion', 240, 420, 150, 3,
        'in_progress', 45, 'in_progress', 'cleared', 2, 'in_progress',
        180, 160, 24, 10, 2, 55.0, 112.5,
        'Example Highway Corridor', date.today().isoformat(), 1,
    ])
    return response


@login_required
def settings_view(request):
    if request.method == 'POST':
        theme = request.POST.get('theme_preference')
        if theme in {'light', 'dark'}:
            request.user.theme_preference = theme
            request.user.save(update_fields=['theme_preference'])
            messages.success(request, 'Theme preference updated.')
            return redirect('predictions:settings')
    return render(request, 'predictions/settings.html', {
        'active_model': ModelVersion.objects.filter(is_active=True).first(),
        'model_ready': ml.model_ready(),
        'recent_activity': ActivityLog.objects.select_related('user')[:10],
        'dataset_path': str(__import__('predictions.synthetic', fromlist=['dataset_path']).dataset_path()),
        'thresholds': {
            'low': ml.RISK_LOW_THRESHOLD,
            'high': ml.RISK_HIGH_THRESHOLD,
        },
    })
