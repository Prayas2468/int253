"""Database models for the land-acquisition delay prediction platform.

The models store project snapshots, machine-learning predictions, the factors
behind each prediction, trained model versions, mitigation plans and an audit
log.  Synthetic records are flagged explicitly so demo/academic data can never
be mistaken for real land-acquisition records.
"""

from datetime import date, timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


def add_months(value, months):
    """Return ``value`` shifted by a whole number of calendar months."""
    if not value:
        return None
    month = value.month - 1 + int(months)
    year = value.year + month // 12
    month = month % 12 + 1
    day = min(value.day, 28)
    return date(year, month, day)


class LandAcquisitionProject(models.Model):
    STATUS_ON_TRACK = 'on_track'
    STATUS_AT_RISK = 'at_risk'
    STATUS_DELAYED = 'delayed'
    STATUS_COMPLETED = 'completed'
    STATUS_CHOICES = [
        (STATUS_ON_TRACK, 'On Track'),
        (STATUS_AT_RISK, 'At Risk'),
        (STATUS_DELAYED, 'Delayed'),
        (STATUS_COMPLETED, 'Completed'),
    ]

    COMPENSATION_STATUS = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
    ]
    APPROVAL_STATUS = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    CLEARANCE_STATUS = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('cleared', 'Cleared'),
        ('rejected', 'Rejected'),
        ('not_required', 'Not Required'),
    ]
    REHABILITATION_STATUS = [
        ('not_started', 'Not Started'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
    ]

    project_id = models.CharField(max_length=32, unique=True)
    project_name = models.CharField(max_length=180)
    state = models.CharField(max_length=80, db_index=True)
    district = models.CharField(max_length=100, db_index=True)
    project_type = models.CharField(max_length=80)

    land_area_acres = models.FloatField(default=0)
    total_land_parcels = models.PositiveIntegerField(default=0)
    acquired_land_parcels = models.PositiveIntegerField(default=0)
    ownership_disputes = models.PositiveIntegerField(default=0)

    compensation_status = models.CharField(
        max_length=20, choices=COMPENSATION_STATUS, default='pending'
    )
    compensation_completion_percentage = models.FloatField(default=0)
    approval_status = models.CharField(
        max_length=20, choices=APPROVAL_STATUS, default='pending'
    )
    environmental_clearance_status = models.CharField(
        max_length=20, choices=CLEARANCE_STATUS, default='pending'
    )
    legal_case_count = models.PositiveIntegerField(default=0)
    rehabilitation_status = models.CharField(
        max_length=20, choices=REHABILITATION_STATUS, default='not_started'
    )

    project_budget = models.FloatField(default=0, help_text='Budget in INR crore')
    allocated_budget = models.FloatField(default=0, help_text='Allocated budget in INR crore')
    project_duration_months = models.PositiveIntegerField(default=12)
    elapsed_months = models.PositiveIntegerField(default=0)
    stakeholder_issues = models.PositiveIntegerField(default=0)

    start_date = models.DateField(default=date.today)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ON_TRACK)

    is_synthetic = models.BooleanField(default=True)
    archived = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='land_projects',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-updated_at', 'project_id')
        indexes = [
            models.Index(fields=['status', 'archived']),
            models.Index(fields=['state', 'district']),
        ]

    def __str__(self):
        return f'{self.project_id} — {self.project_name}'

    def save(self, *args, **kwargs):
        if not self.project_id:
            self.project_id = self._next_project_id()
        super().save(*args, **kwargs)

    @classmethod
    def _next_project_id(cls):
        prefix = f'LA-{timezone.now().year}-'
        latest = (
            cls.objects.filter(project_id__startswith=prefix)
            .order_by('-project_id')
            .values_list('project_id', flat=True)
            .first()
        )
        sequence = 1
        if latest:
            try:
                sequence = int(latest.rsplit('-', 1)[1]) + 1
            except (IndexError, ValueError):
                sequence = 1
        return f'{prefix}{sequence:04d}'

    @property
    def acquisition_progress(self):
        if not self.total_land_parcels:
            return 0.0
        return round(min(100.0, (self.acquired_land_parcels / self.total_land_parcels) * 100), 1)

    @property
    def planned_progress(self):
        if not self.project_duration_months:
            return 0.0
        return round(min(100.0, (self.elapsed_months / self.project_duration_months) * 100), 1)

    @property
    def schedule_variance(self):
        return round(self.acquisition_progress - self.planned_progress, 1)

    @property
    def budget_utilisation(self):
        if not self.allocated_budget:
            return 0.0
        return round(min(100.0, (self.project_budget / self.allocated_budget) * 100), 1)

    @property
    def planned_end_date(self):
        return add_months(self.start_date, self.project_duration_months)

    @property
    def days_elapsed(self):
        return max(0, (date.today() - self.start_date).days)

    @property
    def latest_prediction(self):
        return self.predictions.select_related('model_version').order_by('-created_at').first()

    @property
    def risk_level(self):
        prediction = self.latest_prediction
        return prediction.risk_level if prediction else self.compute_risk_level()

    def compute_risk_level(self):
        scores = self.risk_scores
        highest = max(scores.values()) if scores else 0
        if highest >= 70:
            return 'High'
        if highest >= 40:
            return 'Medium'
        return 'Low'

    # ------------------------------------------------------------------
    # Rule-based risk scoring.  These scores explain current project state;
    # the machine-learning model produces the delay probability separately.
    # ------------------------------------------------------------------
    @property
    def risk_scores(self):
        acquisition_gap = max(0.0, 100 - self.acquisition_progress)
        dispute_pressure = min(100.0, (self.ownership_disputes / max(1, self.total_land_parcels)) * 900)
        ownership = round(min(100.0, 0.45 * acquisition_gap + 0.55 * dispute_pressure), 1)

        compensation = round(max(0.0, 100 - self.compensation_completion_percentage), 1)
        if self.compensation_status == 'completed':
            compensation = 0.0

        legal = round(min(100.0, self.legal_case_count * 14.0), 1)

        approval_map = {'approved': 0, 'in_progress': 45, 'pending': 75, 'rejected': 100}
        approval = approval_map.get(self.approval_status, 60)

        clearance_map = {
            'cleared': 0, 'not_required': 0, 'in_progress': 45,
            'pending': 75, 'rejected': 100,
        }
        environmental = clearance_map.get(self.environmental_clearance_status, 60)

        rehab_map = {'completed': 0, 'in_progress': 45, 'not_started': 80}
        rehabilitation = rehab_map.get(self.rehabilitation_status, 60)

        return {
            'Land Ownership': ownership,
            'Compensation': compensation,
            'Legal': legal,
            'Approval': approval,
            'Environmental': environmental,
            'Rehabilitation': rehabilitation,
        }

    @property
    def risk_profile(self):
        labels = {
            'Land Ownership': ('Land Ownership Risk', 'ownership_disputes'),
            'Compensation': ('Compensation Risk', 'compensation_completion_percentage'),
            'Legal': ('Legal Risk', 'legal_case_count'),
            'Approval': ('Approval Risk', 'approval_status'),
            'Environmental': ('Environmental Risk', 'environmental_clearance_status'),
            'Rehabilitation': ('Rehabilitation Risk', 'rehabilitation_status'),
        }
        rows = []
        for key, score in self.risk_scores.items():
            label, _field = labels[key]
            level = 'High' if score >= 70 else 'Medium' if score >= 40 else 'Low'
            rows.append({'key': key, 'label': label, 'score': score, 'level': level})
        return rows

    @property
    def current_phase(self):
        if self.acquisition_progress >= 99.5 and self.compensation_completion_percentage >= 99.5:
            return 'Acquisition Completion'
        if self.acquired_land_parcels <= 0:
            if self.elapsed_months <= 1:
                return 'Initial Assessment'
            return 'Land Identification'
        if self.ownership_disputes > 0 and self.acquisition_progress < 50:
            return 'Ownership Verification'
        if self.compensation_completion_percentage < 99.5:
            return 'Compensation'
        if (
            self.legal_case_count > 0
            or self.approval_status != 'approved'
            or self.environmental_clearance_status not in {'cleared', 'not_required'}
        ):
            return 'Legal Clearance'
        return 'Initial Assessment'

    def refresh_status(self):
        """Derive a monitoring status from schedule variance (not the ML label)."""
        if self.acquisition_progress >= 99.5 and self.compensation_completion_percentage >= 99.5:
            self.status = self.STATUS_COMPLETED
        elif self.schedule_variance <= -15:
            self.status = self.STATUS_DELAYED
        elif self.schedule_variance <= -5:
            self.status = self.STATUS_AT_RISK
        else:
            self.status = self.STATUS_ON_TRACK
        return self.status


