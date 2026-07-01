from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AssetAttributeViewSet,
    AssetChoicesViewSet,
    AssetTypeAttributeRequirementViewSet,
    AssetTypeViewSet,
    AssetViewSet,
    SoftwareLicenseViewSet,
)

router = DefaultRouter()
router.register(r'asset-types', AssetTypeViewSet, basename='asset-type')
router.register(r'asset-attributes', AssetAttributeViewSet, basename='asset-attribute')
router.register(r'asset-type-requirements', AssetTypeAttributeRequirementViewSet, basename='asset-type-requirement')
router.register(r'assets', AssetViewSet, basename='asset')
router.register(r'software-licenses', SoftwareLicenseViewSet, basename='software-license')
router.register(r'form-choices', AssetChoicesViewSet, basename='form-choices')

urlpatterns = [
    path('', include(router.urls)),
]
