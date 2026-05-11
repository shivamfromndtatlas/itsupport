from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    SOPCategoryViewSet,
    SOPChecklistItemViewSet,
    SOPExecutionViewSet,
    SOPStepViewSet,
    SOPViewSet,
)

router = DefaultRouter()
router.register(r'', SOPViewSet, basename='sop')
router.register(r'categories', SOPCategoryViewSet, basename='sop-category')
router.register(r'steps', SOPStepViewSet, basename='sop-step')
router.register(r'checklist-items', SOPChecklistItemViewSet, basename='sop-checklist-item')
router.register(r'executions', SOPExecutionViewSet, basename='sop-execution')

urlpatterns = [
    path('', include(router.urls)),
]