class ModelVersion(models.Model):
    name = models.CharField(max_length=120)
    algorithm = models.CharField(max_length=40)
    version = models.CharField(max_length=40)
    metrics = models.JSONField(default=dict, blank=True)
    artifact_path = models.CharField(max_length=300, blank=True)
    training_rows = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    trained_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ('-trained_at',)

    def __str__(self):
        return f'{self.name} ({self.version})'

    @property
    def accuracy(self):
        return (self.metrics or {}).get('accuracy')

    @property
    def f1(self):
        return (self.metrics or {}).get('f1')

    @property
    def roc_auc(self):
        return (self.metrics or {}).get('roc_auc')


class ProjectPrediction(models.Model):
    RISK_CHOICES = [('Low', 'Low'), ('Medium', 'Medium'), ('High', 'High')]

    project = models.ForeignKey(
        LandAcquisitionProject, on_delete=models.CASCADE, related_name='predictions'
    )
    delay_probability = models.FloatField(help_text='Probability of delay, 0–1')
    risk_level = models.CharField(max_length=10, choices=RISK_CHOICES)
    predicted_delay_days = models.FloatField(null=True, blank=True)
    estimated_completion_date = models.DateField(null=True, blank=True)
    model_version = models.ForeignKey(
        ModelVersion, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='predictions',
    )
    predicted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='land_predictions',
    )
    inputs_snapshot = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)
        indexes = [models.Index(fields=['risk_level', 'created_at'])]

    def __str__(self):
        return f'{self.project.project_id} — {self.delay_probability:.0%} delay risk'

    @property
    def probability_percent(self):
        return round(self.delay_probability * 100, 1)

    @property
    def predicted_outcome(self):
        return 'Delay' if self.delay_probability >= 0.5 else 'No Delay'


