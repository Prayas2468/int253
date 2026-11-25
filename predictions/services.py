"""Application services: project import, prediction persistence and analytics."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
from django.db.models import Avg, Case, Count, ExpressionWrapper, F, FloatField, OuterRef, Subquery, When
from django.utils import timezone

from . import ml
from .models import (
    ActivityLog,
    LandAcquisitionProject,
    MitigationPlan,
    ModelVersion,
    PredictionFactor,
    ProjectPrediction,
)

RISK_ORDER = {'High': 0, 'Medium': 1, 'Low': 2}
PHASE_ORDER = [
    'Initial Assessment',
    'Land Identification',
    'Ownership Verification',
    'Compensation',
    'Legal Clearance',
    'Acquisition Completion',
]

ACTION_MAP = {
    'Ownership disputes': (
        'Land Ownership',
        'Open an ownership verification review for disputed parcels and prioritise unresolved claims.',
    ),
    'Pending compensation': (
        'Compensation',
        'Release pending compensation and set a weekly payment-completion target.',
    ),
    'Legal cases': (
        'Legal',
        'Assign counsel to pending cases and track hearing dates in the project register.',
    ),
    'Approval bottleneck': (
        'Approval',
        'Escalate pending approvals with the responsible department and set a follow-up date.',
    ),
    'Environmental clearance': (
        'Environmental',
        'Track clearance milestones and prepare mitigation documentation for the review committee.',
    ),
    'Rehabilitation pending': (
        'Rehabilitation',
        'Complete rehabilitation entitlements before issuing possession notices.',
    ),
    'Stakeholder issues': (
        'Stakeholder',
        'Schedule stakeholder consultations and record commitments in the mitigation register.',
    ),
    'Acquisition progress lag': (
        'Acquisition',
        'Re-baseline the acquisition schedule or add field-verification capacity.',
    ),
    'Budget allocation gap': (
        'Budget',
        'Request additional allocation or phase the acquisition scope to match available funds.',
    ),
}

RISK_ACTION_FALLBACK = {
    'Land Ownership': 'Review ownership records for the affected parcels.',
    'Compensation': 'Review the compensation pipeline and pending payments.',
    'Legal': 'Review pending litigation and prioritise unresolved cases.',
    'Approval': 'Follow up on pending departmental approvals.',
    'Environmental': 'Follow up on environmental clearance milestones.',
    'Rehabilitation': 'Review rehabilitation entitlements and completion status.',
}


def log_activity(user, action, entity_type='', entity_id='', detail=''):
    return ActivityLog.objects.create(
        user=user if getattr(user, 'is_authenticated', False) else None,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id or ''),
        detail=detail[:255],
    )


def annotated_projects(include_archived=False):
    """Projects annotated with their latest prediction to avoid N+1 queries."""
    latest = ProjectPrediction.objects.filter(project=OuterRef('pk')).order_by('-created_at')
    queryset = LandAcquisitionProject.objects.all()
    if not include_archived:
        queryset = queryset.filter(archived=False)
    progress = Case(
        When(total_land_parcels=0, then=0.0),
        default=ExpressionWrapper(
            F('acquired_land_parcels') * 100.0 / F('total_land_parcels'),
            output_field=FloatField(),
        ),
        output_field=FloatField(),
    )
    return queryset.annotate(
        acquisition_pct=progress,
        latest_probability=Subquery(latest.values('delay_probability')[:1]),
        latest_risk=Subquery(latest.values('risk_level')[:1]),
        latest_delay_days=Subquery(latest.values('predicted_delay_days')[:1]),
        latest_prediction_id=Subquery(latest.values('pk')[:1]),
        latest_predicted_at=Subquery(latest.values('created_at')[:1]),
    )


def get_active_model_version():
    return ModelVersion.objects.filter(is_active=True).order_by('-trained_at').first()


def train_and_register(user=None):
    metrics = ml.train_models()
    version = metrics.get('generated_at', timezone.now().isoformat())[:19].replace(':', '')
    model = ModelVersion.objects.create(
        name=f"{metrics.get('selected', 'Random Forest')} delay classifier",
        algorithm=metrics.get('selected', 'Random Forest'),
        version=version,
        metrics=metrics,
        artifact_path=str(ml.CLASSIFIER_PATH),
        training_rows=metrics.get('dataset', {}).get('rows', 0),
        is_active=True,
        notes='Trained from the synthetic land-acquisition dataset.',
    )
    ModelVersion.objects.exclude(pk=model.pk).update(is_active=False)
    log_activity(user, 'model_trained', 'ModelVersion', model.pk, f'{model.name} {model.version}')
    return model, metrics


def ensure_model_version(result=None):
    model = get_active_model_version()
    if model:
        return model
    metrics = (result or {}).get('metrics') or ml.read_metrics()
    if not metrics:
        return None
    version = metrics.get('generated_at', timezone.now().isoformat())[:19].replace(':', '')
    model = ModelVersion.objects.create(
        name=f"{metrics.get('selected', 'Random Forest')} delay classifier",
        algorithm=metrics.get('selected', 'Random Forest'),
        version=version,
        metrics=metrics,
        artifact_path=str(ml.CLASSIFIER_PATH),
        training_rows=metrics.get('dataset', {}).get('rows', 0),
        is_active=True,
        notes='Registered automatically from the persisted pipeline.',
    )
    return model


def create_prediction(project, result, user=None, generate_plans=True):
    model = ensure_model_version(result)
    prediction = ProjectPrediction.objects.create(
        project=project,
        delay_probability=result['delay_probability'],
        risk_level=result['risk_level'],
        predicted_delay_days=result['predicted_delay_days'],
        estimated_completion_date=result['estimated_completion_date'],
        model_version=model,
        predicted_by=user if getattr(user, 'is_authenticated', False) else None,
        inputs_snapshot=result.get('feature_row', {}),
    )
    factors = [
        PredictionFactor(
            prediction=prediction,
            factor_name=factor['factor_name'],
            impact=factor['impact'],
            direction=factor['direction'],
            description=factor['description'],
        )
        for factor in result.get('factors', [])
    ]
    if factors:
        PredictionFactor.objects.bulk_create(factors)

    if generate_plans:
        build_mitigation_plans(project, prediction, user)

    project.refresh_status()
    project.save(update_fields=['status', 'updated_at'])
    log_activity(
        user, 'prediction_created', 'ProjectPrediction', prediction.pk,
        f'{project.project_id}: {prediction.probability_percent}% ({prediction.risk_level})',
    )
    return prediction


def run_prediction(project, user=None):
    result = ml.predict_delay(project)
    return create_prediction(project, result, user=user)


def build_mitigation_plans(project, prediction, user=None):
    """Replace un-actioned system suggestions with fresh ones for this prediction."""
    MitigationPlan.objects.filter(
        project=project, status='suggested', generated_by_system=True
    ).delete()
    plans = []
    for factor in prediction.factors.all()[:5]:
        mapping = ACTION_MAP.get(factor.factor_name)
        if not mapping:
            continue
        risk_area, description = mapping
        priority = 'High' if prediction.risk_level == 'High' else 'Medium'
        if factor.impact < 0.02:
            priority = 'Low'
        plans.append(MitigationPlan(
            project=project,
            prediction=prediction,
            risk_area=risk_area,
            title=f'Mitigate {risk_area.lower()} risk',
            description=description,
            priority=priority,
            status='suggested',
            generated_by_system=True,
            created_by=user if getattr(user, 'is_authenticated', False) else None,
        ))
    if not plans:
        risk_area = max(project.risk_scores, key=project.risk_scores.get)
        plans.append(MitigationPlan(
            project=project,
            prediction=prediction,
            risk_area=risk_area,
            title=f'Review {risk_area.lower()} risk',
            description=RISK_ACTION_FALLBACK.get(risk_area, 'Review the project risk profile.'),
            priority='Medium',
            status='suggested',
            generated_by_system=True,
        ))
    MitigationPlan.objects.bulk_create(plans)
    return plans


def _row_to_project(row, index=0):
    def value(key, default=''):
        raw = row.get(key, default)
        if pd.isna(raw):
            return default
        return raw

    total = int(float(value('total_land_parcels', 0) or 0))
    acquired = int(float(value('acquired_land_parcels', 0) or 0))
    duration = max(1, int(float(value('project_duration_months', 12) or 12)))
    elapsed = max(0, int(float(value('elapsed_months', 0) or 0)))
    start = value('start_date', '')
    if start:
        try:
            start = pd.to_datetime(start).date()
        except (ValueError, TypeError):
            start = date.today() - timedelta(days=int(elapsed * 30.44))
    else:
        start = date.today() - timedelta(days=int(elapsed * 30.44))

    project = LandAcquisitionProject(
        project_id=str(value('project_id', '') or '').strip(),
        project_name=str(value('project_name', '') or f'Imported project {index + 1}'),
        state=str(value('state', 'Unknown') or 'Unknown'),
        district=str(value('district', 'Unknown') or 'Unknown'),
        project_type=str(value('project_type', 'Other') or 'Other'),
        land_area_acres=float(value('land_area_acres', 0) or 0),
        total_land_parcels=total,
        acquired_land_parcels=min(acquired, total),
        ownership_disputes=int(float(value('ownership_disputes', 0) or 0)),
        compensation_status=str(value('compensation_status', 'pending') or 'pending'),
        compensation_completion_percentage=float(value('compensation_completion_percentage', 0) or 0),
        approval_status=str(value('approval_status', 'pending') or 'pending'),
        environmental_clearance_status=str(value('environmental_clearance_status', 'pending') or 'pending'),
        legal_case_count=int(float(value('legal_case_count', 0) or 0)),
        rehabilitation_status=str(value('rehabilitation_status', 'not_started') or 'not_started'),
        project_budget=float(value('project_budget', 0) or 0),
        allocated_budget=float(value('allocated_budget', 0) or 0),
        project_duration_months=duration,
        elapsed_months=elapsed,
        stakeholder_issues=int(float(value('stakeholder_issues', 0) or 0)),
        start_date=start,
        is_synthetic=bool(int(float(value('is_synthetic', 1) or 1))),
    )
    for field, valid in (
        ('compensation_status', dict(LandAcquisitionProject.COMPENSATION_STATUS)),
        ('approval_status', dict(LandAcquisitionProject.APPROVAL_STATUS)),
        ('environmental_clearance_status', dict(LandAcquisitionProject.CLEARANCE_STATUS)),
        ('rehabilitation_status', dict(LandAcquisitionProject.REHABILITATION_STATUS)),
    ):
        if getattr(project, field) not in valid:
            setattr(project, field, next(iter(valid)))
    project.refresh_status()
    return project


def seed_projects_from_dataset(predict=True, limit=None, user=None):
    from .synthetic import dataset_path

    path = dataset_path()
    if not path.exists():
        raise FileNotFoundError(
            f'Synthetic dataset not found at {path}. Run: python manage.py generate_synthetic_data'
        )
    frame = pd.read_csv(path)
    if limit:
        frame = frame.head(limit)

    existing = set(LandAcquisitionProject.objects.values_list('project_id', flat=True))
    new_projects = []
    for index, row in frame.iterrows():
        project = _row_to_project(row, index)
        if project.project_id and project.project_id in existing:
            continue
        if not project.project_id:
            project.project_id = LandAcquisitionProject._next_project_id()
        project.created_by = user if getattr(user, 'is_authenticated', False) else None
        new_projects.append(project)
        existing.add(project.project_id)

    LandAcquisitionProject.objects.bulk_create(new_projects, batch_size=500)
    created = len(new_projects)

    prediction_count = 0
    if predict and new_projects:
        if not ml.model_ready():
            train_and_register(user=user)
        results = ml.predict_batch(new_projects)
        model = ensure_model_version(results[0] if results else None)
        predictions = []
        factor_rows = []
        plan_rows = []
        for project, result in zip(new_projects, results):
            prediction = ProjectPrediction(
                project=project,
                delay_probability=result['delay_probability'],
                risk_level=result['risk_level'],
                predicted_delay_days=result['predicted_delay_days'],
                estimated_completion_date=result['estimated_completion_date'],
                model_version=model,
                predicted_by=user if getattr(user, 'is_authenticated', False) else None,
                inputs_snapshot=result.get('feature_row', {}),
            )
            predictions.append(prediction)
        ProjectPrediction.objects.bulk_create(predictions, batch_size=500)

        for prediction, result in zip(predictions, results):
            for factor in result.get('factors', [])[:5]:
                mapping = ACTION_MAP.get(factor['factor_name'])
                factor_rows.append(PredictionFactor(
                    prediction=prediction,
                    factor_name=factor['factor_name'],
                    impact=factor['impact'],
                    direction=factor['direction'],
                    description=factor['description'],
                ))
                if mapping:
                    risk_area, description = mapping
                    plan_rows.append(MitigationPlan(
                        project=prediction.project,
                        prediction=prediction,
                        risk_area=risk_area,
                        title=f'Mitigate {risk_area.lower()} risk',
                        description=description,
                        priority='High' if prediction.risk_level == 'High' else 'Medium',
                        status='suggested',
                        generated_by_system=True,
                        created_by=user if getattr(user, 'is_authenticated', False) else None,
                    ))
        if factor_rows:
            PredictionFactor.objects.bulk_create(factor_rows, batch_size=1000)
        if plan_rows:
            MitigationPlan.objects.bulk_create(plan_rows, batch_size=1000)
        prediction_count = len(predictions)

    log_activity(user, 'dataset_imported', 'LandAcquisitionProject', '', f'{created} projects imported')
    return {'created': created, 'predictions': prediction_count}


def reset_demo_data(user=None, rows=2400, predict=True):
    from .synthetic import write_dataset

    write_dataset(rows=rows)
    deleted, _ = LandAcquisitionProject.objects.filter(is_synthetic=True).delete()
    result = seed_projects_from_dataset(predict=predict, user=user)
    result['deleted'] = deleted
    log_activity(user, 'demo_data_reset', 'LandAcquisitionProject', '', f'deleted {deleted}, created {result["created"]}')
    return result


def import_projects(file, user=None):
    frame = pd.read_csv(file)
    required = {'project_name', 'state', 'district', 'project_type', 'total_land_parcels'}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f'Missing required columns: {", ".join(sorted(missing))}')
    existing = set(LandAcquisitionProject.objects.values_list('project_id', flat=True))
    projects = []
    base_id = LandAcquisitionProject._next_project_id()
    try:
        sequence = int(base_id.rsplit('-', 1)[1])
    except (IndexError, ValueError):
        sequence = 1
    for index, row in frame.iterrows():
        project = _row_to_project(row, index)
        if project.project_id in existing:
            continue
        if not project.project_id:
            project.project_id = f'LA-{timezone.now().year}-{sequence:04d}'
            sequence += 1
        project.created_by = user if getattr(user, 'is_authenticated', False) else None
        projects.append(project)
        existing.add(project.project_id)
    LandAcquisitionProject.objects.bulk_create(projects, batch_size=500)
    log_activity(user, 'projects_imported', 'LandAcquisitionProject', '', f'{len(projects)} projects imported')
    return projects


def predict_many_projects(projects, user=None):
    """Run predictions for an existing list of projects and persist the results."""
    projects = list(projects)
    if not projects:
        return 0
    if not ml.model_ready():
        train_and_register(user=user)
    results = ml.predict_batch(projects)
    model = ensure_model_version(results[0] if results else None)
    predictions = [
        ProjectPrediction(
            project=project,
            delay_probability=result['delay_probability'],
            risk_level=result['risk_level'],
            predicted_delay_days=result['predicted_delay_days'],
            estimated_completion_date=result['estimated_completion_date'],
            model_version=model,
            predicted_by=user if getattr(user, 'is_authenticated', False) else None,
            inputs_snapshot=result.get('feature_row', {}),
        )
        for project, result in zip(projects, results)
    ]
    ProjectPrediction.objects.bulk_create(predictions, batch_size=500)
    factor_rows = []
    plan_rows = []
    for prediction, result in zip(predictions, results):
        for factor in result.get('factors', [])[:5]:
            factor_rows.append(PredictionFactor(
                prediction=prediction,
                factor_name=factor['factor_name'],
                impact=factor['impact'],
                direction=factor['direction'],
                description=factor['description'],
            ))
            mapping = ACTION_MAP.get(factor['factor_name'])
            if mapping:
                risk_area, description = mapping
                plan_rows.append(MitigationPlan(
                    project=prediction.project,
                    prediction=prediction,
                    risk_area=risk_area,
                    title=f'Mitigate {risk_area.lower()} risk',
                    description=description,
                    priority='High' if prediction.risk_level == 'High' else 'Medium',
                    status='suggested',
                    generated_by_system=True,
                    created_by=user if getattr(user, 'is_authenticated', False) else None,
                ))
    if factor_rows:
        PredictionFactor.objects.bulk_create(factor_rows, batch_size=1000)
    if plan_rows:
        MitigationPlan.objects.bulk_create(plan_rows, batch_size=1000)
    log_activity(user, 'predictions_generated', 'ProjectPrediction', '', f'{len(predictions)} predictions stored')
    return len(predictions)


# ---------------------------------------------------------------------------
# Dashboard and analytics aggregations
# ---------------------------------------------------------------------------

def _risk_counts(queryset):
    return {
        'high': queryset.filter(latest_risk='High').count(),
        'medium': queryset.filter(latest_risk='Medium').count(),
        'low': queryset.filter(latest_risk='Low').count(),
    }


def _progress_series(queryset):
    rows = list(queryset.values_list(
        'elapsed_months', 'project_duration_months',
        'total_land_parcels', 'acquired_land_parcels',
    ))
    if not rows:
        return {'labels': [], 'planned': [], 'actual': []}
    buckets = [
        (1, 3), (4, 6), (7, 9), (10, 12), (13, 15), (16, 18),
        (19, 21), (22, 24), (25, 30), (31, 36), (37, 48), (49, 120),
    ]
    labels, planned, actual = [], [], []
    for start, end in buckets:
        subset = [row for row in rows if start <= row[0] <= end]
        if not subset:
            continue
        labels.append(f'M{start}' if start == end else f'M{start}–{end}')
        planned.append(round(sum(
            min(100, (row[0] / row[1]) * 100) for row in subset if row[1]
        ) / max(1, len([row for row in subset if row[1]])), 1))
        actual.append(round(sum(
            (row[3] / row[2]) * 100 for row in subset if row[2]
        ) / max(1, len([row for row in subset if row[2]])), 1))
    return {'labels': labels, 'planned': planned, 'actual': actual}


def _state_risk(queryset):
    totals = {}
    for state, risk, probability in queryset.values_list('state', 'latest_risk', 'latest_probability'):
        row = totals.setdefault(state, {'state': state, 'total': 0, 'high': 0, 'medium': 0, 'low': 0, 'probability_sum': 0.0, 'probability_n': 0})
        row['total'] += 1
        if risk == 'High':
            row['high'] += 1
        elif risk == 'Medium':
            row['medium'] += 1
        elif risk == 'Low':
            row['low'] += 1
        if probability is not None:
            row['probability_sum'] += probability
            row['probability_n'] += 1
    rows = []
    for row in totals.values():
        n = row.pop('probability_n')
        row['avg_probability'] = round((row.pop('probability_sum') / n) * 100, 1) if n else 0
        rows.append(row)
    return sorted(rows, key=lambda item: (-item['high'], -item['avg_probability']))


def _district_risk(queryset):
    totals = {}
    for district, state, risk in queryset.values_list('district', 'state', 'latest_risk'):
        row = totals.setdefault((state, district), {'district': district, 'state': state, 'total': 0, 'high': 0})
        row['total'] += 1
        if risk == 'High':
            row['high'] += 1
    return sorted(totals.values(), key=lambda item: (-item['high'], -item['total']))[:12]


def _compensation_buckets(queryset):
    buckets = [
        ('0–25%', 0, 25), ('26–50%', 25.01, 50), ('51–75%', 50.01, 75),
        ('76–99%', 75.01, 99.49), ('100%', 99.5, 100.01),
    ]
    rows = []
    for label, low, high in buckets:
        subset = queryset.filter(
            compensation_completion_percentage__gte=low,
            compensation_completion_percentage__lt=high,
        )
        total = subset.count()
        high_risk = subset.filter(latest_risk='High').count()
        rows.append({
            'label': label,
            'total': total,
            'high_risk': high_risk,
            'delay_rate': round((subset.filter(latest_probability__gte=0.5).count() / total) * 100, 1) if total else 0,
        })
    return rows


def _approval_analysis(queryset):
    rows = []
    labels = dict(LandAcquisitionProject.APPROVAL_STATUS)
    for status, _label in LandAcquisitionProject.APPROVAL_STATUS:
        subset = queryset.filter(approval_status=status)
        total = subset.count()
        avg = subset.aggregate(avg=Avg('latest_probability'))['avg']
        rows.append({
            'status': labels[status],
            'total': total,
            'high_risk': subset.filter(latest_risk='High').count(),
            'avg_probability': round((avg or 0) * 100, 1),
        })
    return rows


def _legal_analysis(queryset):
    buckets = [('0 cases', 0, 0), ('1–2 cases', 1, 2), ('3–5 cases', 3, 5), ('6+ cases', 6, 99)]
    rows = []
    for label, low, high in buckets:
        subset = queryset.filter(legal_case_count__gte=low, legal_case_count__lte=high)
        total = subset.count()
        rows.append({
            'label': label,
            'total': total,
            'delay_rate': round((subset.filter(latest_probability__gte=0.5).count() / total) * 100, 1) if total else 0,
        })
    return rows


def _phase_distribution(queryset):
    counts = {phase: 0 for phase in PHASE_ORDER}
    for project in queryset.only(
        'total_land_parcels', 'acquired_land_parcels',
        'compensation_completion_percentage', 'legal_case_count',
        'approval_status', 'ownership_disputes',
    ):
        counts[project.current_phase] = counts.get(project.current_phase, 0) + 1
    return [{'phase': phase, 'count': counts[phase]} for phase in PHASE_ORDER if counts[phase]]


def _risk_factor_for(project, scores=None):
    scores = scores or project.risk_scores
    key = max(scores, key=scores.get)
    return key, scores[key], RISK_ACTION_FALLBACK.get(key, 'Review project risk factors.')


def latest_prediction_rows(queryset, limit=None):
    projects = list(queryset.order_by('-latest_probability', '-updated_at')[:limit] if limit else queryset)
    rows = []
    for project in projects:
        prediction = project.latest_prediction
        if not prediction:
            continue
        key, score, action = _risk_factor_for(project)
        rows.append({
            'project': project,
            'prediction': prediction,
            'risk_area': key,
            'risk_score': score,
            'action': action,
            'probability': prediction.probability_percent,
        })
    return rows


def monitoring_rows(queryset):
    rows = []
    for project in queryset:
        rows.append({
            'project': project,
            'probability': round((project.latest_probability or 0) * 100, 1),
            'risk': project.latest_risk or project.risk_level,
            'delay_days': project.latest_delay_days,
            'status': project.get_status_display(),
        })
    return rows


def dashboard_context(request):
    queryset = annotated_projects()
    total = queryset.count()
    risks = _risk_counts(queryset)
    predicted_delayed = queryset.filter(latest_probability__gte=0.5).count()
    on_track = max(0, total - predicted_delayed)
    avg_acquisition = queryset.aggregate(avg=Avg('acquisition_pct'))['avg'] or 0
    avg_compensation = queryset.aggregate(avg=Avg('compensation_completion_percentage'))['avg'] or 0

    focus_id = request.GET.get('project')
    focus = None
    if focus_id:
        focus = queryset.filter(pk=focus_id).first()
    if not focus:
        focus = queryset.filter(latest_probability__isnull=False).order_by('-latest_probability').first()
    if not focus:
        focus = queryset.order_by('-updated_at').first()

    focus_prediction = focus.latest_prediction if focus else None
    focus_profile = focus.risk_profile if focus else []
    focus_factor, focus_score, focus_action = _risk_factor_for(focus) if focus else ('', 0, '')

    top_risks = latest_prediction_rows(queryset, limit=8)
    monitoring = monitoring_rows(queryset.order_by('-latest_probability', '-updated_at')[:10])
    progress = _progress_series(queryset)
    phases = _phase_distribution(queryset)
    states = _state_risk(queryset)
    recommendations = list(
        MitigationPlan.objects.filter(project__in=queryset, status='suggested')
        .select_related('project')[:6]
    )

    spark_base = queryset.order_by('-updated_at')[:12]
    spark_probability = [round((row.latest_probability or 0) * 100, 1) for row in spark_base]
    spark_compensation = [round(row.compensation_completion_percentage, 1) for row in spark_base]

    return {
        'total_projects': total,
        'high_risk': risks['high'],
        'medium_risk': risks['medium'],
        'low_risk': risks['low'],
        'predicted_delayed': predicted_delayed,
        'on_track': on_track,
        'avg_acquisition': round(avg_acquisition, 1),
        'avg_compensation': round(avg_compensation, 1),
        'focus': focus,
        'focus_prediction': focus_prediction,
        'focus_profile': focus_profile,
        'focus_factor': focus_factor,
        'focus_score': focus_score,
        'focus_action': focus_action,
        'top_risks': top_risks,
        'monitoring_rows': monitoring,
        'progress': progress,
        'phases': phases,
        'state_risk': states[:8],
        'recommendations': recommendations,
        'spark_probability': spark_probability,
        'spark_compensation': spark_compensation,
        'model_ready': ml.model_ready(),
        'analytics_data': {
            'progress': progress,
            'phases': phases,
            'risk': [
                {'label': 'High', 'value': risks['high']},
                {'label': 'Medium', 'value': risks['medium']},
                {'label': 'Low', 'value': risks['low']},
            ],
            'stateRisk': states,
            'predictionTrend': _prediction_trend(),
        },
    }


def _prediction_trend(days=14):
    """Daily prediction volume for the last ``days`` days."""
    today = timezone.localdate()
    start = today - timedelta(days=days - 1)
    counts = {
        row['created_at__date']: row['count']
        for row in ProjectPrediction.objects.filter(created_at__date__gte=start)
        .values('created_at__date')
        .annotate(count=Count('id'))
    }
    labels, values = [], []
    for offset in range(days):
        day = start + timedelta(days=offset)
        labels.append(day.strftime('%d %b'))
        values.append(counts.get(day, 0))
    return {'labels': labels, 'values': values}


def risk_analytics_context(request):
    queryset = annotated_projects()
    risks = _risk_counts(queryset)
    progress = _progress_series(queryset)
    metrics = ml.read_metrics()
    total = queryset.count()
    high = risks['high']
    return {
        'total_projects': total,
        'high_risk': high,
        'medium_risk': risks['medium'],
        'low_risk': risks['low'],
        'avg_compensation': round(queryset.aggregate(avg=Avg('compensation_completion_percentage'))['avg'] or 0, 1),
        'delay_rate': round((queryset.filter(latest_probability__gte=0.5).count() / total) * 100, 1) if total else 0,
        'state_risk': _state_risk(queryset),
        'district_risk': _district_risk(queryset),
        'compensation_buckets': _compensation_buckets(queryset),
        'approval_analysis': _approval_analysis(queryset),
        'legal_analysis': _legal_analysis(queryset),
        'progress': progress,
        'feature_importance': metrics.get('feature_importance', []),
        'analytics_data': {
            'risk': [
                {'label': 'High', 'value': risks['high']},
                {'label': 'Medium', 'value': risks['medium']},
                {'label': 'Low', 'value': risks['low']},
            ],
            'stateRisk': _state_risk(queryset),
            'districtRisk': _district_risk(queryset),
            'compensation': _compensation_buckets(queryset),
            'approval': _approval_analysis(queryset),
            'legal': _legal_analysis(queryset),
            'progress': progress,
            'importance': metrics.get('feature_importance', [])[:12],
        },
    }


def model_performance_context():
    summary = ml.model_summary()
    metrics = summary['metrics']
    algorithms = metrics.get('algorithms', {})
    selected = metrics.get('selected', '')
    return {
        'summary': summary,
        'metrics': metrics,
        'dataset': metrics.get('dataset', {}),
        'split': metrics.get('split', {}),
        'algorithms': algorithms,
        'selected': selected,
        'selected_metrics': algorithms.get(selected, {}),
        'importance': metrics.get('feature_importance', []),
        'roc_curves': metrics.get('roc_curves', {}),
        'regressor': metrics.get('regressor', {}),
        'versions': ModelVersion.objects.all()[:10],
        'analytics_data': {
            'roc': metrics.get('roc_curves', {}),
            'importance': metrics.get('feature_importance', [])[:12],
        },
    }
