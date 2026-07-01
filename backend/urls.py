from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('apps.users.urls')),
    path('api/organisations/', include('apps.organisations.urls')),
    path('api/employees/', include('apps.employees.urls')),
    path('api/onboarding/', include('apps.onboarding.urls')),
    path('api/sop/', include('apps.sop.urls')),
    path('api/inventory/', include('apps.inventory.urls')),
    path('api/allocation/', include('apps.allocation.urls')),
    path('api/tickets/', include('apps.tickets.urls')),
    path('api/integrations/', include('apps.integrations.urls')),
    path('api/activity-log/', include('apps.activity_log.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
