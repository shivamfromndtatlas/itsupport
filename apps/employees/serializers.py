from rest_framework import serializers

from apps.organisations.models import Organisation
from apps.inventory.serializers import AssetSerializer, SoftwareLicenseSerializer
from apps.allocation.models import AssetAllocation, LicenseAllocation
from . import alias_rules
from .models import Employee

CORE_PROCESS_MAP = dict(Employee.CORE_PROCESS_CHOICES)


class LineManagerSerializer(serializers.ModelSerializer):
    """Minimal representation of a line manager (name + id)."""

    class Meta:
        model = Employee
        fields = ['id', 'employee_id', 'full_name']


class OrganisationReferenceSerializer(serializers.ModelSerializer):
    logo = serializers.ImageField(read_only=True)

    class Meta:
        model = Organisation
        fields = ['id', 'name', 'logo', 'is_base']


class EmployeeAssetAllocationSerializer(serializers.ModelSerializer):
    asset_detail = AssetSerializer(source='asset', read_only=True)
    assigned_by_name = serializers.CharField(source='assigned_by.full_name', read_only=True)
    recovered_by_name = serializers.CharField(source='recovered_by.full_name', read_only=True)

    class Meta:
        model = AssetAllocation
        fields = [
            'id',
            'asset',
            'asset_detail',
            'assigned_date',
            'recovered_date',
            'status',
            'notes',
            'assigned_by',
            'assigned_by_name',
            'recovered_by',
            'recovered_by_name',
            'created_at',
        ]
        read_only_fields = [
            'id',
            'asset',
            'asset_detail',
            'assigned_date',
            'recovered_date',
            'status',
            'notes',
            'assigned_by',
            'assigned_by_name',
            'recovered_by',
            'recovered_by_name',
            'created_at',
        ]


class EmployeeLicenseAllocationSerializer(serializers.ModelSerializer):
    license_detail = SoftwareLicenseSerializer(source='license', read_only=True)
    assigned_by_name = serializers.CharField(source='assigned_by.full_name', read_only=True)
    revoked_by_name = serializers.CharField(source='revoked_by.full_name', read_only=True)

    class Meta:
        model = LicenseAllocation
        fields = [
            'id',
            'license',
            'license_detail',
            'assigned_date',
            'revoked_date',
            'status',
            'notes',
            'assigned_by',
            'assigned_by_name',
            'revoked_by',
            'revoked_by_name',
            'created_at',
        ]
        read_only_fields = fields


class EmployeeSerializer(serializers.ModelSerializer):
    line_manager_detail = LineManagerSerializer(source='line_manager', read_only=True)
    core_process_name = serializers.CharField(read_only=True)
    organisations = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Organisation.objects.all(), required=False
    )
    organisation_details = OrganisationReferenceSerializer(source='organisations', many=True, read_only=True)

    class Meta:
        model = Employee
        fields = [
            'id',
            'employee_id',
            'full_name',
            'alias_name',
            'client_email',
            'official_email',
            'contact_number',
            'core_process_code',
            'core_process_name',
            'designation',
            'line_manager',
            'line_manager_detail',
            'organisations',
            'organisation_details',
            'status',
            'date_of_joining',
            'date_of_separation',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'client_email', 'core_process_name', 'created_at', 'updated_at']
        extra_kwargs = {
            'official_email': {'validators': []},
            'contact_number': {'required': False, 'allow_blank': True},
            'line_manager': {'write_only': True, 'required': False, 'allow_null': True},
        }

    def _set_core_process_name(self, validated_data):
        code = validated_data.get('core_process_code', '')
        validated_data['core_process_name'] = CORE_PROCESS_MAP.get(code, '')
        return validated_data

    def validate_official_email(self, value):
        queryset = Employee.objects.filter(official_email__iexact=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError('An employee with this email already exists.')
        return value

    def validate(self, attrs):
        alias_name = attrs.get('alias_name', self.instance.alias_name if self.instance else '')
        # An alias left untouched on an update doesn't need to be re-checked --
        # plenty of existing employees have an alias that was typed in (or
        # picked) before the initials-matching rule existed, and re-running
        # the check on every unrelated edit would block saving their record
        # forever. Only a newly-created or newly-changed alias gets checked.
        alias_changed = not self.instance or alias_name != self.instance.alias_name
        if (alias_name or '').strip() and alias_changed:
            full_name = attrs.get('full_name', self.instance.full_name if self.instance else '')
            try:
                attrs['client_email'] = alias_rules.check_alias(
                    full_name,
                    alias_name,
                    exclude_employee_id=self.instance.pk if self.instance else None,
                )
            except alias_rules.AliasError as exc:
                raise serializers.ValidationError({'alias_name': str(exc)})
        elif not (alias_name or '').strip() and 'alias_name' in attrs:
            attrs['client_email'] = None
        return attrs

    def create(self, validated_data):
        return super().create(self._set_core_process_name(validated_data))

    def update(self, instance, validated_data):
        if 'core_process_code' in validated_data:
            self._set_core_process_name(validated_data)
        return super().update(instance, validated_data)
