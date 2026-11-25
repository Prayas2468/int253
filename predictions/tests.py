"""Tests for the predictive analytics application."""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model

from predictions import ml, services, synthetic
from predictions.models import LandAcquisitionProject, ProjectPrediction


class SyntheticDatasetTests(TestCase):
    def test_generator_returns_at_least_two_thousand_rows(self):
        frame = synthetic.generate_dataset()
        self.assertGreaterEqual(len(frame), 2000)

    def test_dataset_has_required_columns(self):
        frame = synthetic.generate_dataset()
        for column in ('project_id', 'delay_status', 'delay_days', 'ownership_disputes',
                       'compensation_completion_percentage', 'legal_case_count'):
            self.assertIn(column, frame.columns)

    def test_delay_rate_is_meaningful(self):
        frame = synthetic.generate_dataset()
        rate = frame['delay_status'].mean()
        self.assertGreater(rate, 0.3)
        self.assertLess(rate, 0.85)


class ModelTests(TestCase):
    def test_metrics_file_exists_and_has_algorithms(self):
        metrics = ml.read_metrics()
        self.assertIn('algorithms', metrics)
        for name in ('Random Forest', 'Decision Tree', 'Logistic Regression'):
            self.assertIn(name, metrics['algorithms'])

    def test_selected_model_has_required_metrics(self):
        metrics = ml.read_metrics()
        selected = metrics['selected']
        values = metrics['algorithms'][selected]
        for key in ('accuracy', 'precision', 'recall', 'f1', 'roc_auc', 'confusion_matrix'):
            self.assertIn(key, values)

    def test_model_artifacts_load(self):
        self.assertTrue(ml.model_ready())
        bundle = ml.load_bundle()
        self.assertIsNotNone(bundle)
        self.assertTrue(ml.model_ready())


class ProjectCrudTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='tester', email='tester@example.com', password='secret123')
        self.client = Client()
        self.client.login(username='tester@example.com', password='secret123')

    def test_create_project(self):
        response = self.client.post('/analytics/projects/add/', {
            'project_name': 'Test Project', 'state': 'Bihar', 'district': 'Patna',
            'project_type': 'Highway Expansion', 'land_area_acres': 12.5,
            'total_land_parcels': 10, 'acquired_land_parcels': 3,
            'ownership_disputes': 2, 'compensation_status': 'pending',
            'compensation_completion_percentage': 20, 'approval_status': 'pending',
            'environmental_clearance_status': 'pending', 'legal_case_count': 1,
            'rehabilitation_status': 'not_started', 'project_budget': 50,
            'allocated_budget': 20, 'project_duration_months': 24,
            'elapsed_months': 6, 'stakeholder_issues': 1, 'start_date': '2026-01-15',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(LandAcquisitionProject.objects.filter(project_name='Test Project').exists())

    def test_project_detail_and_edit(self):
        project = LandAcquisitionProject.objects.create(
            project_name='Detail Project', state='Bihar', district='Gaya',
            project_type='Industrial Corridor', land_area_acres=40,
            total_land_parcels=25, acquired_land_parcels=5,
            ownership_disputes=6, compensation_status='pending',
            compensation_completion_percentage=10, approval_status='pending',
            environmental_clearance_status='pending', legal_case_count=3,
            rehabilitation_status='not_started', project_budget=120,
            allocated_budget=30, project_duration_months=36, elapsed_months=8,
            stakeholder_issues=4, start_date='2026-02-01',
        )
        response = self.client.get(f'/analytics/projects/{project.pk}/')
        self.assertEqual(response.status_code, 200)
        response = self.client.post(f'/analytics/projects/{project.pk}/edit/', {
            'project_name': 'Detail Project Updated', 'state': 'Bihar', 'district': 'Gaya',
            'project_type': 'Industrial Corridor', 'land_area_acres': 40,
            'total_land_parcels': 25, 'acquired_land_parcels': 5,
            'ownership_disputes': 6, 'compensation_status': 'pending',
            'compensation_completion_percentage': 10, 'approval_status': 'pending',
            'environmental_clearance_status': 'pending', 'legal_case_count': 3,
            'rehabilitation_status': 'not_started', 'project_budget': 120,
            'allocated_budget': 30, 'project_duration_months': 36,
            'elapsed_months': 8, 'stakeholder_issues': 4, 'start_date': '2026-02-01',
        })
        self.assertEqual(response.status_code, 302)
        project.refresh_from_db()
        self.assertEqual(project.project_name, 'Detail Project Updated')


class PredictionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='tester2', email='tester2@example.com', password='secret123')
        self.client = Client()
        self.client.login(username='tester2@example.com', password='secret123')

    def test_predict_scenario_persists_prediction(self):
        before = ProjectPrediction.objects.count()
        response = self.client.post('/analytics/predict/', {
            'project_name': 'Scenario Project', 'state': 'Bihar', 'district': 'Gaya',
            'project_type': 'Industrial Corridor', 'land_area_acres': 40,
            'total_land_parcels': 25, 'acquired_land_parcels': 5,
            'ownership_disputes': 6, 'compensation_status': 'pending',
            'compensation_completion_percentage': 10, 'approval_status': 'pending',
            'environmental_clearance_status': 'pending', 'legal_case_count': 3,
            'rehabilitation_status': 'not_started', 'project_budget': 120,
            'allocated_budget': 30, 'project_duration_months': 36,
            'elapsed_months': 8, 'stakeholder_issues': 4,
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ProjectPrediction.objects.count(), before + 1)
        prediction = ProjectPrediction.objects.order_by('-pk').first()
        self.assertIn(prediction.risk_level, ('Low', 'Medium', 'High'))
        self.assertGreaterEqual(prediction.delay_probability, 0.0)
        self.assertLessEqual(prediction.delay_probability, 1.0)


class DashboardAndReportsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='tester3', email='tester3@example.com', password='secret123')
        self.client = Client()
        self.client.login(username='tester3@example.com', password='secret123')

    def test_dashboard_renders(self):
        response = self.client.get('/dashboard/')
        self.assertEqual(response.status_code, 200)

    def test_report_endpoints(self):
        for url in ('/reports/', '/reports/projects/csv/', '/reports/projects/pdf/',
                    '/reports/predictions/csv/', '/reports/risk/csv/', '/reports/model/csv/',
                    '/reports/excel/'):
            response = self.client.get(url)
            self.assertIn(response.status_code, (200,), msg=url)

    def test_prediction_history_and_risk_analytics(self):
        for url in ('/analytics/prediction-history/', '/analytics/risk-analytics/',
                    '/analytics/monitoring/', '/analytics/mitigation/', '/analytics/model-performance/'):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, msg=url)
