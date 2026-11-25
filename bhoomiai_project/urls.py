from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

urlpatterns = [
    # Browsers (and the Django admin) request /favicon.ico by default; point it at
    # the branded SVG so it never returns a 404.
    path('favicon.ico', RedirectView.as_view(url='/static/images/favicon.svg', permanent=True)),
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('accounts/', include('accounts.urls')),
    path('dashboard/', include('dashboard.urls')),
    path('documents/', include('documents.urls')),
    path('validation/', include('validation.urls')),
    path('duplicates/', include('duplicates.urls')),
    path('reports/', include('reports.urls')),
    path('notifications/', include('notifications.urls')),
    path('analytics/', include('predictions.urls')),
]

# THIS IS CRITICAL FOR CSS/IMAGES TO LOAD:
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL,
                          document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL,
                          document_root=settings.MEDIA_ROOT)
