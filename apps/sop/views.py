from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.users.permissions import IsITSpecialistOrSuperAdmin

from .models import SOP, SOPCategory, SOPChecklistItem, SOPExecution, SOPStep, SOPStepCompletion
from .serializers import (
    SOPCategorySerializer,
    SOPCreateSerializer,
    SOPExecutionSerializer,
    SOPSerializer,
    SOPStepCompletionSerializer,
    SOPStepSerializer,
)


class SOPCategoryViewSet(viewsets.ModelViewSet):
    """
    CRUD for SOP categories.
    Write access: IT specialist or super_admin.
    Read access: all authenticated users.
    """

    queryset = SOPCategory.objects.select_related('created_by').all()
    serializer_class = SOPCategorySerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsITSpecialistOrSuperAdmin()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class SOPViewSet(viewsets.ModelViewSet):
    """
    CRUD for SOPs with nested steps.
    Write access: IT specialist or super_admin.
    Read access: all authenticated users.
    """

    queryset = SOP.objects.select_related('category', 'created_by').prefetch_related(
        'steps__checklist_items'
    ).all()

    def get_serializer_class(self):
        if self.action == 'create':
            return SOPCreateSerializer
        return SOPSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy', 'execute'):
            return [IsITSpecialistOrSuperAdmin()]
        return [IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        serializer = SOPCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        sop = serializer.save()
        return Response(SOPSerializer(sop).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='execute')
    def execute(self, request, pk=None):
        sop = self.get_object()
        execution = SOPExecution.objects.create(sop=sop, started_by=request.user)
        return Response(
            {'id': execution.id, 'status': execution.status},
            status=status.HTTP_201_CREATED,
        )


class SOPStepViewSet(viewsets.ModelViewSet):
    """
    CRUD for individual SOP steps (with nested checklist items).
    Write access: IT specialist or super_admin.
    """

    queryset = SOPStep.objects.prefetch_related('checklist_items').all()
    serializer_class = SOPStepSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsITSpecialistOrSuperAdmin()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = super().get_queryset()
        sop_id = self.request.query_params.get('sop')
        if sop_id:
            qs = qs.filter(sop_id=sop_id)
        return qs


class SOPChecklistItemViewSet(viewsets.ModelViewSet):
    """CRUD for checklist items within a step."""

    queryset = SOPChecklistItem.objects.all()

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsITSpecialistOrSuperAdmin()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        from .serializers import SOPChecklistItemSerializer
        return SOPChecklistItemSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        step_id = self.request.query_params.get('step')
        if step_id:
            qs = qs.filter(step_id=step_id)
        return qs


class SOPExecutionViewSet(viewsets.ModelViewSet):
    """
    Manage SOP executions.
    Any authenticated user can start an execution.
    complete_step action marks a specific step done and advances current_step.
    """

    queryset = SOPExecution.objects.select_related('sop', 'started_by').prefetch_related(
        'step_completions__step',
        'step_completions__completed_by',
    ).all()
    serializer_class = SOPExecutionSerializer

    def get_permissions(self):
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(started_by=self.request.user)

    @action(detail=True, methods=['post'], url_path='complete_step')
    def complete_step(self, request, pk=None):
        """
        Mark a step as complete within this execution.
        Body: { "step": <step_id>, "notes": "...", "checklist_data": {...} }
        Advances execution.current_step and marks execution completed when all
        required steps are done.
        """
        execution = self.get_object()

        if execution.status != 'in_progress':
            return Response(
                {'detail': f'Execution is already {execution.status}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        step_id = request.data.get('step')
        if not step_id:
            return Response(
                {'detail': '`step` field is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            step = SOPStep.objects.get(pk=step_id, sop=execution.sop)
        except SOPStep.DoesNotExist:
            return Response(
                {'detail': 'Step not found in this SOP.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if SOPStepCompletion.objects.filter(execution=execution, step=step).exists():
            return Response(
                {'detail': 'This step has already been completed.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        completion = SOPStepCompletion.objects.create(
            execution=execution,
            step=step,
            completed_by=request.user,
            notes=request.data.get('notes', ''),
            checklist_data=request.data.get('checklist_data', {}),
        )

        # Advance current_step pointer
        next_step_number = step.step_number + 1
        execution.current_step = next_step_number

        # Check if all required steps are now completed
        required_steps = SOPStep.objects.filter(sop=execution.sop, is_required=True)
        completed_step_ids = set(
            SOPStepCompletion.objects.filter(execution=execution).values_list('step_id', flat=True)
        )
        all_required_done = all(s.pk in completed_step_ids for s in required_steps)

        if all_required_done:
            execution.status = 'completed'
            execution.completed_at = timezone.now()

        execution.save()

        return Response(
            {
                'detail': 'Step completed.',
                'completion': SOPStepCompletionSerializer(completion).data,
                'execution_status': execution.status,
                'current_step': execution.current_step,
            },
            status=status.HTTP_200_OK,
        )
