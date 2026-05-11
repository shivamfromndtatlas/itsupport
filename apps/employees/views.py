from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.users.permissions import IsHROrSuperAdmin

from .models import Employee
from .serializers import EmployeeSerializer


class EmployeeViewSet(viewsets.ModelViewSet):
    """
    list / retrieve: all authenticated users
    create / update / partial_update / destroy: HR or super_admin only
    """

    queryset = Employee.objects.select_related('line_manager').all()
    serializer_class = EmployeeSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsHROrSuperAdmin()]
        return [IsAuthenticated()]
