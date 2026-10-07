"""
Dashboard overview: one role-aware request that aggregates the portal's local
data for the home screen. It only reads the database (no calls out to SureMDM,
Trellix, etc.) so it stays fast; live integration figures are fetched by the
frontend per widget.
"""
from datetime import timedelta

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.activity_log.models import ActivityLog
from apps.allocation.models import AssetAllocation
from apps.employees.models import Employee
from apps.integrations.models import (
    DellSupportConnection,
    GoogleWorkspaceConnection,
    SureMDMConnection,
    SynthesiaConnection,
    TeamViewerConnection,
    TrellixConnection,
)
from apps.inventory.models import Asset, SoftwareLicense
from apps.onboarding.models import NewJoinerRequest
from apps.tickets.models import Ticket

TREND_DAYS = 14
ACTIVE_TICKET_STATUSES = ('open', 'in_progress')
PRIORITY_RANK = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}


def _ticket_section(user):
    qs = Ticket.objects.all()
    if user.role == 'employee':
        qs = qs.filter(raised_by=user)

    today = timezone.localdate()
    since = today - timedelta(days=TREND_DAYS - 1)

    status_counts = {key: 0 for key, _ in Ticket.STATUS_CHOICES}
    for row in qs.values('status').annotate(count=Count('id')):
        status_counts[row['status']] = row['count']

    active = qs.filter(status__in=ACTIVE_TICKET_STATUSES)
    priority_counts = {key: 0 for key, _ in Ticket.PRIORITY_CHOICES}
    for row in active.values('priority').annotate(count=Count('id')):
        priority_counts[row['priority']] = row['count']
    category_counts = {key: 0 for key, _ in Ticket.CATEGORY_CHOICES}
    for row in active.values('category').annotate(count=Count('id')):
        category_counts[row['category']] = row['count']

    created_by_day = dict(
        qs.filter(created_at__date__gte=since)
        .annotate(day=TruncDate('created_at'))
        .values_list('day')
        .annotate(count=Count('id'))
    )
    resolved_by_day = dict(
        qs.filter(resolved_at__date__gte=since)
        .annotate(day=TruncDate('resolved_at'))
        .values_list('day')
        .annotate(count=Count('id'))
    )
    trend = []
    for offset in range(TREND_DAYS):
        day = since + timedelta(days=offset)
        trend.append({
            'date': day.isoformat(),
            'created': created_by_day.get(day, 0),
            'resolved': resolved_by_day.get(day, 0),
        })

    recent = sorted(
        active.select_related('raised_by', 'assigned_to')[:50],
        key=lambda t: (PRIORITY_RANK.get(t.priority, 9), -t.created_at.timestamp()),
    )[:6]

    return {
        'status_counts': status_counts,
        'active': sum(status_counts[s] for s in ACTIVE_TICKET_STATUSES),
        'unassigned': active.filter(assigned_to__isnull=True).count(),
        'priority_counts': priority_counts,
        'category_counts': category_counts,
        'trend': trend,
        'recent': [
            {
                'id': t.id,
                'ticket_id': t.ticket_id,
                'title': t.title,
                'priority': t.priority,
                'status': t.status,
                'category': t.category,
                'raised_by': getattr(t.raised_by, 'full_name', '') or getattr(t.raised_by, 'email', ''),
                'assigned_to': (getattr(t.assigned_to, 'full_name', '') or getattr(t.assigned_to, 'email', '')) if t.assigned_to else None,
                'created_at': t.created_at,
            }
            for t in recent
        ],
    }


def _people_section():
    today = timezone.localdate()
    employees = Employee.objects.all()
    status_counts = {key: 0 for key, _ in Employee.STATUS_CHOICES}
    for row in employees.values('status').annotate(count=Count('id')):
        status_counts[row['status']] = row['count']

    upcoming = (
        NewJoinerRequest.objects.exclude(status='rejected')
        .filter(date_of_joining__gte=today, date_of_joining__lte=today + timedelta(days=30))
        .order_by('date_of_joining')[:6]
    )
    return {
        'employees_total': employees.count(),
        'employee_status': status_counts,
        'joined_last_30_days': employees.filter(date_of_joining__gte=today - timedelta(days=30), date_of_joining__lte=today).count(),
        'pending_onboardings': NewJoinerRequest.objects.filter(status='pending').count(),
        'upcoming_joiners': [
            {
                'id': r.id,
                'full_name': r.full_name,
                'designation': r.designation,
                'date_of_joining': r.date_of_joining,
                'status': r.status,
            }
            for r in upcoming
        ],
    }


