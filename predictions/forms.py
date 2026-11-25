"""Forms for project management, prediction scenarios and CSV import."""

from django import forms
from django.core.validators import MinValueValidator

from .models import LandAcquisitionProject

TEXT_INPUT = {'class': 'form-input'}
SELECT_INPUT = {'class': 'form-input'}
NUMBER_INPUT = {'class': 'form-input', 'step': 'any'}


class ProjectForm(forms.ModelForm):
    class Meta:
        model = LandAcquisitionProject
        fields = [
            'project_name', 'state', 'district', 'project_type',
            'land_area_acres', 'total_land_parcels', 'acquired_land_parcels',
            'ownership_disputes', 'compensation_status',
            'compensation_completion_percentage', 'approval_status',
            'environmental_clearance_status', 'legal_case_count',
            'rehabilitation_status', 'project_budget', 'allocated_budget',
            'project_duration_months', 'elapsed_months', 'stakeholder_issues',
            'start_date',
        ]
        widgets = {
            'project_name': forms.TextInput(attrs=TEXT_INPUT),
            'state': forms.TextInput(attrs={**TEXT_INPUT, 'list': 'state-options'}),
            'district': forms.TextInput(attrs={**TEXT_INPUT, 'list': 'district-options'}),
            'project_type': forms.TextInput(attrs={**TEXT_INPUT, 'list': 'type-options'}),
            'land_area_acres': forms.NumberInput(attrs=NUMBER_INPUT),
            'total_land_parcels': forms.NumberInput(attrs=NUMBER_INPUT),
            'acquired_land_parcels': forms.NumberInput(attrs=NUMBER_INPUT),
            'ownership_disputes': forms.NumberInput(attrs=NUMBER_INPUT),
            'compensation_status': forms.Select(attrs=SELECT_INPUT),
            'compensation_completion_percentage': forms.NumberInput(attrs={**NUMBER_INPUT, 'min': 0, 'max': 100}),
            'approval_status': forms.Select(attrs=SELECT_INPUT),
            'environmental_clearance_status': forms.Select(attrs=SELECT_INPUT),
            'legal_case_count': forms.NumberInput(attrs=NUMBER_INPUT),
            'rehabilitation_status': forms.Select(attrs=SELECT_INPUT),
            'project_budget': forms.NumberInput(attrs=NUMBER_INPUT),
            'allocated_budget': forms.NumberInput(attrs=NUMBER_INPUT),
            'project_duration_months': forms.NumberInput(attrs=NUMBER_INPUT),
            'elapsed_months': forms.NumberInput(attrs=NUMBER_INPUT),
            'stakeholder_issues': forms.NumberInput(attrs=NUMBER_INPUT),
            'start_date': forms.DateInput(attrs={**TEXT_INPUT, 'type': 'date'}),
        }

    def clean(self):
        cleaned = super().clean()
        total = cleaned.get('total_land_parcels') or 0
        acquired = cleaned.get('acquired_land_parcels') or 0
        compensation = cleaned.get('compensation_completion_percentage')
        duration = cleaned.get('project_duration_months') or 0
        elapsed = cleaned.get('elapsed_months') or 0
        allocated = cleaned.get('allocated_budget') or 0
        budget = cleaned.get('project_budget') or 0

        if acquired > total:
            self.add_error('acquired_land_parcels', 'Acquired parcels cannot exceed total parcels.')
        if compensation is not None and not 0 <= compensation <= 100:
            self.add_error('compensation_completion_percentage', 'Enter a value between 0 and 100.')
        if duration <= 0:
            self.add_error('project_duration_months', 'Duration must be at least one month.')
        if elapsed > duration + 24:
            self.add_error('elapsed_months', 'Elapsed months look inconsistent with the project duration.')
        if budget <= 0:
            self.add_error('project_budget', 'Budget must be greater than zero.')
        if allocated < 0:
            self.add_error('allocated_budget', 'Allocated budget cannot be negative.')
        return cleaned

    def save(self, commit=True):
        project = super().save(commit=False)
        project.refresh_status()
        if commit:
            project.save()
        return project


