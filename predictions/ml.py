"""Machine-learning pipeline for land-acquisition delay prediction.

The module trains and compares Random Forest, Decision Tree and Logistic
Regression classifiers, selects the best model by ROC-AUC, and trains a
Random Forest regressor for delay duration on delayed projects.

All preprocessing is wrapped in scikit-learn pipelines so that the exact same
transformations are used during training and inference.  Metrics are written to
``ml_artifacts/metrics.json`` and are also exposed through the Model Performance
page; nothing is hardcoded.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from django.conf import settings
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier

from .synthetic import dataset_path

ARTIFACT_DIR = Path(settings.BASE_DIR) / 'ml_artifacts'
CLASSIFIER_PATH = ARTIFACT_DIR / 'delay_classifier.joblib'
REGRESSOR_PATH = ARTIFACT_DIR / 'delay_days_regressor.joblib'
METRICS_PATH = ARTIFACT_DIR / 'metrics.json'

TARGET = 'delay_status'

CATEGORICAL_FEATURES = [
    'state',
    'project_type',
    'compensation_status',
    'approval_status',
    'environmental_clearance_status',
    'rehabilitation_status',
]

NUMERIC_FEATURES = [
    'land_area_acres',
    'total_land_parcels',
    'acquired_land_parcels',
    'ownership_disputes',
    'compensation_completion_percentage',
    'legal_case_count',
    'project_budget',
    'allocated_budget',
    'project_duration_months',
    'elapsed_months',
    'stakeholder_issues',
    'acquisition_progress',
    'budget_utilisation',
]

FEATURE_COLUMNS = NUMERIC_FEATURES + CATEGORICAL_FEATURES
EXCLUDED_COLUMNS = [
    'project_id', 'project_name', 'start_date', 'is_synthetic',
    'delay_status', 'delay_days',
]

RISK_LOW_THRESHOLD = 0.35
RISK_HIGH_THRESHOLD = 0.65

FACTOR_RULES = {
    'ownership_disputes': (
        'Ownership disputes',
        lambda p: min(1.0, p.ownership_disputes / 10.0),
        'Ownership disputes can stall parcel handover and require verification.',
    ),
    'compensation_completion_percentage': (
        'Pending compensation',
        lambda p: max(0.0, (100.0 - p.compensation_completion_percentage) / 100.0),
        'Incomplete compensation keeps landowners from releasing possession.',
    ),
    'legal_case_count': (
        'Legal cases',
        lambda p: min(1.0, p.legal_case_count / 6.0),
        'Pending litigation adds uncertainty to acquisition timelines.',
    ),
    'approval_status': (
        'Approval bottleneck',
        lambda p: {'approved': 0.0, 'in_progress': 0.45, 'pending': 0.8, 'rejected': 1.0}.get(p.approval_status, 0.6),
        'Pending or rejected approvals block the next acquisition stage.',
    ),
    'environmental_clearance_status': (
        'Environmental clearance',
        lambda p: {'cleared': 0.0, 'not_required': 0.0, 'in_progress': 0.45, 'pending': 0.8, 'rejected': 1.0}.get(p.environmental_clearance_status, 0.6),
        'Unresolved environmental clearance is a common schedule constraint.',
    ),
    'rehabilitation_status': (
        'Rehabilitation pending',
        lambda p: {'completed': 0.0, 'in_progress': 0.45, 'not_started': 0.85}.get(p.rehabilitation_status, 0.6),
        'Rehabilitation commitments must be settled before land is vacated.',
    ),
    'stakeholder_issues': (
        'Stakeholder issues',
        lambda p: min(1.0, p.stakeholder_issues / 8.0),
        'Unresolved stakeholder concerns can trigger objections and rework.',
    ),
    'acquisition_progress': (
        'Acquisition progress lag',
        lambda p: max(0.0, min(1.0, (p.planned_progress - p.acquisition_progress) / 50.0)),
        'Actual acquisition is behind the planned progress for elapsed time.',
    ),
    'allocated_budget': (
        'Budget allocation gap',
        lambda p: max(0.0, min(1.0, (1 - (p.allocated_budget / p.project_budget)))) if p.project_budget else 0.0,
        'Allocated funds are below the estimated project budget.',
    ),
}


def load_dataset() -> pd.DataFrame:
    path = dataset_path()
    if not path.exists():
        raise FileNotFoundError(
            f'Synthetic dataset not found at {path}. Run: python manage.py generate_synthetic_data'
        )
    frame = pd.read_csv(path)
    return prepare_frame(frame)


def prepare_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Add derived features and coerce types consistently."""
    frame = frame.copy()
    frame['total_land_parcels'] = pd.to_numeric(frame['total_land_parcels'], errors='coerce').fillna(0)
    frame['acquired_land_parcels'] = pd.to_numeric(frame['acquired_land_parcels'], errors='coerce').fillna(0)
    frame['acquisition_progress'] = np.where(
        frame['total_land_parcels'] > 0,
        (frame['acquired_land_parcels'] / frame['total_land_parcels']) * 100,
        0,
    )
    frame['budget_utilisation'] = np.where(
        frame['allocated_budget'] > 0,
        (frame['project_budget'] / frame['allocated_budget']) * 100,
        0,
    )
    for column in NUMERIC_FEATURES:
        frame[column] = pd.to_numeric(frame[column], errors='coerce')
    for column in CATEGORICAL_FEATURES:
        frame[column] = frame[column].astype(str).fillna('Unknown')
    return frame