def _inventory_section():
    today = timezone.localdate()
    assets = Asset.objects.exclude(vendor='SureMDM').exclude(asset_id__startswith='SUREMDM-')

    status_counts = {key: 0 for key, _ in Asset.STATUS_CHOICES}
    for row in assets.values('status').annotate(count=Count('id')):
        status_counts[row['status']] = row['count']

    by_type = [
        {'name': row['asset_type__name'], 'count': row['count'],
         'available': row['available'], 'assigned': row['assigned']}
        for row in assets.values('asset_type__name').annotate(
            count=Count('id'),
            available=Count('id', filter=Q(status='available')),
            assigned=Count('id', filter=Q(status='assigned')),
        ).order_by('-count')
    ]

    # Effective warranty end: the asset's own field, else the date scraped from
    # the manufacturer's support page (Dell / Lenovo lookup).
    warranty = {'expired': 0, 'next_30': 0, 'next_90': 0, 'covered': 0, 'unknown': 0}
    expiring = []
    for asset in assets.exclude(status='retired').select_related('asset_type', 'support_info'):
        expiry = asset.warranty_expiry
        if not expiry:
            support = getattr(asset, 'support_info', None)
            expiry = parse_date(str((support.warranty or {}).get('end_date') or '')) if support else None
        if not expiry:
            warranty['unknown'] += 1
            continue
        days_left = (expiry - today).days
        if days_left < 0:
            warranty['expired'] += 1
        elif days_left <= 30:
            warranty['next_30'] += 1
        elif days_left <= 90:
            warranty['next_90'] += 1
        else:
            warranty['covered'] += 1
        if days_left <= 90:
            expiring.append((expiry, asset, days_left))
    expiring.sort(key=lambda item: (item[2] < 0, item[0] if item[2] >= 0 else -item[0].toordinal()))

    limited = SoftwareLicense.objects.filter(is_unlimited=False)
    seats = limited.aggregate(total=Sum('total_seats'), available=Sum('available_seats'))
    total_seats = seats['total'] or 0
    available_seats = seats['available'] or 0

    recent_allocations = (
        AssetAllocation.objects.select_related('asset__asset_type', 'employee')
        .order_by('-created_at')[:5]
    )

    return {
        'total': assets.count(),
        'status_counts': status_counts,
        'by_type': by_type,
        'warranty': warranty,
        'expiring_soon': [
            {
                'id': a.id,
                'asset_id': a.asset_id,
                'asset_type': a.asset_type.name,
                'serial_number': a.serial_number,
                'warranty_expiry': expiry,
                'days_left': days_left,
            }
            for expiry, a, days_left in expiring[:6]
        ],
        'licenses': {
            'total': SoftwareLicense.objects.count(),
            'total_seats': total_seats,
            'used_seats': total_seats - available_seats,
            'available_seats': available_seats,
            'unlimited': SoftwareLicense.objects.filter(is_unlimited=True).count(),
        },
        'recent_allocations': [
            {
                'id': al.id,
                'asset_id': al.asset.asset_id,
                'asset_pk': al.asset_id,
                'asset_type': al.asset.asset_type.name,
                'employee': al.employee.full_name,
                'employee_id': al.employee.employee_id,
                'status': al.status,
                'date': al.recovered_date if al.status == 'recovered' and al.recovered_date else al.assigned_date,
            }
            for al in recent_allocations
        ],
    }


def _connection_status(key, name, connection):
    if not connection:
        return {'key': key, 'name': name, 'configured': False}
    return {
        'key': key,
        'name': name,
        'configured': True,
        'active': connection.is_active,
        'last_test_status': connection.last_test_status or None,
        'last_tested_at': connection.last_tested_at,
    }


def _integrations_section():
    latest = lambda model: model.objects.order_by('-updated_at').first()  # noqa: E731
    items = [
        _connection_status('suremdm', 'SureMDM', latest(SureMDMConnection)),
        _connection_status('trellix', 'Trellix', latest(TrellixConnection)),
        _connection_status('teamviewer', 'TeamViewer', latest(TeamViewerConnection)),
        _connection_status('synthesia', 'Synthesia', latest(SynthesiaConnection)),
        _connection_status('dell', 'Dell Warranty', latest(DellSupportConnection)),
    ]
    gw = list(GoogleWorkspaceConnection.objects.all())
    gw_item = {'key': 'google_workspace', 'name': 'Google Workspace', 'configured': bool(gw)}
    if gw:
        gw_item.update({
            'active': any(c.is_active for c in gw),
            'domains': len(gw),
            'last_test_status': 'failed' if any(c.last_test_status == 'failed' for c in gw)
            else ('success' if any(c.last_test_status == 'success' for c in gw) else None),
            'last_tested_at': max((c.last_tested_at for c in gw if c.last_tested_at), default=None),
        })
    items.append(gw_item)
    return items


def _activity_section():
    return [
        {
            'id': log.id,
            'action': log.action,
            'user': (getattr(log.user, 'full_name', '') or getattr(log.user, 'email', '')) if log.user else 'System',
            'method': log.method,
            'status_code': log.status_code,
            'created_at': log.created_at,
        }
        for log in ActivityLog.objects.select_related('user').exclude(method='GET').order_by('-created_at')[:8]
    ]


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_overview(request):
    user = request.user
    role = user.role
    payload = {'role': role, 'generated_at': timezone.now(), 'tickets': _ticket_section(user)}

    if role in ('super_admin', 'hr', 'it_specialist'):
        payload['people'] = _people_section()
    if role in ('super_admin', 'it_specialist'):
        payload['inventory'] = _inventory_section()
        payload['integrations'] = _integrations_section()
    if role == 'super_admin':
        payload['activity'] = _activity_section()

    return Response(payload)
