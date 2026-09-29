from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    DellSupportConnectionView,
    DellSupportViewSet,
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
from .views_google_workspace import GoogleWorkspaceConnectionViewSet, GoogleWorkspaceViewSet

router = DefaultRouter()
router.register(r'suremdm', SureMDMViewSet, basename='suremdm')
router.register(r'trellix', TrellixViewSet, basename='trellix')
router.register(r'synthesia', SynthesiaViewSet, basename='synthesia')
router.register(r'synthesia-invoices', SynthesiaInvoiceViewSet, basename='synthesia-invoice')
router.register(r'teamviewer', TeamViewerViewSet, basename='teamviewer')
router.register(r'dell-support', DellSupportViewSet, basename='dell-support')
router.register(r'google-workspace-connections', GoogleWorkspaceConnectionViewSet, basename='google-workspace-connection')
router.register(r'google-workspace', GoogleWorkspaceViewSet, basename='google-workspace')

urlpatterns = [
    path('suremdm/connection/', SureMDMConnectionView.as_view(), name='suremdm-connection'),
    path('trellix/connection/', TrellixConnectionView.as_view(), name='trellix-connection'),
    path('synthesia/connection/', SynthesiaConnectionView.as_view(), name='synthesia-connection'),
    path('teamviewer/connection/', TeamViewerConnectionView.as_view(), name='teamviewer-connection'),
    path('dell-support/connection/', DellSupportConnectionView.as_view(), name='dell-support-connection'),
    path('', include(router.urls)),
]
