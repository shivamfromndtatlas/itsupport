from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import TicketCommentViewSet, TicketViewSet

router = DefaultRouter()
router.register(r'', TicketViewSet, basename='ticket')
router.register(r'comments', TicketCommentViewSet, basename='ticket-comment')

urlpatterns = [
    path('', include(router.urls)),
]
