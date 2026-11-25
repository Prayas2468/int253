# Predictive Analytics System for Early Detection of Land Acquisition Delays

**Category:** Smart Automation  
**Brand / Product:** BhoomiAI  
**Status:** Working academic prototype (synthetic data)

An intelligent predictive analytics platform that uses Machine Learning on synthetic
land acquisition project data to identify potential delays, analyse risk factors,
monitor project progress and support preventive decision-making through an
interactive dashboard.

---

## 1. Problem statement

Land acquisition is a critical dependency for infrastructure and development
projects. Delays are usually caused by a combination of ownership disputes,
pending compensation, approval bottlenecks, legal cases, environmental clearance
and incomplete rehabilitation. Detecting these risks early allows programme
managers to intervene before a delay becomes unavoidable.

This project builds a reproducible predictive analytics workspace on top of a
clearly labelled synthetic dataset, so the end-to-end pipeline (data → model →
dashboard → reports) can be demonstrated without exposing real landowner or
personal information.

## 2. Objectives

- Generate a realistic, documented synthetic land-acquisition dataset (≥ 2,000 rows).
- Train and compare Random Forest, Decision Tree and Logistic Regression classifiers.
- Predict the probability of a land-acquisition delay and label the risk as Low / Medium / High.
- Estimate expected delay duration for projects flagged as delayed.
- Explain each prediction with contributing factors and suggested mitigation actions.
- Provide an interactive dashboard, project management, monitoring, risk analytics,
  prediction history and report exports.
- Preserve the existing BhoomiAI visual identity, theme, logo, icons and components.

## 3. Key features

- **Overview dashboard** — KPI cards, planned vs actual progress, predicted project end,
  project details, risk profile, phase distribution, top risks and monitoring table.
- **Project management** — create, view, edit, archive and delete projects; search, filter
  and sort by state, status and risk level.
- **Data import** — CSV import with validation, CSV template download, and a one-click
  rebuild of the 2,400-row synthetic demo workspace.
- **Delay prediction** — real saved-model inference with delay probability, risk band,
  expected delay days, contributing factors and mitigation suggestions.
- **Risk analytics** — overall risk distribution, state-wise and district-wise exposure,
  compensation, approval and legal bottleneck analysis, progress and feature importance.
- **Project monitoring** — acquisition and compensation progress with risk and delay estimates.
- **Mitigation plans** — system-suggested preventive actions with a user-controlled workflow status.
- **Model performance** — accuracy, precision, recall, F1, confusion matrices, ROC curves and
  feature importance for all three candidates.
- **Prediction history** — audit trail of every stored prediction with model version.
- **Reports & exports** — CSV, PDF and Excel exports generated from live data and persisted metrics.
- **Notifications & settings** — unread notification badge and theme preference.

## 4. Technology stack

- **Backend:** Python 3, Django 6.1.3
- **Database:** SQLite (`db.sqlite3`)
- **Machine learning:** scikit-learn, pandas, numpy, joblib
- **Frontend:** Django templates, existing BhoomiAI CSS design system, Chart.js
- **Reports:** reportlab (PDF), openpyxl (Excel), standard-library CSV
- **Authentication:** Django auth with a custom email-based user model

## 5. System architecture

```
data/land_acquisition_projects.csv        <- synthetic dataset (2,400 rows)
ml_artifacts/                            <- trained classifier + regressor + metrics.json
predictions/                             <- Django app: models, services, ML pipeline, views
  synthetic.py                           <- documented synthetic data generator
  ml.py                                  <- training, evaluation, serialization, inference
  services.py                            <- import, prediction persistence, analytics
  models.py                              <- LandAcquisitionProject, ProjectPrediction, ...
  views.py / forms.py / urls.py
templates/                               <- BhoomiAI templates (base, base_app, pages)
static/                                  <- existing CSS/JS + predictive.css + analytics.js
reports/                                 <- CSV / PDF / Excel exports
```

All analytics values come from the database or `ml_artifacts/metrics.json`. Nothing on
the dashboard or in the reports is hardcoded.

## 6. Synthetic dataset

- **File:** `data/land_acquisition_projects.csv`
- **Rows:** 2,400
- **Delay rate:** 56.87 % (1,365 delayed)
- **States:** multiple Indian states and union territories
- **Labelled:** every row carries `is_synthetic` semantics in the application; the dataset
  is documented as synthetic and intended for academic demonstration only.

Key features: `project_id`, `project_name`, `state`, `district`, `project_type`,
`land_area_acres`, `total_land_parcels`, `acquired_land_parcels`,
`ownership_disputes`, `compensation_status`, `compensation_completion_percentage`,
`approval_status`, `environmental_clearance_status`, `legal_case_count`,
`rehabilitation_status`, `project_budget`, `allocated_budget`,
`project_duration_months`, `elapsed_months`, `stakeholder_issues`, `delay_status`,
`delay_days`.

### Generation assumptions

