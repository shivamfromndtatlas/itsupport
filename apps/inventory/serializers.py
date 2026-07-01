from rest_framework import serializers

from apps.organisations.models import Organisation

from .models import Asset, AssetAttribute, AssetType, AssetTypeAttributeRequirement, SoftwareLicense


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


class AssetTypeAttributeRequirementSerializer(serializers.ModelSerializer):
    asset_type_name = serializers.CharField(source='asset_type.name', read_only=True)
    attribute_name = serializers.CharField(source='attribute.name', read_only=True)
    attribute_field_type = serializers.CharField(source='attribute.field_type', read_only=True)

    class Meta:
        model = AssetTypeAttributeRequirement
        fields = [
            'id',
            'asset_type',
            'asset_type_name',
            'attribute',
            'attribute_name',
            'attribute_field_type',
            'requirement',
            'notes',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'asset_type_name', 'attribute_name', 'attribute_field_type']


class AssetSerializer(serializers.ModelSerializer):
    asset_type_name = serializers.CharField(source='asset_type.name', read_only=True)
    organisation_detail = serializers.SerializerMethodField()
    location_detail = serializers.SerializerMethodField()
    attribute_values_with_names = serializers.SerializerMethodField()
    allocation_state = serializers.SerializerMethodField()
    availability_status = serializers.SerializerMethodField()

    class Meta:
        model = Asset
        fields = [
            'id', 'asset_id', 'organisation', 'organisation_detail', 'location', 'location_detail', 'asset_type', 'asset_type_name',
            'serial_number', 'status', 'purchase_date', 'purchase_cost',
            'warranty_expiry', 'vendor', 'notes', 'attribute_values',
            'attribute_values_with_names',
            'allocation_state',
            'availability_status',
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
            'logo': organisation.logo.url if organisation.logo else '',
            'is_base': organisation.is_base,
        }

    def get_location_detail(self, obj):
        location = obj.location
        if not location:
            return None
        return {
            'id': location.id,
            'name': location.name,
            'organisation_id': location.organisation_id,
            'organisation_name': location.organisation.name if location.organisation_id else None,
            'city': location.city,
            'country': location.country,
        }

    def get_allocation_state(self, obj):
        from apps.allocation.models import AssetAllocation

        allocation = (
            AssetAllocation.objects.select_related('employee', 'assigned_by', 'recovered_by')
            .filter(asset=obj)
            .order_by('-assigned_date', '-created_at')
            .first()
        )
        if not allocation:
            return {
                'status': 'unallocated',
                'label': 'Unallocated',
                'employee_name': '',
                'allocation_id': None,
            }
        return {
            'status': allocation.status,
            'label': 'Active' if allocation.status == 'active' else 'Recovered',
            'employee_name': allocation.employee.full_name if allocation.employee_id else '',
            'allocation_id': allocation.id,
            'assigned_date': allocation.assigned_date,
            'recovered_date': allocation.recovered_date,
        }

    def get_availability_status(self, obj):
        from apps.allocation.models import AssetAllocation

        allocation = (
            AssetAllocation.objects.select_related('employee')
            .filter(asset=obj)
            .order_by('-assigned_date', '-created_at')
            .first()
        )

        attribute_values = obj.attribute_values or {}
        if allocation and allocation.status == 'recovered':
            condition_value = str(attribute_values.get('condition') or '').strip().lower()
            if condition_value in {'good', 'ok', 'okay', 'fair'}:
                return 'In Stock'
            return 'Under Repair'

        raw_value = (
            attribute_values.get('Availability Status')
            or attribute_values.get('availability status')
            or attribute_values.get('10')
            or ''
        )
        normalized = str(raw_value or '').strip().lower()
        if normalized in {'in stock', 'issued', 'under repair', 'retired', 'reserved stock'}:
            return raw_value

        if obj.status == 'assigned':
            return 'Issued'
        if obj.status == 'maintenance':
            return 'Under Repair'
        if obj.status == 'retired':
            return 'Retired'
        return 'Reserved Stock'


class AssetCreateSerializer(serializers.Serializer):
    """
    Accepts asset_type as a string name (get_or_create) so the frontend
    doesn't need to manage AssetType IDs.
    """
    organisation = serializers.PrimaryKeyRelatedField(
        queryset=Organisation.objects.all(), required=False, allow_null=True, default=None
    )
    location = serializers.PrimaryKeyRelatedField(
        queryset=Organisation.objects.none(), required=False, allow_null=True, default=None
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.organisations.models import OrganisationLocation
        self.fields['location'].queryset = OrganisationLocation.objects.select_related('organisation').all()

    def validate(self, attrs):
        organisation = attrs.get('organisation') or getattr(self.instance, 'organisation', None)
        location = attrs.get('location') or getattr(self.instance, 'location', None)
        if location and organisation and location.organisation_id != organisation.id:
            raise serializers.ValidationError({'location': 'Selected location must belong to the chosen organisation.'})

        instance = getattr(self, 'instance', None)
        asset_type_name = attrs.get('asset_type') or (getattr(instance.asset_type, 'name', None) if instance else None)
        if asset_type_name:
            asset_type = AssetType.objects.filter(name=asset_type_name).first()
            if asset_type:
                requirements = AssetTypeAttributeRequirement.objects.select_related('attribute').filter(asset_type=asset_type)
                attribute_values = attrs.get('attribute_values') or {}
                errors = {}
                for requirement in requirements:
                    key_candidates = {str(requirement.attribute.id), requirement.attribute.name}
                    value = None
                    for key in key_candidates:
                        if key in attribute_values and attribute_values.get(key) not in (None, ''):
                            value = attribute_values.get(key)
                            break
                    if requirement.requirement == 'mandatory' and value in (None, ''):
                        errors.setdefault('attribute_values', []).append(
                            f'{requirement.attribute.name} is mandatory for {asset_type.name}.'
                        )
                    if requirement.requirement == 'hidden' and value not in (None, ''):
                        errors.setdefault('attribute_values', []).append(
                            f'{requirement.attribute.name} must be hidden for {asset_type.name}.'
                        )
                if errors:
                    raise serializers.ValidationError(errors)
        return attrs

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
            'logo': organisation.logo.url if organisation.logo else '',
            'is_base': organisation.is_base,
        }

    def create(self, validated_data):
        # Initialise available_seats to match total_seats on creation
        total = validated_data.get('total_seats', 1)
        validated_data.setdefault('available_seats', total)
        return super().create(validated_data)
