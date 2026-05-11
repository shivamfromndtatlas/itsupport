from django.db.models import Count, Sum
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.users.permissions import IsITOrHROrSuperAdmin, IsITSpecialistOrSuperAdmin

from .models import Asset, AssetAttribute, AssetType, SoftwareLicense
from .serializers import (
    AssetAttributeSerializer,
    AssetCreateSerializer,
    AssetSerializer,
    AssetTypeSerializer,
    SoftwareLicenseSerializer,
)


class AssetTypeViewSet(viewsets.ModelViewSet):
    """
    CRUD for asset types.
    Write: IT specialist or super_admin. Read: all authenticated.
    """

    queryset = AssetType.objects.all()
    serializer_class = AssetTypeSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsITSpecialistOrSuperAdmin()]
        return [IsAuthenticated()]


class AssetAttributeViewSet(viewsets.ModelViewSet):
    """
    CRUD for asset attributes.
    Write: IT specialist or super_admin. Read: all authenticated.
    """

    queryset = AssetAttribute.objects.prefetch_related('asset_types').all()
    serializer_class = AssetAttributeSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsITSpecialistOrSuperAdmin()]
        return [IsAuthenticated()]


class AssetViewSet(viewsets.ModelViewSet):
    """
    CRUD for assets.
    Write: IT specialist or super_admin. Read: all authenticated.
    dashboard_stats action: IT/HR/super_admin.
    """

    queryset = Asset.objects.select_related('asset_type').all()

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return AssetCreateSerializer
        return AssetSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsITSpecialistOrSuperAdmin()]
        if self.action == 'dashboard_stats':
            return [IsITOrHROrSuperAdmin()]
        return [IsAuthenticated()]

    @action(detail=False, methods=['get'], url_path='dashboard-stats')
    def dashboard_stats(self, request):
        """
        Returns a summary of asset counts by status and type,
        top 5 asset types, and a software licence seat summary.
        """
        assets_qs = Asset.objects.all()
        total = assets_qs.count()

        status_counts = {
            'available': assets_qs.filter(status='available').count(),
            'assigned': assets_qs.filter(status='assigned').count(),
            'maintenance': assets_qs.filter(status='maintenance').count(),
            'retired': assets_qs.filter(status='retired').count(),
        }

        # Count per asset type (name)
        assets_by_type = (
            assets_qs.values('asset_type__name')
            .annotate(count=Count('id'))
            .order_by('asset_type__name')
        )
        assets_by_type_list = [
            {'asset_type': row['asset_type__name'], 'count': row['count']}
            for row in assets_by_type
        ]

        top_5_types = sorted(assets_by_type_list, key=lambda x: x['count'], reverse=True)[:5]

        # Software licence summary
        licenses_qs = SoftwareLicense.objects.all()
        total_seats = licenses_qs.aggregate(total=Sum('total_seats'))['total'] or 0
        available_seats = licenses_qs.aggregate(avail=Sum('available_seats'))['avail'] or 0
        used_seats = total_seats - available_seats

        return Response(
            {
                'total_assets': total,
                'status_counts': status_counts,
                'assets_by_type': assets_by_type_list,
                'top_5_asset_types': top_5_types,
                'software_licenses': {
                    'total_licenses': licenses_qs.count(),
                    'total_seats': total_seats,
                    'used_seats': used_seats,
                    'available_seats': available_seats,
                },
            }
        )


class SoftwareLicenseViewSet(viewsets.ModelViewSet):
    """
    CRUD for software licences.
    Write: IT specialist or super_admin. Read: all authenticated.
    """

    queryset = SoftwareLicense.objects.all()
    serializer_class = SoftwareLicenseSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsITSpecialistOrSuperAdmin()]
        return [IsAuthenticated()]
