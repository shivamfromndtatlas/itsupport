from rest_framework import serializers

from apps.organisations.models import Organisation
from apps.employees.models import Employee


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

    def validate_new_members(self, value):
        for member in value:
            if 'employee_id' not in member or 'full_name' not in member or 'official_email' not in member:
                raise serializers.ValidationError('New members must include employee_id, full_name, and official_email.')
        return value