class PredictionFactor(models.Model):
    DIRECTION_CHOICES = [('increases', 'Increases delay risk'), ('decreases', 'Reduces delay risk')]

    prediction = models.ForeignKey(
        ProjectPrediction, on_delete=models.CASCADE, related_name='factors'
    )
    factor_name = models.CharField(max_length=120)
    impact = models.FloatField(default=0, help_text='Signed model contribution')
    direction = models.CharField(max_length=12, choices=DIRECTION_CHOICES, default='increases')
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ('-impact',)

    def __str__(self):
        return self.factor_name


class MitigationPlan(models.Model):
    STATUS_CHOICES = [
        ('suggested', 'Suggested'),
        ('planned', 'Planned'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
    ]
    PRIORITY_CHOICES = [('Low', 'Low'), ('Medium', 'Medium'), ('High', 'High')]

    project = models.ForeignKey(
        LandAcquisitionProject, on_delete=models.CASCADE, related_name='mitigation_plans'
    )
    prediction = models.ForeignKey(
        ProjectPrediction, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='mitigation_plans',
    )
    risk_area = models.CharField(max_length=80)
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='Medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='suggested')
    generated_by_system = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='mitigation_plans',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return self.title


class ActivityLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='activities',
    )
    action = models.CharField(max_length=80)
    entity_type = models.CharField(max_length=60, blank=True)
    entity_id = models.CharField(max_length=40, blank=True)
    detail = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.action} — {self.detail}'
