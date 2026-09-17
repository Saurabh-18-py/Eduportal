from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from core_views import home_view
from notifications.views import service_worker

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home_view, name='home'),
    path('accounts/', include('accounts.urls')),
    path('notes/', include('notes.urls')),
    path('mocktest/', include('mocktest.urls')),
    path('notifications/', include('notifications.urls')),
    path('sw.js', service_worker, name='service_worker'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
