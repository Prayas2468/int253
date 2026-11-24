from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    path('', views.notification_list, name='list'),
    path('unread/', views.unread_count, name='unread'),
    path('read-all/', views.mark_all_read, name='mark_all_read'),
    path('<int:pk>/read/', views.mark_read, name='mark_read'),
]