def build_preprocessor() -> ColumnTransformer:
    return ColumnTransformer(
        transformers=[
            ('num', Pipeline([
                ('imputer', SimpleImputer(strategy='median')),
                ('scaler', StandardScaler()),
            ]), NUMERIC_FEATURES),
            ('cat', Pipeline([
                ('imputer', SimpleImputer(strategy='most_frequent')),
                ('onehot', OneHotEncoder(handle_unknown='ignore', sparse_output=False)),
            ]), CATEGORICAL_FEATURES),
        ],
        remainder='drop',
    )


def _classifier_candidates() -> dict:
    return {
        'Random Forest': RandomForestClassifier(
            n_estimators=320, max_depth=12, min_samples_leaf=3,
            class_weight='balanced', random_state=42, n_jobs=-1,
        ),
        'Decision Tree': DecisionTreeClassifier(
            max_depth=9, min_samples_leaf=5, class_weight='balanced', random_state=42,
        ),
        'Logistic Regression': LogisticRegression(
            max_iter=3000, class_weight='balanced', random_state=42,
        ),
    }


def _metrics(y_true, prediction, probability) -> dict:
    matrix = confusion_matrix(y_true, prediction, labels=[0, 1]).tolist()
    return {
        'accuracy': round(float(accuracy_score(y_true, prediction)), 4),
        'precision': round(float(precision_score(y_true, prediction, zero_division=0)), 4),
        'recall': round(float(recall_score(y_true, prediction, zero_division=0)), 4),
        'f1': round(float(f1_score(y_true, prediction, zero_division=0)), 4),
        'roc_auc': round(float(roc_auc_score(y_true, probability)), 4),
        'confusion_matrix': matrix,
    }


def _aggregate_importance(pipeline, preprocessor) -> list:
    model = pipeline.named_steps['model']
    if hasattr(model, 'feature_importances_'):
        raw = np.asarray(model.feature_importances_, dtype=float)
    elif hasattr(model, 'coef_'):
        raw = np.abs(np.asarray(model.coef_, dtype=float)).ravel()
    else:
        return []

    try:
        names = list(preprocessor.get_feature_names_out())
    except Exception:
        return []

    totals = {}
    for name, value in zip(names, raw):
        source = None
        remainder = name.split('__', 1)[-1]
        for feature in NUMERIC_FEATURES:
            if remainder == feature:
                source = feature
                break
        if source is None:
            for feature in CATEGORICAL_FEATURES:
                if remainder.startswith(feature + '_'):
                    source = feature
                    break
        if source is None:
            continue
        totals[source] = totals.get(source, 0.0) + float(value)

    total = sum(totals.values()) or 1.0
    return [
        {'feature': feature, 'importance': round(value / total, 4)}
        for feature, value in sorted(totals.items(), key=lambda item: item[1], reverse=True)
    ]


