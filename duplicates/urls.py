from django.urls import path
from . import views

app_name = 'duplicates'

urlpatterns = [
    path('', views.list_view, name='list'),
    path('scan/', views.scan, name='scan'),
    path('<int:pk>/review/', views.review, name='review'),
]
