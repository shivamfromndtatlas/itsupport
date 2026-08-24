from rest_framework import serializers

from apps.employees import alias_rules

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
        extra_kwargs = {
            'complete_address': {'required': False, 'allow_blank': True},
            'line_manager': {'required': False, 'allow_blank': True},
            'core_process': {'required': False, 'allow_blank': True},
        }

    def validate(self, attrs):
        alias_name = attrs.get('alias_name', self.instance.alias_name if self.instance else '')
        if (alias_name or '').strip():
            full_name = attrs.get('full_name', self.instance.full_name if self.instance else '')
            try:
                alias_rules.check_alias(full_name, alias_name)
            except alias_rules.AliasError as exc:
                raise serializers.ValidationError({'alias_name': str(exc)})
        return attrs
