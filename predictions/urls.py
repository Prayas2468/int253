from django.urls import path

from . import views

app_name = 'predictions'

urlpatterns = [
    path('projects/', views.project_list, name='project_list'),
    path('projects/add/', views.project_create, name='project_create'),
    path('projects/<int:pk>/', views.project_detail, name='project_detail'),
    path('projects/<int:pk>/edit/', views.project_edit, name='project_edit'),
    path('projects/<int:pk>/delete/', views.project_delete, name='project_delete'),
    path('projects/<int:pk>/archive/', views.project_archive, name='project_archive'),
    path('projects/<int:pk>/predict/', views.project_predict, name='project_predict'),
    path('data-import/', views.data_import, name='data_import'),
    path('data-import/template/', views.csv_template, name='csv_template'),
    path('predict/', views.predict_scenario, name='predict'),
    path('predictions/<int:pk>/', views.prediction_detail, name='prediction_detail'),
    path('prediction-history/', views.prediction_history, name='prediction_history'),
    path('risk-analytics/', views.risk_analytics, name='risk_analytics'),
    path('monitoring/', views.monitoring, name='monitoring'),
    path('mitigation/', views.mitigation_list, name='mitigation_list'),
    path('mitigation/<int:pk>/status/', views.mitigation_update, name='mitigation_update'),
    path('model-performance/', views.model_performance, name='model_performance'),
    path('model-performance/train/', views.train_model, name='train_model'),
    path('settings/', views.settings_view, name='settings'),
]
