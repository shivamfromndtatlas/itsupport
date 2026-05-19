from rest_framework import serializers

from .models import Employee

CORE_PROCESS_MAP = dict(Employee.CORE_PROCESS_CHOICES)


class LineManagerSerializer(serializers.ModelSerializer):
    """Minimal representation of a line manager (name + id)."""

    class Meta:
        model = Employee
        fields = ['id', 'employee_id', 'full_name']


class EmployeeSerializer(serializers.ModelSerializer):
    line_manager_detail = LineManagerSerializer(source='line_manager', read_only=True)
    core_process_name = serializers.CharField(read_only=True)

    class Meta:
        model = Employee
        fields = [
            'id',
            'employee_id',
            'full_name',
            'alias_name',
            'official_email',
            'contact_number',
            'core_process_code',
            'core_process_name',
            'designation',
            'line_manager',
            'line_manager_detail',
            'status',
            'date_of_joining',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'core_process_name', 'created_at', 'updated_at']
        extra_kwargs = {
            'line_manager': {'write_only': True, 'required': False, 'allow_null': True},
        }

    def _set_core_process_name(self, validated_data):
        code = validated_data.get('core_process_code', '')
        validated_data['core_process_name'] = CORE_PROCESS_MAP.get(code, '')
        return validated_data

    def create(self, validated_data):
        return super().create(self._set_core_process_name(validated_data))

    def update(self, instance, validated_data):
        if 'core_process_code' in validated_data:
            self._set_core_process_name(validated_data)
        return super().update(instance, validated_data)
