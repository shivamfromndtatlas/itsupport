from rest_framework import viewsets
from apps.users.permissions import IsSuperAdmin

from .models import ActivityLog
from .serializers import ActivityLogSerializer


class ActivityLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ActivityLog.objects.select_related('user').all()
    serializer_class = ActivityLogSerializer
    pagination_class = None

    def get_permissions(self):
        return [IsSuperAdmin()]

    def get_queryset(self):
        queryset = super().get_queryset()
        user_id = self.request.query_params.get('user_id')
        action = self.request.query_params.get('action')
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        if action:
            queryset = queryset.filter(action__icontains=action)
        return queryset
