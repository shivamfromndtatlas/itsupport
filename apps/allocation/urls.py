from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AssetAllocationViewSet, LicenseAllocationViewSet, scan_qr

router = DefaultRouter()
router.register(r'assets', AssetAllocationViewSet, basename='asset-allocation')
router.register(r'licenses', LicenseAllocationViewSet, basename='license-allocation')

urlpatterns = [
    path('', include(router.urls)),
    path('scan/<uuid:qr_uuid>/', scan_qr, name='scan-qr'),
]
