from rest_framework import serializers

from .models import NewJoinerRequest


class NewJoinerRequestSerializer(serializers.ModelSerializer):
    submitted_by_name = serializers.CharField(
        source='submitted_by.full_name', read_only=True
    )
    confirmed_by_name = serializers.CharField(
        source='confirmed_by.full_name', read_only=True
    )

    class Meta:
        model = NewJoinerRequest
        fields = [
            'id',
            'full_name',
            'employee_id',
            'contact_number',
            'personal_email',
            'complete_address',
            'designation',
            'core_process',
            'alias_name',
            'date_of_joining',
            'line_manager',
            'status',
            'submitted_by',
            'submitted_by_name',
            'confirmed_by',
            'confirmed_by_name',
            'confirmed_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'status',
            'submitted_by',
            'submitted_by_name',
            'confirmed_by',
            'confirmed_by_name',
            'confirmed_at',
            'created_at',
            'updated_at',
        ]
