from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.employees.models import Employee
from apps.employees.base_org_assignment import skip_base_org_assignment
from apps.employees.serializers import EmployeeSerializer
from apps.organisations.models import Organisation, OrganisationLocation, OrganisationMemberProfile
from apps.organisations.serializers import (
    OrganisationLocationSerializer,
    OrganisationMemberAssignmentSerializer,
    OrganisationMemberProfileSerializer,
    OrganisationSerializer,
)
from apps.users.permissions import IsSuperAdmin


def _generate_employee_id():
    from uuid import uuid4

    candidate = f'AUTO-{uuid4().hex[:10].upper()}'
    while Employee.objects.filter(employee_id=candidate).exists():
        candidate = f'AUTO-{uuid4().hex[:10].upper()}'
    return candidate


class OrganisationViewSet(viewsets.ModelViewSet):
    queryset = Organisation.objects.all()
    serializer_class = OrganisationSerializer
    pagination_class = None

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy', 'add_members'):
            return [IsSuperAdmin()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        organisation = serializer.save()
        if organisation.is_base:
            organisation.members.add(*Employee.objects.all())

    @action(detail=True, methods=['post'], url_path='members', url_name='add-members')
    def add_members(self, request, pk=None):
        organisation = self.get_object()
        if organisation.is_base:
            return Response(
                {'detail': 'Base organisation members are managed automatically.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = OrganisationMemberAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        employee_ids = serializer.validated_data.get('employee_ids', [])
        new_members = serializer.validated_data.get('new_members', [])

        if employee_ids:
            employees = Employee.objects.filter(id__in=employee_ids, organisations__is_base=True).distinct()
            organisation.members.add(*employees)
            for employee in employees:
                OrganisationMemberProfile.objects.get_or_create(
                    organisation=organisation,
                    employee=employee,
                )

        created_employees = []
        for member_data in new_members:
            member_data = member_data.copy()
            if not member_data.get('employee_id'):
                member_data['employee_id'] = _generate_employee_id()

            employee_serializer = EmployeeSerializer(data=member_data)
            employee_serializer.is_valid(raise_exception=True)
            with skip_base_org_assignment():
                employee = employee_serializer.save()
            employee.organisations.add(organisation)
            OrganisationMemberProfile.objects.get_or_create(
                organisation=organisation,
                employee=employee,
            )
            created_employees.append(employee)

        assigned_ids = list(Employee.objects.filter(organisations=organisation).values_list('id', flat=True))

        return Response(
            {
                'detail': 'Members added to organisation.',
                'organisation_id': organisation.id,
                'assigned_member_ids': assigned_ids,
                'created_member_ids': [employee.id for employee in created_employees],
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=['get', 'patch', 'delete'], url_path='member-profiles', url_name='member-profiles')
    def member_profiles(self, request, pk=None):
        organisation = self.get_object()
        if organisation.is_base:
            return Response(
                {'detail': 'Client-specific member profiles are only available for client organisations.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if request.method in ('PATCH', 'DELETE') and getattr(request.user, 'role', None) != 'super_admin':
            return Response({'detail': 'You do not have permission to modify member profiles.'}, status=status.HTTP_403_FORBIDDEN)

        if request.method == 'GET':
            profiles = []
            employees = Employee.objects.filter(organisations=organisation).prefetch_related('organisations')
            for employee in employees:
                profile, _ = OrganisationMemberProfile.objects.get_or_create(
                    organisation=organisation,
                    employee=employee,
                )
                profiles.append(profile)
            serializer = OrganisationMemberProfileSerializer(profiles, many=True)
            return Response(serializer.data)

        if request.method == 'DELETE':
            employee_id = request.data.get('employee') or request.data.get('id')
            if not employee_id:
                return Response({'detail': 'Employee is required.'}, status=status.HTTP_400_BAD_REQUEST)

            try:
                employee = Employee.objects.get(id=employee_id, organisations=organisation)
            except Employee.DoesNotExist:
                return Response({'detail': 'Employee is not a member of this organisation.'}, status=status.HTTP_404_NOT_FOUND)

            OrganisationMemberProfile.objects.filter(organisation=organisation, employee=employee).delete()
            employee.organisations.remove(organisation)
            return Response(status=status.HTTP_204_NO_CONTENT)

        employee_id = request.data.get('employee') or request.data.get('id')
        if not employee_id:
            return Response({'detail': 'Employee is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            employee = Employee.objects.get(id=employee_id, organisations=organisation)
        except Employee.DoesNotExist:
            return Response({'detail': 'Employee is not a member of this organisation.'}, status=status.HTTP_404_NOT_FOUND)

        profile, _ = OrganisationMemberProfile.objects.get_or_create(
            organisation=organisation,
            employee=employee,
        )
        serializer = OrganisationMemberProfileSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=True, methods=['get'], url_path='locations', url_name='list-locations')
    def list_locations(self, request, pk=None):
        organisation = self.get_object()
        locations = OrganisationLocation.objects.filter(organisation=organisation)
        serializer = OrganisationLocationSerializer(locations, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='locations/add', url_name='add-location')
    def add_location(self, request, pk=None):
        organisation = self.get_object()
        serializer = OrganisationLocationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(organisation=organisation)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['patch'], url_path='locations/(?P<location_id>[0-9]+)/edit', url_name='update-location')
    def update_location(self, request, pk=None, location_id=None):
        organisation = self.get_object()
        try:
            location = OrganisationLocation.objects.get(id=location_id, organisation=organisation)
        except OrganisationLocation.DoesNotExist:
            return Response({'detail': 'Location not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = OrganisationLocationSerializer(location, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['delete'], url_path='locations/(?P<location_id>[0-9]+)', url_name='delete-location')
    def delete_location(self, request, pk=None, location_id=None):
        organisation = self.get_object()
        try:
            location = OrganisationLocation.objects.get(id=location_id, organisation=organisation)
        except OrganisationLocation.DoesNotExist:
            return Response({'detail': 'Location not found.'}, status=status.HTTP_404_NOT_FOUND)
        location.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
