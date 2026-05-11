from rest_framework import serializers

from .models import Ticket, TicketComment


class TicketCommentSerializer(serializers.ModelSerializer):
    commented_by_name = serializers.CharField(source='commented_by.full_name', read_only=True)

    class Meta:
        model = TicketComment
        fields = [
            'id',
            'ticket',
            'commented_by',
            'commented_by_name',
            'comment',
            'created_at',
        ]
        read_only_fields = ['id', 'commented_by', 'commented_by_name', 'created_at']


class TicketSerializer(serializers.ModelSerializer):
    comments = TicketCommentSerializer(many=True, read_only=True)
    raised_by_name = serializers.CharField(source='raised_by.full_name', read_only=True)
    assigned_to_name = serializers.CharField(source='assigned_to.full_name', read_only=True)

    class Meta:
        model = Ticket
        fields = [
            'id',
            'ticket_id',
            'title',
            'description',
            'category',
            'priority',
            'status',
            'raised_by',
            'raised_by_name',
            'assigned_to',
            'assigned_to_name',
            'employee',
            'resolved_at',
            'created_at',
            'updated_at',
            'comments',
        ]
        read_only_fields = [
            'id',
            'ticket_id',
            'raised_by',
            'raised_by_name',
            'resolved_at',
            'created_at',
            'updated_at',
        ]
