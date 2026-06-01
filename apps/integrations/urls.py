from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import SureMDMConnectionView, SureMDMViewSet

router = DefaultRouter()
router.register(r'suremdm', SureMDMViewSet, basename='suremdm')

urlpatterns = [
    path('suremdm/connection/', SureMDMConnectionView.as_view(), name='suremdm-connection'),
    path('', include(router.urls)),
]
