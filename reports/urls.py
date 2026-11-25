from django.urls import path

from . import views

app_name = 'reports'

urlpatterns = [
    path('', views.index, name='index'),

    path('projects/csv/', views.projects_csv, name='projects_csv'),
    path('projects/pdf/', views.projects_pdf, name='projects_pdf'),
    path('monitoring/csv/', views.monitoring_csv, name='monitoring_csv'),
    path('monitoring/pdf/', views.monitoring_pdf, name='monitoring_pdf'),
    path('predictions/csv/', views.predictions_csv, name='predictions_csv'),
    path('predictions/pdf/', views.predictions_pdf, name='predictions_pdf'),
    path('risk/csv/', views.risk_csv, name='risk_csv'),
    path('risk/pdf/', views.risk_pdf, name='risk_pdf'),
    path('model/csv/', views.model_csv, name='model_csv'),
    path('model/pdf/', views.model_pdf, name='model_pdf'),
    path('mitigation/csv/', views.mitigation_csv, name='mitigation_csv'),

    path('excel/', views.excel_export, name='excel'),
    # Backwards-compatible aliases.
    path('csv/', views.csv_export, name='csv'),
    path('pdf/', views.pdf_export, name='pdf'),
]
