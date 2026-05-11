from rest_framework import serializers

from apps.employees.serializers import EmployeeSerializer
from apps.inventory.serializers import AssetSerializer, SoftwareLicenseSerializer

from .models import AssetAllocation, LicenseAllocation


class AssetAllocationSerializer(serializers.ModelSerializer):
    asset_detail = AssetSerializer(source='asset', read_only=True)
    employee_detail = EmployeeSerializer(source='employee', read_only=True)
    assigned_by_name = serializers.CharField(source='assigned_by.full_name', read_only=True)
    recovered_by_name = serializers.CharField(source='recovered_by.full_name', read_only=True)
    qr_code_url = serializers.ImageField(source='qr_code', read_only=True)

    class Meta:
        model = AssetAllocation
        fields = [
            'id',
            'asset',
            'asset_detail',
            'employee',
            'employee_detail',
            'assigned_by',
            'assigned_by_name',
            'assigned_date',
            'recovered_date',
            'recovered_by',
            'recovered_by_name',
            'status',
            'notes',
            'qr_code_url',
            'qr_uuid',
            'created_at',
        ]
        read_only_fields = [
            'id',
            'assigned_by',
            'assigned_by_name',
            'recovered_by',
            'recovered_by_name',
            'status',
            'qr_code_url',
            'qr_uuid',
            'created_at',
        ]
        extra_kwargs = {
            'asset': {'write_only': True},
            'employee': {'write_only': True},
        }


class LicenseAllocationSerializer(serializers.ModelSerializer):
    license_detail = SoftwareLicenseSerializer(source='license', read_only=True)
    employee_detail = EmployeeSerializer(source='employee', read_only=True)
    assigned_by_name = serializers.CharField(source='assigned_by.full_name', read_only=True)
    revoked_by_name = serializers.CharField(source='revoked_by.full_name', read_only=True)

    class Meta:
        model = LicenseAllocation
        fields = [
            'id',
            'license',
            'license_detail',
            'employee',
            'employee_detail',
            'assigned_by',
            'assigned_by_name',
            'assigned_date',
            'revoked_date',
            'revoked_by',
            'revoked_by_name',
            'status',
            'notes',
            'created_at',
        ]
        read_only_fields = [
            'id',
            'assigned_by',
            'assigned_by_name',
            'revoked_by',
            'revoked_by_name',
            'status',
            'created_at',
        ]
        extra_kwargs = {
            'license': {'write_only': True},
            'employee': {'write_only': True},
        }