class PredictionForm(forms.Form):
    project = forms.ModelChoiceField(
        queryset=LandAcquisitionProject.objects.filter(archived=False),
        required=False,
        empty_label='Create a new scenario project',
        widget=forms.Select(attrs=SELECT_INPUT),
        label='Existing project (optional)',
    )
    project_name = forms.CharField(max_length=180, widget=forms.TextInput(attrs=TEXT_INPUT))
    state = forms.CharField(max_length=80, widget=forms.TextInput(attrs=TEXT_INPUT))
    district = forms.CharField(max_length=100, widget=forms.TextInput(attrs=TEXT_INPUT))
    project_type = forms.CharField(max_length=80, widget=forms.TextInput(attrs=TEXT_INPUT))
    land_area_acres = forms.FloatField(min_value=0.01, widget=forms.NumberInput(attrs=NUMBER_INPUT))
    total_land_parcels = forms.IntegerField(min_value=1, widget=forms.NumberInput(attrs=NUMBER_INPUT))
    acquired_land_parcels = forms.IntegerField(min_value=0, widget=forms.NumberInput(attrs=NUMBER_INPUT))
    ownership_disputes = forms.IntegerField(min_value=0, widget=forms.NumberInput(attrs=NUMBER_INPUT))
    compensation_status = forms.ChoiceField(
        choices=LandAcquisitionProject.COMPENSATION_STATUS, widget=forms.Select(attrs=SELECT_INPUT)
    )
    compensation_completion_percentage = forms.FloatField(
        min_value=0, max_value=100, widget=forms.NumberInput(attrs={**NUMBER_INPUT, 'min': 0, 'max': 100})
    )
    approval_status = forms.ChoiceField(
        choices=LandAcquisitionProject.APPROVAL_STATUS, widget=forms.Select(attrs=SELECT_INPUT)
    )
    environmental_clearance_status = forms.ChoiceField(
        choices=LandAcquisitionProject.CLEARANCE_STATUS, widget=forms.Select(attrs=SELECT_INPUT)
    )
    legal_case_count = forms.IntegerField(min_value=0, widget=forms.NumberInput(attrs=NUMBER_INPUT))
    rehabilitation_status = forms.ChoiceField(
        choices=LandAcquisitionProject.REHABILITATION_STATUS, widget=forms.Select(attrs=SELECT_INPUT)
    )
    project_budget = forms.FloatField(min_value=0.01, widget=forms.NumberInput(attrs=NUMBER_INPUT))
    allocated_budget = forms.FloatField(min_value=0, widget=forms.NumberInput(attrs=NUMBER_INPUT))
    project_duration_months = forms.IntegerField(min_value=1, widget=forms.NumberInput(attrs=NUMBER_INPUT))
    elapsed_months = forms.IntegerField(min_value=0, widget=forms.NumberInput(attrs=NUMBER_INPUT))
    stakeholder_issues = forms.IntegerField(min_value=0, widget=forms.NumberInput(attrs=NUMBER_INPUT))
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={**TEXT_INPUT, 'type': 'date'}),
        help_text='Leave blank to estimate from elapsed months.',
    )

    PROJECT_FIELDS = [
        'project_name', 'state', 'district', 'project_type',
        'land_area_acres', 'total_land_parcels', 'acquired_land_parcels',
        'ownership_disputes', 'compensation_status',
        'compensation_completion_percentage', 'approval_status',
        'environmental_clearance_status', 'legal_case_count',
        'rehabilitation_status', 'project_budget', 'allocated_budget',
        'project_duration_months', 'elapsed_months', 'stakeholder_issues',
        'start_date',
    ]

    def clean(self):
        cleaned = super().clean()
        total = cleaned.get('total_land_parcels') or 0
        acquired = cleaned.get('acquired_land_parcels') or 0
        duration = cleaned.get('project_duration_months') or 0
        elapsed = cleaned.get('elapsed_months') or 0
        if acquired > total:
            self.add_error('acquired_land_parcels', 'Acquired parcels cannot exceed total parcels.')
        if elapsed > duration + 24:
            self.add_error('elapsed_months', 'Elapsed months look inconsistent with the project duration.')
        return cleaned

    def apply_to_project(self, project):
        from datetime import date, timedelta

        for field in self.PROJECT_FIELDS:
            value = self.cleaned_data.get(field)
            if field == 'start_date' and not value:
                elapsed = self.cleaned_data.get('elapsed_months') or 0
                value = date.today() - timedelta(days=int(elapsed * 30.44))
            setattr(project, field, value)
        project.refresh_status()
        return project


class ImportForm(forms.Form):
    file = forms.FileField(
        label='CSV file',
        widget=forms.FileInput(attrs={'class': 'form-input', 'accept': '.csv'}),
        help_text='Upload a CSV with project_name, state, district, project_type and total_land_parcels at minimum.',
    )
    predict = forms.BooleanField(
        required=False,
        initial=False,
        label='Run predictions for imported projects',
        help_text='Uses the active model and may take a few moments for large files.',
    )


class MonitoringFilterForm(forms.Form):
    q = forms.CharField(required=False, widget=forms.TextInput(attrs={**TEXT_INPUT, 'placeholder': 'Search project, district or ID'}))
    state = forms.ChoiceField(required=False, widget=forms.Select(attrs=SELECT_INPUT))
    status = forms.ChoiceField(required=False, choices=[('', 'All statuses')] + LandAcquisitionProject.STATUS_CHOICES, widget=forms.Select(attrs=SELECT_INPUT))
    risk = forms.ChoiceField(required=False, choices=[('', 'All risk levels'), ('High', 'High'), ('Medium', 'Medium'), ('Low', 'Low')], widget=forms.Select(attrs=SELECT_INPUT))
    sort = forms.ChoiceField(
        required=False,
        choices=[
            ('', 'Default order'),
            ('risk', 'Highest delay probability'),
            ('progress', 'Lowest acquisition progress'),
            ('compensation', 'Lowest compensation'),
            ('delay', 'Longest predicted delay'),
            ('name', 'Project name'),
        ],
        widget=forms.Select(attrs=SELECT_INPUT),
    )

    def __init__(self, *args, **kwargs):
        states = kwargs.pop('states', [])
        super().__init__(*args, **kwargs)
        self.fields['state'].choices = [('', 'All states')] + [(state, state) for state in states]
