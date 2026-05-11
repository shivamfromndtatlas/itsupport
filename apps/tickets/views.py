from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.users.permissions import IsITOrHROrSuperAdmin

from .models import Ticket, TicketComment
from .serializers import TicketCommentSerializer, TicketSerializer


class TicketViewSet(viewsets.ModelViewSet):
    """
    Ticket management.
    - Employees see only tickets they raised.
    - IT specialists, HR, and super_admin see all tickets.
    - Any authenticated user can create a ticket.
    - Status transitions and assignment are available to IT/HR/super_admin.
    """

    serializer_class = TicketSerializer

    def get_permissions(self):
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        qs = Ticket.objects.select_related(
            'raised_by', 'assigned_to', 'employee'
        ).prefetch_related('comments__commented_by').all()

        if user.role == 'employee':
            qs = qs.filter(raised_by=user)

        # Allow filtering by status / category / priority via query params
        status_param = self.request.query_params.get('status')
        category_param = self.request.query_params.get('category')
        priority_param = self.request.query_params.get('priority')

        if status_param:
            qs = qs.filter(status=status_param)
        if category_param:
            qs = qs.filter(category=category_param)
        if priority_param:
            qs = qs.filter(priority=priority_param)

        return qs

    def perform_create(self, serializer):
        serializer.save(raised_by=self.request.user)

    @action(detail=True, methods=['get', 'post'], url_path='comments')
    def comments(self, request, pk=None):
        ticket = self.get_object()
        if request.method == 'GET':
            qs = TicketComment.objects.filter(ticket=ticket).select_related('commented_by')
            return Response(TicketCommentSerializer(qs, many=True).data)
        serializer = TicketCommentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(ticket=ticket, commented_by=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=['post'],
        url_path='assign',
        permission_classes=[IsITOrHROrSuperAdmin],
    )
    def assign(self, request, pk=None):
        """Assign a ticket to a user (IT/HR/super_admin only)."""
        ticket = self.get_object()
        assigned_to_id = request.data.get('assigned_to')
        if not assigned_to_id:
            return Response(
                {'detail': '`assigned_to` field is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from apps.users.models import User
        try:
            assignee = User.objects.get(pk=assigned_to_id)
        except User.DoesNotExist:
            return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        ticket.assigned_to = assignee
        if ticket.status == 'open':
            ticket.status = 'in_progress'
        ticket.save()
        return Response(TicketSerializer(ticket, context={'request': request}).data)

    @action(
        detail=True,
        methods=['post'],
        url_path='resolve',
        permission_classes=[IsITOrHROrSuperAdmin],
    )
    def resolve(self, request, pk=None):
        """Mark a ticket as resolved (IT/HR/super_admin only)."""
        ticket = self.get_object()
        if ticket.status in ('resolved', 'closed'):
            return Response(
                {'detail': f'Ticket is already {ticket.status}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        ticket.status = 'resolved'
        ticket.resolved_at = timezone.now()
        ticket.save()
        return Response(TicketSerializer(ticket, context={'request': request}).data)

    @action(
        detail=True,
        methods=['post'],
        url_path='close',
        permission_classes=[IsITOrHROrSuperAdmin],
    )
    def close(self, request, pk=None):
        """Close a resolved ticket (IT/HR/super_admin only)."""
        ticket = self.get_object()
        if ticket.status == 'closed':
            return Response(
                {'detail': 'Ticket is already closed.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        ticket.status = 'closed'
        ticket.save()
        return Response(TicketSerializer(ticket, context={'request': request}).data)


class TicketCommentViewSet(viewsets.ModelViewSet):
    """
    Comments on tickets.
    - Any authenticated user can add/view comments on tickets they can see.
    - Edit/delete: only the comment author or IT/HR/super_admin.
    """

    serializer_class = TicketCommentSerializer

    def get_permissions(self):
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        qs = TicketComment.objects.select_related('ticket', 'commented_by').all()

        # Employees only see comments on their own tickets
        if user.role == 'employee':
            qs = qs.filter(ticket__raised_by=user)

        ticket_id = self.request.query_params.get('ticket')
        if ticket_id:
            qs = qs.filter(ticket_id=ticket_id)

        return qs

    def perform_create(self, serializer):
        serializer.save(commented_by=self.request.user)

    def update(self, request, *args, **kwargs):
        comment = self.get_object()
        user = request.user
        if comment.commented_by != user and user.role not in ('it_specialist', 'hr', 'super_admin'):
            return Response(
                {'detail': 'You do not have permission to edit this comment.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        comment = self.get_object()
        user = request.user
        if comment.commented_by != user and user.role not in ('it_specialist', 'hr', 'super_admin'):
            return Response(
                {'detail': 'You do not have permission to delete this comment.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().destroy(request, *args, **kwargs)
