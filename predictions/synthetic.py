"""Synthetic land-acquisition dataset generation.

The data in this module is entirely artificial.  It does not describe real
projects, landowners, districts or payments.  It is designed for academic
demonstration of a delay-prediction workflow, with labels that respond to
project friction factors (disputes, compensation, approvals, legal cases,
clearance and rehabilitation) plus random noise.

Usage:
    python manage.py generate_synthetic_data
    python manage.py generate_synthetic_data --rows 2500 --seed 42 --seed-db
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from django.conf import settings

DATASET_RELATIVE_PATH = Path('data') / 'land_acquisition_projects.csv'

STATES = {
    'Maharashtra': ['Pune', 'Nashik', 'Nagpur', 'Thane'],
    'Uttar Pradesh': ['Lucknow', 'Varanasi', 'Kanpur', 'Agra'],
    'Karnataka': ['Bengaluru Urban', 'Mysuru', 'Belagavi', 'Dharwad'],
    'Tamil Nadu': ['Chennai', 'Coimbatore', 'Madurai', 'Salem'],
    'Gujarat': ['Ahmedabad', 'Surat', 'Vadodara', 'Rajkot'],
    'Rajasthan': ['Jaipur', 'Jodhpur', 'Udaipur', 'Kota'],
    'Madhya Pradesh': ['Bhopal', 'Indore', 'Gwalior', 'Jabalpur'],
    'West Bengal': ['Kolkata', 'Howrah', 'Siliguri', 'Durgapur'],
    'Telangana': ['Hyderabad', 'Warangal', 'Nizamabad', 'Karimnagar'],
    'Kerala': ['Kochi', 'Thiruvananthapuram', 'Kozhikode', 'Thrissur'],
    'Bihar': ['Patna', 'Gaya', 'Bhagalpur', 'Muzaffarpur'],
    'Punjab': ['Ludhiana', 'Amritsar', 'Jalandhar', 'Patiala'],
    'Haryana': ['Gurugram', 'Faridabad', 'Panipat', 'Karnal'],
    'Odisha': ['Bhubaneswar', 'Cuttack', 'Rourkela', 'Sambalpur'],
    'Andhra Pradesh': ['Visakhapatnam', 'Vijayawada', 'Guntur', 'Tirupati'],
}

PROJECT_TYPES = [
    ('Highway Expansion', 0.55),
    ('Railway Corridor', 0.50),
    ('Industrial Park', 0.35),
    ('Solar Park', 0.25),
    ('Urban Township', 0.40),
    ('Canal Irrigation', 0.45),
    ('Airport Expansion', 0.55),
    ('Port Development', 0.60),
    ('Mining Zone', 0.70),
    ('Transmission Line', 0.20),
]

PHASES = ('Phase I', 'Phase II', 'Phase III', 'Phase IV')

DATASET_COLUMNS = [
    'project_id', 'project_name', 'state', 'district', 'project_type',
    'land_area_acres', 'total_land_parcels', 'acquired_land_parcels',
    'ownership_disputes', 'compensation_status',
    'compensation_completion_percentage', 'approval_status',
    'environmental_clearance_status', 'legal_case_count',
    'rehabilitation_status', 'project_budget', 'allocated_budget',
    'project_duration_months', 'elapsed_months', 'stakeholder_issues',
    'delay_status', 'delay_days', 'start_date', 'is_synthetic',
]


def dataset_path() -> Path:
    return Path(settings.BASE_DIR) / DATASET_RELATIVE_PATH


def _sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-value))


def _compensation_status(percentage: float) -> str:
    if percentage >= 99.5:
        return 'completed'
    if percentage > 0:
        return 'in_progress'
    return 'pending'


def _rehab_status(rng, compensation: float) -> str:
    if compensation >= 90 and rng.random() < 0.65:
        return 'completed'
    if compensation >= 40 or rng.random() < 0.45:
        return 'in_progress'
    return 'not_started'


def generate_dataset(rows: int = 2400, seed: int = 42, reference_date: date | None = None):
    """Return a deterministic synthetic DataFrame and write assumptions metadata."""
    rng = np.random.default_rng(seed)
    reference_date = reference_date or date.today()
    states = list(STATES)
    state_weights = np.array([1.5, 1.4, 1.1, 1.1, 1.0, 0.9, 0.9, 0.8, 0.8, 0.7, 0.7, 0.7, 0.7, 0.6, 0.6])
    state_weights = state_weights / state_weights.sum()
    type_names = [name for name, _ in PROJECT_TYPES]
    type_risk = {name: risk for name, risk in PROJECT_TYPES}
    type_weights = np.array([1.2, 1.0, 1.2, 0.9, 1.0, 0.8, 0.7, 0.6, 0.6, 0.8])
    type_weights = type_weights / type_weights.sum()

    records = []
    for index in range(1, rows + 1):
        state = str(rng.choice(states, p=state_weights))
        district = str(rng.choice(STATES[state]))
        project_type = str(rng.choice(type_names, p=type_weights))

        total_parcels = int(rng.integers(40, 1801))
        area = round(total_parcels * float(rng.uniform(0.18, 1.35)), 1)
        duration = int(rng.integers(12, 61))
        elapsed = int(rng.integers(1, duration + 7))

        # Friction factors.
        disputes = int(min(total_parcels * 0.12, rng.gamma(1.6, 2.4)))
        if rng.random() < 0.12:
            disputes = 0
        legal_cases = int(min(15, rng.poisson(0.55 + disputes * 0.22)))
        stakeholder = int(min(12, rng.poisson(0.9 + legal_cases * 0.35)))

        planned_ratio = min(1.0, elapsed / max(1, duration))
        compensation = float(rng.normal(planned_ratio * 100 + 8, 22))
        compensation = float(np.clip(round(compensation / 5) * 5, 0, 100))
        if planned_ratio < 0.15 and rng.random() < 0.45:
            compensation = 0.0

        approval_roll = rng.random()
        if approval_roll < 0.42 + planned_ratio * 0.32:
            approval = 'approved'
        elif approval_roll < 0.80:
            approval = 'in_progress'
        elif approval_roll < 0.96:
            approval = 'pending'
        else:
            approval = 'rejected'

        clearance_roll = rng.random()
        if clearance_roll < 0.58:
            clearance = 'cleared'
        elif clearance_roll < 0.72:
            clearance = 'in_progress'
        elif clearance_roll < 0.94:
            clearance = 'pending'
        elif clearance_roll < 0.98:
            clearance = 'rejected'
        else:
            clearance = 'not_required'

        rehab = _rehab_status(rng, compensation)

        # Acquisition progress reacts to friction and available time.
        friction = (
            min(1.0, disputes / 12.0) * 0.22
            + (1 - compensation / 100.0) * 0.20
            + (0.18 if approval in {'pending', 'in_progress'} else 0.38 if approval == 'rejected' else 0)
            + min(1.0, legal_cases / 8.0) * 0.12
        )
        actual_ratio = planned_ratio + float(rng.normal(-0.04, 0.16)) - friction
        actual_ratio = float(np.clip(actual_ratio, 0, 1))
        acquired = int(round(total_parcels * actual_ratio))
        if actual_ratio >= 0.985 and compensation >= 95 and approval == 'approved':
            acquired = total_parcels
        acquired = min(acquired, total_parcels)

        # Budget assumptions, in INR crore.
        per_acre = {
            'Highway Expansion': 0.55, 'Railway Corridor': 0.75, 'Industrial Park': 1.15,
            'Solar Park': 0.28, 'Urban Township': 1.60, 'Canal Irrigation': 0.35,
            'Airport Expansion': 1.25, 'Port Development': 1.45, 'Mining Zone': 0.65,
            'Transmission Line': 0.18,
        }[project_type]
        project_budget = round(area * per_acre * float(rng.uniform(0.85, 1.25)), 2)
        allocated_budget = round(project_budget * float(rng.uniform(0.70, 1.12)), 2)

        # Latent delay propensity.  The label is a probabilistic function of
        # the observed friction factors, not a random assignment.
        severity = (
            (1 - compensation / 100.0) * 1.55
            + min(1.0, disputes / 10.0) * 1.65
            + {'approved': 0.0, 'in_progress': 0.65, 'pending': 1.25, 'rejected': 2.10}[approval]
            + {'cleared': 0.0, 'not_required': 0.0, 'in_progress': 0.45, 'pending': 0.95, 'rejected': 1.80}[clearance]
            + min(1.0, legal_cases / 6.0) * 1.35
            + {'completed': 0.0, 'in_progress': 0.35, 'not_started': 0.75}[rehab]
            + min(1.0, stakeholder / 8.0) * 0.70
            + max(0.0, planned_ratio - actual_ratio) * 2.4
            + (0.45 if allocated_budget + 0.01 < project_budget else 0.0)
            + type_risk[project_type] * 0.55
            - 3.05
            + float(rng.normal(0, 0.24))
        )
        probability = _sigmoid(severity)
        delayed = bool(rng.random() < probability)

        if delayed:
            severity_signal = min(1.6, max(0.0, severity + 1.2))
            delay_days = int(30 + severity_signal * 290 + rng.normal(0, 22))
            delay_days = max(30, min(720, delay_days))
        else:
            delay_days = int(rng.integers(0, 12))

        start = reference_date - timedelta(days=int(elapsed * 30.44))
        project_name = f'{project_type} — {district} {PHASES[index % len(PHASES)]}'

        records.append({
            'project_id': f'LA-{index:05d}',
            'project_name': project_name,
            'state': state,
            'district': district,
            'project_type': project_type,
            'land_area_acres': area,
            'total_land_parcels': total_parcels,
            'acquired_land_parcels': acquired,
            'ownership_disputes': disputes,
            'compensation_status': _compensation_status(compensation),
            'compensation_completion_percentage': compensation,
            'approval_status': approval,
            'environmental_clearance_status': clearance,
            'legal_case_count': legal_cases,
            'rehabilitation_status': rehab,
            'project_budget': project_budget,
            'allocated_budget': allocated_budget,
            'project_duration_months': duration,
            'elapsed_months': elapsed,
            'stakeholder_issues': stakeholder,
            'delay_status': int(delayed),
            'delay_days': delay_days,
            'start_date': start.isoformat(),
            'is_synthetic': 1,
        })

    return pd.DataFrame(records, columns=DATASET_COLUMNS)


def write_dataset(rows: int = 2400, seed: int = 42) -> Path:
    path = dataset_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = generate_dataset(rows=rows, seed=seed)
    frame.to_csv(path, index=False)

    assumptions = f"""# Synthetic Dataset — Read Me

