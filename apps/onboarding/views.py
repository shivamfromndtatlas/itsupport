from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.employees.models import Employee
from apps.employees.serializers import CORE_PROCESS_MAP
from apps.users.permissions import IsHROrSuperAdmin, IsITOrHROrSuperAdmin

from .models import NewJoinerRequest
from .serializers import NewJoinerRequestSerializer


class NewJoinerRequestViewSet(viewsets.ModelViewSet):
    """
    HR creates new joiner requests.
    IT Specialists and Super Admins can confirm or reject them.
    On confirmation, an Employee record is automatically created.
    """

    queryset = NewJoinerRequest.objects.select_related(
        'submitted_by', 'confirmed_by'
    ).all()
    serializer_class = NewJoinerRequestSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        status_filter = self.request.query_params.get('status')

        if status_filter:
            valid_statuses = {choice[0] for choice in NewJoinerRequest.STATUS_CHOICES}
            if status_filter in valid_statuses:
                queryset = queryset.filter(status=status_filter)
            else:
                queryset = queryset.none()

        return queryset

    def get_permissions(self):
        if self.action == 'create':
            return [IsHROrSuperAdmin()]
        if self.action in ('confirm', 'reject'):
            return [IsITOrHROrSuperAdmin()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(submitted_by=self.request.user)

    @action(detail=True, methods=['post'], url_path='confirm')
    def confirm(self, request, pk=None):
        """
        Mark the request as confirmed and auto-create the Employee record.
        """
        onboarding_request = self.get_object()

        if onboarding_request.status != 'pending':
            return Response(
                {'detail': f'Request is already {onboarding_request.status}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check for duplicate employee_id or official_email
        if Employee.objects.filter(employee_id=onboarding_request.employee_id).exists():
            return Response(
                {'detail': 'An employee with this employee ID already exists.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if Employee.objects.filter(official_email=onboarding_request.personal_email).exists():
            return Response(
                {'detail': 'An employee with this email already exists.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Update onboarding request
        onboarding_request.status = 'confirmed'
        onboarding_request.confirmed_by = request.user
        onboarding_request.confirmed_at = timezone.now()
        onboarding_request.save()

        # Auto-create Employee record
        employee = Employee.objects.create(
            employee_id=onboarding_request.employee_id,
            full_name=onboarding_request.full_name,
            alias_name=onboarding_request.alias_name,
            official_email=onboarding_request.personal_email,
            contact_number=onboarding_request.contact_number,
            core_process_code=onboarding_request.core_process,
            core_process_name=CORE_PROCESS_MAP.get(onboarding_request.core_process, ''),
            designation=onboarding_request.designation,
            date_of_joining=onboarding_request.date_of_joining,
        )

        return Response(
            {
                'detail': 'Request confirmed and employee record created.',
                'employee_id': employee.employee_id,
                'onboarding': NewJoinerRequestSerializer(onboarding_request).data,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=['post'], url_path='reject')
    def reject(self, request, pk=None):
        """Mark the request as rejected."""
        onboarding_request = self.get_object()

        if onboarding_request.status != 'pending':
            return Response(
                {'detail': f'Request is already {onboarding_request.status}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        onboarding_request.status = 'rejected'
        onboarding_request.confirmed_by = request.user
        onboarding_request.confirmed_at = timezone.now()
        onboarding_request.save()

        return Response(
            {
                'detail': 'Request rejected.',
                'onboarding': NewJoinerRequestSerializer(onboarding_request).data,
            },
            status=status.HTTP_200_OK,
        )
