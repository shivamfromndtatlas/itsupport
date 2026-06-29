from rest_framework import serializers

from apps.organisations.models import Organisation

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
    organisation_detail = serializers.SerializerMethodField()
    attribute_values_with_names = serializers.SerializerMethodField()

    class Meta:
        model = Asset
        fields = [
            'id', 'asset_id', 'organisation', 'organisation_detail', 'asset_type', 'asset_type_name',
            'serial_number', 'status', 'purchase_date', 'purchase_cost',
            'warranty_expiry', 'vendor', 'notes', 'attribute_values',
            'attribute_values_with_names',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_attribute_values_with_names(self, obj):
        """
        Returns attribute_values with both numeric IDs and attribute names as keys
        for easier access in the frontend.
        """
        from apps.inventory.models import AssetAttribute
        
        result = dict(obj.attribute_values or {})
        
        # Get all attributes - both linked to asset type and common attributes
        try:
            if obj.asset_type:
                # Get attributes linked to this asset type
                linked_attrs = obj.asset_type.attributes.all()
                # Also get common attributes
                common_attrs = AssetAttribute.objects.filter(is_common=True)
                # Combine them
                all_attrs = set(linked_attrs) | set(common_attrs)
                
                for attr in all_attrs:
                    # Try both integer and string keys since JSON can have either
                    attr_id_int = attr.id
                    attr_id_str = str(attr.id)
                    
                    # Check for the attribute value using both int and string keys
                    if attr_id_int in result:
                        result[attr.name] = result[attr_id_int]
                    elif attr_id_str in result:
                        result[attr.name] = result[attr_id_str]
        except Exception:
            pass
        
        return result

    def get_organisation_detail(self, obj):
        organisation = obj.organisation
        if not organisation:
            return None
        return {
            'id': organisation.id,
            'name': organisation.name,
            'is_base': organisation.is_base,
        }


class AssetCreateSerializer(serializers.Serializer):
    """
    Accepts asset_type as a string name (get_or_create) so the frontend
    doesn't need to manage AssetType IDs.
    """
    organisation = serializers.PrimaryKeyRelatedField(
        queryset=Organisation.objects.all(), required=False, allow_null=True, default=None
    )
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
    organisation_detail = serializers.SerializerMethodField()

    class Meta:
        model = SoftwareLicense
        fields = [
            'id', 'software_name', 'organisation', 'organisation_detail', 'license_key', 'vendor',
            'total_seats', 'available_seats', 'used_seats',
            'license_type', 'expiry_date', 'purchase_date', 'cost',
            'status', 'attribute_values', 'notes',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'available_seats', 'created_at', 'updated_at']

    def get_used_seats(self, obj):
        return obj.total_seats - obj.available_seats

    def get_organisation_detail(self, obj):
        organisation = obj.organisation
        if not organisation:
            return None
        return {
            'id': organisation.id,
            'name': organisation.name,
            'is_base': organisation.is_base,
        }

    def create(self, validated_data):
        # Initialise available_seats to match total_seats on creation
        total = validated_data.get('total_seats', 1)
        validated_data.setdefault('available_seats', total)
        return super().create(validated_data)
