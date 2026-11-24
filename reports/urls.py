from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('', views.index, name='index'),
    path('csv/', views.csv_export, name='csv'),
    path('excel/', views.excel_export, name='excel'),
    path('pdf/', views.pdf_export, name='pdf'),
]
