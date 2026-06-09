from rest_framework import serializers

from apps.organisations.models import Organisation, OrganisationMemberProfile
from apps.employees.models import Employee

CORE_PROCESS_MAP = dict(Employee.CORE_PROCESS_CHOICES)


class OrganisationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organisation
        fields = [
            'id',
            'name',
            'logo',
            'address',
            'city',
            'country',
            'is_base',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, attrs):
        is_base = attrs.get('is_base', False)
        if is_base:
            existing_base = Organisation.objects.filter(is_base=True)
            if self.instance:
                existing_base = existing_base.exclude(pk=self.instance.pk)
            if existing_base.exists():
                raise serializers.ValidationError('A base organisation already exists.')

        if not is_base and not Organisation.objects.filter(is_base=True).exists():
            raise serializers.ValidationError('A base organisation must be created before a client organisation.')

        return attrs


class OrganisationMemberAssignmentSerializer(serializers.Serializer):
    employee_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True,
    )
    new_members = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        allow_empty=True,
    )

    def validate_employee_ids(self, value):
        valid_ids = list(Employee.objects.filter(id__in=value, organisations__is_base=True).values_list('id', flat=True))
        if len(valid_ids) != len(set(value)):
            raise serializers.ValidationError('All assigned employees must already belong to the base organisation.')
        return value


class OrganisationMemberProfileSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    employee = serializers.IntegerField(read_only=True)
    employee_id = serializers.CharField(required=False, allow_blank=True)
    full_name = serializers.CharField(required=False, allow_blank=True)
    alias_name = serializers.CharField(required=False, allow_blank=True)
    official_email = serializers.EmailField(required=False, allow_blank=True)
    contact_number = serializers.CharField(required=False, allow_blank=True)
    designation = serializers.CharField(required=False, allow_blank=True)
    core_process_code = serializers.CharField(required=False, allow_blank=True)
    core_process_name = serializers.CharField(read_only=True)
    date_of_joining = serializers.DateField(required=False, allow_null=True)
    status = serializers.ChoiceField(
        choices=Employee.STATUS_CHOICES,
        required=False,
        allow_blank=True,
    )
    display_name = serializers.CharField(read_only=True)
    is_base_employee = serializers.BooleanField(read_only=True)

    def _value(self, profile, profile_field, employee_field):
        value = getattr(profile, profile_field)
        if value not in (None, ''):
            return value
        return getattr(profile.employee, employee_field)

    def _is_base_employee(self, employee):
        return employee.organisations.filter(is_base=True).exists()

    def to_representation(self, profile):
        employee = profile.employee
        employee_id = self._value(profile, 'employee_code', 'employee_id')
        full_name = self._value(profile, 'full_name', 'full_name')
        alias_name = self._value(profile, 'alias_name', 'alias_name')
        official_email = self._value(profile, 'official_email', 'official_email')
        contact_number = self._value(profile, 'contact_number', 'contact_number')
        designation = self._value(profile, 'designation', 'designation')
        core_process_code = self._value(profile, 'core_process_code', 'core_process_code')
        date_of_joining = profile.date_of_joining or employee.date_of_joining
        status = profile.status or employee.status
        is_base_employee = self._is_base_employee(employee)

        return {
            'id': employee.id,
            'employee': employee.id,
            'employee_id': employee_id,
            'full_name': full_name,
            'alias_name': alias_name,
            'official_email': official_email,
            'contact_number': contact_number,
            'designation': designation,
            'core_process_code': core_process_code,
            'core_process_name': CORE_PROCESS_MAP.get(core_process_code, ''),
            'date_of_joining': date_of_joining.isoformat() if date_of_joining else None,
            'status': status,
            'display_name': alias_name if is_base_employee and alias_name else full_name,
            'is_base_employee': is_base_employee,
        }

    def update(self, profile, validated_data):
        field_map = {
            'employee_id': 'employee_code',
            'full_name': 'full_name',
            'alias_name': 'alias_name',
            'official_email': 'official_email',
            'contact_number': 'contact_number',
            'designation': 'designation',
            'core_process_code': 'core_process_code',
            'date_of_joining': 'date_of_joining',
            'status': 'status',
        }
        for source, target in field_map.items():
            if source in validated_data:
                setattr(profile, target, validated_data[source] or None if source == 'date_of_joining' else validated_data[source])
        profile.save()
        return profile

    def validate_new_members(self, value):
        for member in value:
            if 'employee_id' not in member or 'full_name' not in member or 'official_email' not in member:
                raise serializers.ValidationError('New members must include employee_id, full_name, and official_email.')
        return value
