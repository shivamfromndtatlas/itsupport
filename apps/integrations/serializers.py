from django.utils import timezone
from rest_framework import serializers
from urllib.parse import urlparse

from .models import SureMDMConnection, SynthesiaConnection, SynthesiaInvoice, TeamViewerConnection, TrellixConnection


class TeamViewerConnectionSerializer(serializers.ModelSerializer):
    api_token = serializers.CharField(write_only=True, required=False, allow_blank=True)
    has_api_token = serializers.SerializerMethodField()

    class Meta:
        model = TeamViewerConnection
        fields = [
            'id',
            'name',
            'base_url',
            'api_token',
            'has_api_token',
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
            'has_api_token',
            'last_tested_at',
            'last_test_status',
            'last_test_message',
            'last_synced_at',
            'created_at',
            'updated_at',
        ]

    def get_has_api_token(self, obj):
        return bool(obj.api_token)

    def validate_base_url(self, value):
        parsed = urlparse(value)
        if not parsed.scheme or not parsed.netloc:
            raise serializers.ValidationError('Enter a valid TeamViewer API URL.')
        return value.rstrip('/')

    def update(self, instance, validated_data):
        if validated_data.get('api_token') == '':
            validated_data.pop('api_token')
        return super().update(instance, validated_data)


class SynthesiaConnectionSerializer(serializers.ModelSerializer):
    api_key = serializers.CharField(write_only=True, required=False, allow_blank=True)
    has_api_key = serializers.SerializerMethodField()

    class Meta:
        model = SynthesiaConnection
        fields = [
            'id',
            'name',
            'base_url',
            'api_key',
            'has_api_key',
            'is_active',
            'plan_name',
            'billing_period',
            'credit_allowance',
            'billing_cycle_renews_on',
            'credits_used_override',
            'credits_used_override_at',
            'last_tested_at',
            'last_test_status',
            'last_test_message',
            'last_synced_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'has_api_key',
            'credits_used_override_at',
            'last_tested_at',
            'last_test_status',
            'last_test_message',
            'last_synced_at',
            'created_at',
            'updated_at',
        ]

    def get_has_api_key(self, obj):
        return bool(obj.api_key)

    def validate_base_url(self, value):
        parsed = urlparse(value)
        if not parsed.scheme or not parsed.netloc:
            raise serializers.ValidationError('Enter a valid Synthesia API URL.')
        return value.rstrip('/')

    def update(self, instance, validated_data):
        if validated_data.get('api_key') == '':
            validated_data.pop('api_key')
        if 'credits_used_override' in validated_data and validated_data['credits_used_override'] != instance.credits_used_override:
            validated_data['credits_used_override_at'] = timezone.now()
        return super().update(instance, validated_data)


class SynthesiaInvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = SynthesiaInvoice
        fields = [
            'id',
            'payment_date',
            'amount',
            'currency',
            'invoice_number',
            'invoice_file',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def validate_invoice_file(self, value):
        if value and not value.name.lower().endswith('.pdf'):
            raise serializers.ValidationError('Invoice attachment must be a PDF file.')
        return value


class TrellixConnectionSerializer(serializers.ModelSerializer):
    client_secret = serializers.CharField(write_only=True, required=False, allow_blank=True)
    api_key = serializers.CharField(write_only=True, required=False, allow_blank=True)
    has_client_secret = serializers.SerializerMethodField()
    has_api_key = serializers.SerializerMethodField()

    class Meta:
        model = TrellixConnection
        fields = [
            'id',
            'base_url',
            'auth_url',
            'tenant_name',
            'tenant_id',
            'client_id',
            'client_secret',
            'api_key',
            'scope',
            'has_client_secret',
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
            'has_client_secret',
            'has_api_key',
            'last_tested_at',
            'last_test_status',
            'last_test_message',
            'last_synced_at',
            'created_at',
            'updated_at',
        ]

    def get_has_client_secret(self, obj):
        return bool(obj.client_secret)

    def get_has_api_key(self, obj):
        return bool(obj.api_key)

    def validate_base_url(self, value):
        parsed = urlparse(value)
        if not parsed.scheme or not parsed.netloc:
            raise serializers.ValidationError('Enter a valid Trellix API URL.')
        return value.rstrip('/')

    def validate_auth_url(self, value):
        parsed = urlparse(value)
        if not parsed.scheme or not parsed.netloc:
            raise serializers.ValidationError('Enter a valid Trellix token URL.')
        return value

    def update(self, instance, validated_data):
        if validated_data.get('client_secret') == '':
            validated_data.pop('client_secret')
        if validated_data.get('api_key') == '':
            validated_data.pop('api_key')
        return super().update(instance, validated_data)


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