- Delay risk increases with ownership disputes, legal cases, stakeholder issues,
  pending/low compensation completion, pending approvals, pending environmental
  clearance and incomplete rehabilitation.
- `delay_status` (binary) and `delay_days` are derived from a documented risk score
  with controlled noise; they are **excluded** from model inputs to prevent leakage.
- IDs, dates and the target columns are never used as prediction inputs.
- No real landowner or personal information is used.

Regenerate with:

```bash
python manage.py generate_synthetic_data
python manage.py generate_synthetic_data --seed-db
```

## 7. Machine learning

### Pipeline

- Dataset loading and cleaning (`predictions/synthetic.py`, `predictions/ml.py`)
- Missing-value handling via `SimpleImputer`
- Categorical encoding via `OneHotEncoder`
- Numerical scaling via `StandardScaler`
- Stratified 80 / 20 train-test split
- Three candidate classifiers trained on the same preprocessing pipeline
- A separate Random Forest regressor for delay duration on delayed projects only
- Serialization with `joblib` to `ml_artifacts/`

### Candidates

1. Random Forest Classifier
2. Decision Tree Classifier
3. Logistic Regression

### Selection

The candidate with the highest ROC-AUC on the test split is selected and activated.
On the current dataset this is **Logistic Regression**.

### Persisted metrics (`ml_artifacts/metrics.json`)

| Algorithm | Accuracy | Precision | Recall | F1 | ROC-AUC |
|---|---:|---:|---:|---:|---:|
| Logistic Regression (selected) | 0.715 | 0.774 | 0.703 | 0.737 | 0.784 |
| Random Forest | 0.706 | — | — | 0.749 | 0.761 |
| Decision Tree | 0.637 | — | — | 0.672 | 0.668 |

Delay-duration regressor (Random Forest, delayed projects only):
MAE 50.37 days, RMSE 77.65 days, R² 0.622.

All values are read from `ml_artifacts/metrics.json`; nothing is hardcoded.

### Risk thresholds

- Delay probability `< 0.35` → Low
- `0.35 – 0.649` → Medium
- `>= 0.65` → High
- Delay outcome threshold `>= 0.50` → Delayed

### Risk scoring vs. ML

Six rule-based risk cards (Land Ownership, Compensation, Legal, Approval,
Environmental, Rehabilitation) are computed deterministically from project features.
They are displayed alongside, but are separate from, the ML delay probability.

## 8. Database structure

Main models:

- `LandAcquisitionProject` — project snapshot (features, status, synthetic flag)
- `ProjectPrediction` — probability, risk level, delay days, estimated completion,
  model version, timestamp
- `PredictionFactor` — contributing factors with impact scores
- `ModelVersion` — algorithm, version, training rows, metrics, active flag
- `MitigationPlan` — suggested preventive actions with workflow status
- `ActivityLog` — audit trail

Migrations are under `predictions/migrations/`. The database already contains
2,400 seeded projects and predictions; do not reset it.

## 9. Installation

```bash
cd "C:\Users\sachin kumar singh\Downloads\bhoomiai\bhoomiai\bhoomiai_django"
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
```

## 10. Run commands

```bash
# Generate the synthetic dataset (CSV only)
python manage.py generate_synthetic_data

# Generate and seed the database (2,400 projects + predictions)
python manage.py generate_synthetic_data --seed-db

# Train / compare models (writes ml_artifacts/)
python manage.py train_delay_model

# Start the development server
python manage.py runserver
```

Open `http://127.0.0.1:8000/` and sign in. A default admin account can be created
with `python manage.py createsuperuser`.

## 11. Testing

```bash
python manage.py check
python manage.py check --database default
python manage.py test
```

The test suite covers synthetic dataset size and relationships, model metrics and
artifacts, project CRUD, prediction persistence and dashboard/report endpoints.

## 12. Screenshots

Screenshots of the updated application are stored in the `screenshots/` directory:
dashboard, projects, add project, data import, delay prediction, risk analytics,
monitoring, mitigation plans, model performance, prediction history, settings,
reports, home and project detail.

## 13. Limitations

- The dataset is synthetic and intended for academic demonstration only.
- Risk scores and mitigation suggestions are heuristic indicators, not legal or
  financial advice.
- The delay-duration regressor is trained only on delayed projects.
- Python-side aggregation is used for some analytics (acceptable at ~2,400 rows).

## 14. Future scope

- Real project data ingestion with privacy controls.
- Additional algorithms (e.g. XGBoost, gradient boosting) and hyper-parameter tuning.
- Time-series forecasting of acquisition progress.
- Role-based access control and audit dashboards.
- Scheduled retraining and model monitoring.

---

## Synthetic data disclaimer

All project records, delay labels and predictions in this repository are generated
from a documented synthetic process. No real landowner, parcel owner or personal
information is used. The system is an academic demonstration and must not be used
as the sole basis for legal, financial or acquisition decisions.
