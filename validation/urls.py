from django.urls import path
from . import views

app_name = 'validation'

urlpatterns = [
    path('', views.results_list, name='list'),
    path('run-all/', views.run_all, name='run_all'),
    path('<int:pk>/run/', views.run_validation, name='run'),
]
