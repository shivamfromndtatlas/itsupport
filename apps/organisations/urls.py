from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import OrganisationViewSet

router = DefaultRouter()
router.register(r'', OrganisationViewSet, basename='organisation')

urlpatterns = [
    path('', include(router.urls)),
]
