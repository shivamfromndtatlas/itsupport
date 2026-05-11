from rest_framework import serializers

from .models import SOP, SOPCategory, SOPChecklistItem, SOPExecution, SOPStep, SOPStepCompletion


class SOPCategorySerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)

    class Meta:
        model = SOPCategory
        fields = ['id', 'name', 'description', 'created_by', 'created_by_name', 'created_at']
        read_only_fields = ['id', 'created_by', 'created_by_name', 'created_at']


class SOPChecklistItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = SOPChecklistItem
        fields = ['id', 'item_text', 'is_required', 'order']
        read_only_fields = ['id']


class SOPStepSerializer(serializers.ModelSerializer):
    # Expose step_type as "type" to match the frontend field name
    type = serializers.CharField(source='step_type', read_only=True)
    # Return checklist items as plain strings instead of nested objects
    checklist_items = serializers.SerializerMethodField()

    class Meta:
        model = SOPStep
        fields = [
            'id', 'sop', 'step_number', 'title', 'description',
            'type', 'is_required', 'responsible_role', 'checklist_items',
        ]
        read_only_fields = ['id']

    def get_checklist_items(self, obj):
        return [item.item_text for item in obj.checklist_items.all()]


class SOPSerializer(serializers.ModelSerializer):
    steps = SOPStepSerializer(many=True, read_only=True)
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = SOP
        fields = [
            'id', 'name', 'description', 'category', 'category_name',
            'is_active', 'created_by', 'created_by_name',
            'created_at', 'updated_at', 'steps',
        ]
        read_only_fields = ['id', 'created_by', 'created_by_name', 'created_at', 'updated_at']


# ── Writable serializers for SOP creation ──────────────────────────────────

class SOPStepCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=300)
    description = serializers.CharField(required=False, allow_blank=True, default='')
    type = serializers.CharField(required=False, default='manual')
    checklist_items = serializers.ListField(
        child=serializers.CharField(allow_blank=True),
        required=False,
        default=list,
    )


class SOPCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    category = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True, default='')
    steps = SOPStepCreateSerializer(many=True, required=False, default=list)

    def create(self, validated_data):
        user = self.context['request'].user

        category, _ = SOPCategory.objects.get_or_create(
            name=validated_data['category'],
            defaults={'created_by': user},
        )

        sop = SOP.objects.create(
            name=validated_data['name'],
            description=validated_data.get('description', ''),
            category=category,
            created_by=user,
        )

        for idx, step_data in enumerate(validated_data.get('steps', []), start=1):
            step = SOPStep.objects.create(
                sop=sop,
                step_number=idx,
                title=step_data['title'],
                description=step_data.get('description', ''),
                step_type=step_data.get('type', 'manual'),
            )
            for order, item_text in enumerate(step_data.get('checklist_items', [])):
                if item_text.strip():
                    SOPChecklistItem.objects.create(step=step, item_text=item_text, order=order)

        return sop


# ── Execution serializers ───────────────────────────────────────────────────

class SOPStepCompletionSerializer(serializers.ModelSerializer):
    completed_by_name = serializers.CharField(source='completed_by.full_name', read_only=True)
    step_title = serializers.CharField(source='step.title', read_only=True)

    class Meta:
        model = SOPStepCompletion
        fields = [
            'id', 'execution', 'step', 'step_title',
            'completed_by', 'completed_by_name',
            'completed_at', 'notes', 'checklist_data',
        ]
        read_only_fields = ['id', 'completed_by', 'completed_by_name', 'completed_at']


class SOPExecutionSerializer(serializers.ModelSerializer):
    step_completions = SOPStepCompletionSerializer(many=True, read_only=True)
    started_by_name = serializers.CharField(source='started_by.full_name', read_only=True)
    sop_name = serializers.CharField(source='sop.name', read_only=True)

    class Meta:
        model = SOPExecution
        fields = [
            'id', 'sop', 'sop_name', 'reference_type', 'reference_id',
            'current_step', 'status', 'started_by', 'started_by_name',
            'started_at', 'completed_at', 'step_completions',
        ]
        read_only_fields = [
            'id', 'current_step', 'started_by', 'started_by_name',
            'started_at', 'completed_at',
        ]
