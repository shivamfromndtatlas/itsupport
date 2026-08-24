from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    SureMDMConnectionView,
    SureMDMViewSet,
    SynthesiaConnectionView,
    SynthesiaInvoiceViewSet,
    SynthesiaViewSet,
    TeamViewerConnectionView,
    TeamViewerViewSet,
    TrellixConnectionView,
    TrellixViewSet,
)

router = DefaultRouter()
router.register(r'suremdm', SureMDMViewSet, basename='suremdm')
router.register(r'trellix', TrellixViewSet, basename='trellix')
router.register(r'synthesia', SynthesiaViewSet, basename='synthesia')
router.register(r'synthesia-invoices', SynthesiaInvoiceViewSet, basename='synthesia-invoice')
router.register(r'teamviewer', TeamViewerViewSet, basename='teamviewer')

urlpatterns = [
    path('suremdm/connection/', SureMDMConnectionView.as_view(), name='suremdm-connection'),
    path('trellix/connection/', TrellixConnectionView.as_view(), name='trellix-connection'),
    path('synthesia/connection/', SynthesiaConnectionView.as_view(), name='synthesia-connection'),
    path('teamviewer/connection/', TeamViewerConnectionView.as_view(), name='teamviewer-connection'),
    path('', include(router.urls)),
]
