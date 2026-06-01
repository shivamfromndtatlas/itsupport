from rest_framework import serializers
from urllib.parse import urlparse

from .models import SureMDMConnection


class SureMDMConnectionSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    api_key = serializers.CharField(write_only=True, required=False, allow_blank=True)
    has_password = serializers.SerializerMethodField()
    has_api_key = serializers.SerializerMethodField()

    class Meta:
        model = SureMDMConnection
        fields = [
            'id',
            'base_url',
            'username',
            'password',
            'api_key',
            'has_password',
            'has_api_key',
            'is_active',
            'last_tested_at',
            'last_test_status',
            'last_test_message',
            'last_synced_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'has_password',
            'has_api_key',
            'last_tested_at',
            'last_test_status',
            'last_test_message',
            'last_synced_at',
            'created_at',
            'updated_at',
        ]

    def get_has_password(self, obj):
        return bool(obj.password)

    def get_has_api_key(self, obj):
        return bool(obj.api_key)

    def validate_base_url(self, value):
        parsed = urlparse(value)
        if not parsed.scheme or not parsed.netloc:
            raise serializers.ValidationError('Enter a valid SureMDM URL.')

        base_url = f'{parsed.scheme}://{parsed.netloc}'
        if parsed.path.rstrip('/').endswith('/api'):
            return value.rstrip('/')
        return f'{base_url}/api'

    def update(self, instance, validated_data):
        if validated_data.get('password') == '':
            validated_data.pop('password')
        if validated_data.get('api_key') == '':
            validated_data.pop('api_key')
        return super().update(instance, validated_data)