def train_models(test_size: float = 0.2, seed: int = 42) -> dict:
    """Train, compare, persist and describe the models. Returns metrics."""
    frame = load_dataset()
    if TARGET not in frame:
        raise ValueError('Dataset is missing the delay_status target column.')

    X = frame[FEATURE_COLUMNS]
    y = frame[TARGET].astype(int)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=seed, stratify=y,
    )

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    results = {}
    fitted = {}
    roc_points = {}

    for name, estimator in _classifier_candidates().items():
        preprocessor = build_preprocessor()
        pipeline = Pipeline([('preprocessor', preprocessor), ('model', estimator)])
        pipeline.fit(X_train, y_train)
        prediction = pipeline.predict(X_test)
        probability = pipeline.predict_proba(X_test)[:, 1]
        metrics = _metrics(y_test, prediction, probability)
        results[name] = metrics
        fitted[name] = (pipeline, preprocessor)
        fpr, tpr, _thresholds = roc_curve(y_test, probability)
        step = max(1, len(fpr) // 40)
        roc_points[name] = {
            'fpr': [round(float(value), 4) for value in fpr[::step]],
            'tpr': [round(float(value), 4) for value in tpr[::step]],
        }

    best_name = max(results, key=lambda key: (results[key]['roc_auc'], results[key]['f1']))
    best_pipeline, best_preprocessor = fitted[best_name]
    joblib.dump(best_pipeline, CLASSIFIER_PATH)

    importance = _aggregate_importance(best_pipeline, best_preprocessor)

    # Delay-duration regressor, trained only on historically delayed projects.
    delayed_mask = frame[TARGET].astype(int) == 1
    regressor_metrics = {}
    if delayed_mask.sum() >= 60 and 'delay_days' in frame:
        X_delay = frame.loc[delayed_mask, FEATURE_COLUMNS]
        y_delay = pd.to_numeric(frame.loc[delayed_mask, 'delay_days'], errors='coerce').fillna(0)
        Xd_train, Xd_test, yd_train, yd_test = train_test_split(
            X_delay, y_delay, test_size=test_size, random_state=seed,
        )
        regressor = Pipeline([
            ('preprocessor', build_preprocessor()),
            ('model', RandomForestRegressor(
                n_estimators=260, max_depth=12, min_samples_leaf=3,
                random_state=42, n_jobs=-1,
            )),
        ])
        regressor.fit(Xd_train, yd_train)
        predicted_days = regressor.predict(Xd_test)
        regressor_metrics = {
            'mae': round(float(mean_absolute_error(yd_test, predicted_days)), 2),
            'rmse': round(float(np.sqrt(mean_squared_error(yd_test, predicted_days))), 2),
            'r2': round(float(r2_score(yd_test, predicted_days)), 4),
            'training_rows': int(len(Xd_train)),
            'test_rows': int(len(Xd_test)),
        }
        joblib.dump(regressor, REGRESSOR_PATH)
    else:
        if REGRESSOR_PATH.exists():
            REGRESSOR_PATH.unlink()

    metrics = {
        'generated_at': pd.Timestamp.utcnow().isoformat(),
        'dataset': {
            'path': str(dataset_path()),
            'rows': int(len(frame)),
            'delayed': int(y.sum()),
            'no_delay': int(len(y) - y.sum()),
            'delay_rate': round(float(y.mean()), 4),
            'features': FEATURE_COLUMNS,
            'excluded': EXCLUDED_COLUMNS,
        },
        'split': {'train_rows': int(len(X_train)), 'test_rows': int(len(X_test)), 'test_size': test_size, 'seed': seed},
        'algorithms': results,
        'selected': best_name,
        'feature_importance': importance,
        'roc_curves': roc_points,
        'regressor': regressor_metrics,
        'target': TARGET,
    }
    METRICS_PATH.write_text(json.dumps(metrics, indent=2), encoding='utf-8')
    load_bundle.cache_clear()
    return metrics


def read_metrics() -> dict:
    if not METRICS_PATH.exists():
        return {}
    try:
        return json.loads(METRICS_PATH.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return {}


@lru_cache(maxsize=1)
def load_bundle():
    """Load the persisted pipeline, training on first use if necessary."""
    if not CLASSIFIER_PATH.exists():
        train_models()
    pipeline = joblib.load(CLASSIFIER_PATH)
    regressor = joblib.load(REGRESSOR_PATH) if REGRESSOR_PATH.exists() else None
    metrics = read_metrics()
    return pipeline, regressor, metrics


def model_ready() -> bool:
    return CLASSIFIER_PATH.exists()


def build_feature_row(project) -> dict:
    return {
        'state': project.state or 'Unknown',
        'district': project.district or 'Unknown',
        'project_type': project.project_type or 'Unknown',
        'land_area_acres': float(project.land_area_acres or 0),
        'total_land_parcels': int(project.total_land_parcels or 0),
        'acquired_land_parcels': int(project.acquired_land_parcels or 0),
        'ownership_disputes': int(project.ownership_disputes or 0),
        'compensation_status': project.compensation_status,
        'compensation_completion_percentage': float(project.compensation_completion_percentage or 0),
        'approval_status': project.approval_status,
        'environmental_clearance_status': project.environmental_clearance_status,
        'legal_case_count': int(project.legal_case_count or 0),
        'rehabilitation_status': project.rehabilitation_status,
        'project_budget': float(project.project_budget or 0),
        'allocated_budget': float(project.allocated_budget or 0),
        'project_duration_months': int(project.project_duration_months or 0),
        'elapsed_months': int(project.elapsed_months or 0),
        'stakeholder_issues': int(project.stakeholder_issues or 0),
        'acquisition_progress': project.acquisition_progress,
        'budget_utilisation': project.budget_utilisation,
    }


def _risk_level(probability: float) -> str:
    if probability >= RISK_HIGH_THRESHOLD:
        return 'High'
    if probability >= RISK_LOW_THRESHOLD:
        return 'Medium'
    return 'Low'


def _factor_attribution(project, metrics: dict) -> list:
    importances = {
        item['feature']: item['importance']
        for item in metrics.get('feature_importance', [])
    }
    rows = []
    for feature, (label, severity_fn, description) in FACTOR_RULES.items():
        try:
            severity = float(severity_fn(project))
        except (AttributeError, TypeError, ValueError, ZeroDivisionError):
            severity = 0.0
        importance = float(importances.get(feature, 0.0))
        impact = round(importance * max(0.0, min(1.0, severity)), 4)
        if impact <= 0:
            continue
        rows.append({
            'factor_name': label,
            'impact': impact,
            'direction': 'increases',
            'description': description,
        })
    rows.sort(key=lambda row: row['impact'], reverse=True)
    return rows[:6]


def _build_result(project, probability: float, predicted_days: float, metrics: dict) -> dict:
    risk = _risk_level(probability)
    predicted_days = round(max(0.0, float(predicted_days)), 1)
    planned_end = project.planned_end_date
    estimated_end = planned_end + timedelta(days=int(round(predicted_days))) if planned_end else None

    return {
        'delay_probability': round(float(probability), 4),
        'risk_level': risk,
        'predicted_delay_days': predicted_days,
        'estimated_completion_date': estimated_end,
        'planned_end_date': planned_end,
        'factors': _factor_attribution(project, metrics),
        'model_name': metrics.get('selected', 'Random Forest'),
        'model_version': metrics.get('generated_at', ''),
        'feature_row': build_feature_row(project),
        'metrics': metrics,
    }


def predict_delay(project) -> dict:
    """Run the persisted model for one project and return an explainable result."""
    pipeline, regressor, metrics = load_bundle()
    row = build_feature_row(project)
    frame = pd.DataFrame([row])
    for column in NUMERIC_FEATURES:
        frame[column] = pd.to_numeric(frame[column], errors='coerce')
    probability = float(pipeline.predict_proba(frame[FEATURE_COLUMNS])[0, 1])

    predicted_days = 0.0
    if regressor is not None and probability >= 0.5:
        predicted_days = float(max(0.0, regressor.predict(frame[FEATURE_COLUMNS])[0]))

    return _build_result(project, probability, predicted_days, metrics)


def predict_batch(projects) -> list:
    """Vectorised prediction used when seeding or retraining the workspace."""
    projects = list(projects)
    if not projects:
        return []
    pipeline, regressor, metrics = load_bundle()
    rows = [build_feature_row(project) for project in projects]
    frame = pd.DataFrame(rows)
    for column in NUMERIC_FEATURES:
        frame[column] = pd.to_numeric(frame[column], errors='coerce')
    frame = frame[FEATURE_COLUMNS]
    probabilities = pipeline.predict_proba(frame)[:, 1]
    days = np.zeros(len(projects), dtype=float)
    if regressor is not None:
        delayed_mask = probabilities >= 0.5
        if delayed_mask.any():
            days[delayed_mask] = np.maximum(0.0, regressor.predict(frame.loc[delayed_mask]))
    return [
        _build_result(project, probability, day, metrics)
        for project, probability, day in zip(projects, probabilities, days)
    ]


def model_summary() -> dict:
    """Metrics plus file state for the Model Performance page."""
    metrics = read_metrics()
    return {
        'ready': model_ready(),
        'metrics': metrics,
        'classifier_path': str(CLASSIFIER_PATH),
        'regressor_path': str(REGRESSOR_PATH) if REGRESSOR_PATH.exists() else '',
        'trained_at': metrics.get('generated_at', ''),
    }
