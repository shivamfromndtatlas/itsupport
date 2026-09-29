import json
import re

from cryptography.hazmat.primitives import serialization
from django.utils import timezone
from rest_framework import serializers
from urllib.parse import urlparse

from .models import (
    DellSupportConnection,
    GoogleWorkspaceConnection,
    SureMDMConnection,
    SynthesiaConnection,
    SynthesiaInvoice,
    TeamViewerConnection,
    TrellixConnection,
)


DOMAIN_PATTERN = re.compile(r'^(?=.{4,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$')


class GoogleWorkspaceConnectionSerializer(serializers.ModelSerializer):
    service_account_json = serializers.CharField(write_only=True, required=False, allow_blank=True)
    has_service_account_key = serializers.SerializerMethodField()

    class Meta:
        model = GoogleWorkspaceConnection
        fields = [
            'id',
            'domain',
            'label',
            'admin_email',
            'service_account_json',
            'has_service_account_key',
            'service_account_email',
            'service_account_client_id',
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
            'has_service_account_key',
            'service_account_email',
            'service_account_client_id',
            'last_tested_at',
            'last_test_status',
            'last_test_message',
            'last_synced_at',
            'created_at',
            'updated_at',
        ]

    def get_has_service_account_key(self, obj):
        return bool(obj.service_account_json)

    def validate_domain(self, value):
        domain = value.strip().lower()
        if not DOMAIN_PATTERN.match(domain):
            raise serializers.ValidationError('Enter a domain like example.com (no https:// or @).')
        return domain

    def validate_service_account_json(self, value):
        if not value.strip():
            return ''
        try:
            info = json.loads(value)
        except ValueError:
            raise serializers.ValidationError('This is not valid JSON. Paste the full contents of the key file.')
        if not isinstance(info, dict) or info.get('type') != 'service_account':
            raise serializers.ValidationError('This is not a service account key (its "type" must be "service_account").')
        if not info.get('client_email') or not info.get('private_key'):
            raise serializers.ValidationError('The key is missing "client_email" or "private_key".')
        try:
            serialization.load_pem_private_key(info['private_key'].encode('utf-8'), password=None)
        except (ValueError, TypeError):
            raise serializers.ValidationError('The private key in this file is malformed or truncated.')
        # Keep only what auth and the setup screen need, so nothing else in an
        # uploaded file (project id, key id, ...) gets stored.
        return json.dumps({
            'type': 'service_account',
            'client_email': info['client_email'],
            'client_id': str(info.get('client_id') or ''),
            'private_key': info['private_key'],
        })

    def validate(self, attrs):
        if not self.instance and not attrs.get('service_account_json'):
            raise serializers.ValidationError({'service_account_json': 'A service account key is required.'})
        return attrs

    def _apply_key(self, validated_data):
        key = validated_data.get('service_account_json')
        if key:
            info = json.loads(key)
            validated_data['service_account_email'] = info['client_email']
            validated_data['service_account_client_id'] = info['client_id']
        else:
            # Blank on edit means "keep the saved key", like the other secret fields.
            validated_data.pop('service_account_json', None)

    def create(self, validated_data):
        self._apply_key(validated_data)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        self._apply_key(validated_data)
        return super().update(instance, validated_data)


class DellSupportConnectionSerializer(serializers.ModelSerializer):
    client_secret = serializers.CharField(write_only=True, required=False, allow_blank=True)
    has_client_secret = serializers.SerializerMethodField()

    class Meta:
        model = DellSupportConnection
        fields = [
            'id',
            'base_url',
            'client_id',
            'client_secret',
            'has_client_secret',
            'is_active',
            'last_tested_at',
            'last_test_status',
            'last_test_message',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'has_client_secret',
            'last_tested_at',
            'last_test_status',
            'last_test_message',
            'created_at',
            'updated_at',
        ]

    def get_has_client_secret(self, obj):
        return bool(obj.client_secret)

    def validate_base_url(self, value):
        parsed = urlparse(value)
        if not parsed.scheme or not parsed.netloc:
            raise serializers.ValidationError('Enter a valid Dell API gateway URL.')
        return f'{parsed.scheme}://{parsed.netloc}'

    def update(self, instance, validated_data):
        if validated_data.get('client_secret') == '':
            validated_data.pop('client_secret')
        # Any credential change invalidates the cached token.
        if 'client_secret' in validated_data or 'client_id' in validated_data or 'base_url' in validated_data:
            validated_data['access_token'] = ''
            validated_data['token_expires_at'] = None
        return super().update(instance, validated_data)


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
            'credits_used_estimated',
            'credits_used_synced_at',
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
            'credits_used_estimated',
            'credits_used_synced_at',
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
