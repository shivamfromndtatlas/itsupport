from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.users.permissions import IsHROrSuperAdmin

from .models import Employee
from .serializers import EmployeeAssetAllocationSerializer, EmployeeSerializer


class EmployeeViewSet(viewsets.ModelViewSet):
    """
    list / retrieve: all authenticated users
    create / update / partial_update / destroy: HR or super_admin only
    """

    serializer_class = EmployeeSerializer
    pagination_class = None

    def get_queryset(self):
        scope = self.request.query_params.get('scope')
        organisation_id = self.request.query_params.get('organisation_id')
        core_process_code = self.request.query_params.get('core_process_code')
        # Detail routes must be able to resolve employees outside the base org.
        if self.action in ('retrieve', 'update', 'partial_update', 'destroy', 'dashboard') or scope == 'all':
            queryset = (
                Employee.objects.all()
                .select_related('line_manager')
                .prefetch_related(
                    'organisations',
                    'organisation_profiles__organisation',
                    'asset_allocations__asset__asset_type',
                    'asset_allocations__assigned_by',
                    'asset_allocations__recovered_by',
                )
            )
            if organisation_id:
                queryset = queryset.filter(organisations__id=organisation_id)
            if core_process_code:
                queryset = queryset.filter(core_process_code=core_process_code)
            return queryset.distinct()
        if scope == 'allocatable':
            return (
                Employee.objects.filter(organisations__isnull=False)
                .distinct()
                .select_related('line_manager')
                .prefetch_related('organisations')
            )

        return (
            Employee.objects.filter(organisations__is_base=True)
            .distinct()
            .select_related('line_manager')
            .prefetch_related('organisations')
        )

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsHROrSuperAdmin()]
        return [IsAuthenticated()]

    @action(detail=True, methods=['get'], url_path='dashboard', url_name='dashboard')
    def dashboard(self, request, pk=None):
        employee = self.get_object()
        organisations = list(employee.organisations.all().order_by('-is_base', 'name'))
        profiles = {profile.organisation_id: profile for profile in employee.organisation_profiles.all()}
        primary_profile = next((profiles.get(org.id) for org in organisations if org and not org.is_base and profiles.get(org.id)), None)
        profile_employee_id = primary_profile.employee_code if primary_profile and primary_profile.employee_code else employee.employee_id
        profile_full_name = primary_profile.full_name if primary_profile and primary_profile.full_name else employee.full_name
        profile_alias_name = primary_profile.alias_name if primary_profile and primary_profile.alias_name else employee.alias_name
        profile_email = primary_profile.official_email if primary_profile and primary_profile.official_email else employee.official_email
        profile_contact = primary_profile.contact_number if primary_profile and primary_profile.contact_number else employee.contact_number
        profile_designation = primary_profile.designation if primary_profile and primary_profile.designation else employee.designation
        profile_core_process_code = (
            primary_profile.core_process_code if primary_profile and primary_profile.core_process_code else employee.core_process_code
        )
        profile_core_process_name = dict(Employee.CORE_PROCESS_CHOICES).get(profile_core_process_code, '')
        profile_joining_date = primary_profile.date_of_joining if primary_profile and primary_profile.date_of_joining else employee.date_of_joining
        profile_status = primary_profile.status if primary_profile and primary_profile.status else employee.status

        organisation_cards = []
        base_email = None
        client_emails = []

        for organisation in organisations:
            profile = profiles.get(organisation.id)
            profile_email = profile.official_email if profile and profile.official_email else ''
            profile_designation = profile.designation if profile and profile.designation else ''
            profile_joining_date = profile.date_of_joining if profile and profile.date_of_joining else None
            email = employee.official_email if organisation.is_base else (profile_email or employee.official_email)
            card = {
                'id': organisation.id,
                'name': organisation.name,
                'logo': organisation.logo.url if organisation.logo else None,
                'is_base': organisation.is_base,
                'email': email,
                'designation': profile_designation or employee.designation,
                'date_of_joining': (profile_joining_date or employee.date_of_joining).isoformat()
                if profile_joining_date or employee.date_of_joining
                else None,
            }
            organisation_cards.append(card)

            if organisation.is_base:
                base_email = email
            else:
                client_emails.append(card)

        asset_allocations = employee.asset_allocations.all().order_by('-assigned_date', '-created_at')

        return Response(
            {
                **EmployeeSerializer(employee, context={'request': request}).data,
                'employee_id': profile_employee_id,
                'full_name': profile_full_name,
                'alias_name': profile_alias_name,
                'official_email': profile_email,
                'contact_number': profile_contact,
                'core_process_code': profile_core_process_code,
                'core_process_name': profile_core_process_name,
                'designation': profile_designation,
                'date_of_joining': profile_joining_date.isoformat() if profile_joining_date else None,
                'status': profile_status,
                'date_of_separation': employee.date_of_separation.isoformat() if employee.date_of_separation else None,
                'organisation_cards': organisation_cards,
                'base_email': base_email,
                'client_emails': client_emails,
                'assigned_assets': EmployeeAssetAllocationSerializer(asset_allocations, many=True, context={'request': request}).data,
            }
        )
