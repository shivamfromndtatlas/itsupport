from rest_framework import serializers

from .models import Employee


class LineManagerSerializer(serializers.ModelSerializer):
    """Minimal representation of a line manager (name + id)."""

    class Meta:
        model = Employee
        fields = ['id', 'employee_id', 'full_name']


class EmployeeSerializer(serializers.ModelSerializer):
    line_manager_detail = LineManagerSerializer(source='line_manager', read_only=True)

    class Meta:
        model = Employee
        fields = [
            'id',
            'employee_id',
            'full_name',
            'alias_name',
            'official_email',
            'contact_number',
            'core_process',
            'designation',
            'line_manager',
            'line_manager_detail',
            'is_active',
            'date_of_joining',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {
            'line_manager': {'write_only': True, 'required': False, 'allow_null': True},
        }