This directory contains **synthetic** land-acquisition project data generated by
`predictions/synthetic.py` (seed {seed}, {rows} rows). It is intended for academic
demonstration of the delay-prediction workflow only.

## What the data represents
Each row is a snapshot of a hypothetical land-acquisition project. Fields include
location, project type, land area, parcels acquired, ownership disputes,
compensation completion, approval and environmental-clearance status, legal
cases, rehabilitation status, budget, duration, elapsed time and stakeholder
issues.

## Label generation
`delay_status` (1 = delayed, 0 = not delayed) is sampled from a logistic
probability built from the friction factors above plus random noise. The signal
is meaningful but deliberately imperfect. `delay_days` is generated only for
delayed projects and is **not** used as an input feature.

## Leakage controls
- `delay_status` and `delay_days` are excluded from model inputs.
- `project_id`, `project_name`, `start_date` and `is_synthetic` are identifiers,
  not predictors.
- Acquisition progress and budget utilisation are derived from current-state
  fields only; no future outcome is included.

## Privacy
No real landowner names, identities, parcel numbers or payment records are used.
All locations are district names used as generic synthetic categories.

## Provenance
Generated on {date.today().isoformat()} using a deterministic random seed. The CSV is
committed so that the training pipeline is reproducible.
"""
    (path.parent / 'README.md').write_text(assumptions, encoding='utf-8')
    return path
