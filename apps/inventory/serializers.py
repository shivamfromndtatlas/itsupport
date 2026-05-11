from rest_framework import serializers

from .models import Asset, AssetAttribute, AssetType, SoftwareLicense


class AssetTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetType
        fields = ['id', 'name', 'asset_type', 'description', 'created_at']
        read_only_fields = ['id', 'created_at']


class AssetAttributeSerializer(serializers.ModelSerializer):
    asset_types = serializers.PrimaryKeyRelatedField(
        many=True, queryset=AssetType.objects.all(), required=False
    )

    class Meta:
        model = AssetAttribute
        fields = ['id', 'name', 'field_type', 'options', 'asset_types', 'is_common', 'created_at']
        read_only_fields = ['id', 'created_at']


class AssetSerializer(serializers.ModelSerializer):
    asset_type_name = serializers.CharField(source='asset_type.name', read_only=True)

    class Meta:
        model = Asset
        fields = [
            'id', 'asset_id', 'asset_type', 'asset_type_name',
            'serial_number', 'status', 'purchase_date', 'purchase_cost',
            'warranty_expiry', 'vendor', 'notes', 'attribute_values',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class AssetCreateSerializer(serializers.Serializer):
    """
    Accepts asset_type as a string name (get_or_create) so the frontend
    doesn't need to manage AssetType IDs.
    """
    asset_type = serializers.CharField(max_length=100)
    asset_id = serializers.CharField(max_length=100)
    serial_number = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')
    vendor = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')
    purchase_date = serializers.DateField(required=False, allow_null=True, default=None)
    purchase_cost = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True, default=None)
    warranty_expiry = serializers.DateField(required=False, allow_null=True, default=None)
    status = serializers.ChoiceField(choices=['available', 'assigned', 'maintenance', 'retired'], default='available')
    notes = serializers.CharField(required=False, allow_blank=True, default='')
    attribute_values = serializers.DictField(required=False, default=dict)

    def create(self, validated_data):
        asset_type_name = validated_data.pop('asset_type')
        asset_type, _ = AssetType.objects.get_or_create(
            name=asset_type_name,
            defaults={'asset_type': 'hardware'},
        )
        return Asset.objects.create(asset_type=asset_type, **validated_data)

    def update(self, instance, validated_data):
        asset_type_name = validated_data.pop('asset_type', None)
        if asset_type_name:
            asset_type, _ = AssetType.objects.get_or_create(
                name=asset_type_name,
                defaults={'asset_type': 'hardware'},
            )
            instance.asset_type = asset_type
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class SoftwareLicenseSerializer(serializers.ModelSerializer):
    used_seats = serializers.SerializerMethodField()

    class Meta:
        model = SoftwareLicense
        fields = [
            'id', 'software_name', 'license_key', 'vendor',
            'total_seats', 'available_seats', 'used_seats',
            'license_type', 'expiry_date', 'purchase_date', 'cost',
            'status', 'attribute_values', 'notes',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'available_seats', 'created_at', 'updated_at']

    def get_used_seats(self, obj):
        return obj.total_seats - obj.available_seats

    def create(self, validated_data):
        # Initialise available_seats to match total_seats on creation
        total = validated_data.get('total_seats', 1)
        validated_data.setdefault('available_seats', total)
        return super().create(validated_data)
