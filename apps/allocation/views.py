import io

import qrcode
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.users.permissions import IsITSpecialistOrSuperAdmin

from .models import AssetAllocation, LicenseAllocation
from .serializers import AssetAllocationSerializer, LicenseAllocationSerializer


def generate_qr_code(allocation):
    """Generate a QR code PNG for an AssetAllocation and attach it to the instance."""
    qr_data = (
        f"ASSET:{allocation.asset.asset_id}"
        f"|EMP:{allocation.employee.employee_id}"
        f"|DATE:{allocation.assigned_date}"
        f"|UUID:{allocation.qr_uuid}"
    )
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(qr_data)
    qr.make(fit=True)
    img = qr.make_image(fill='black', back_color='white')
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    filename = f'qr_{allocation.qr_uuid}.png'
    allocation.qr_code.save(filename, ContentFile(buffer.getvalue()), save=False)


class AssetAllocationViewSet(viewsets.ModelViewSet):
    """
    CRUD for asset allocations.
    On create: generates QR code image and sets Asset status to 'assigned'.
    recover action: marks allocation recovered, resets Asset status to 'available'.
    Write: IT specialist or super_admin. Read: all authenticated.
    """

    queryset = AssetAllocation.objects.select_related(
        'asset__asset_type',
        'employee',
        'assigned_by',
        'recovered_by',
    ).all()
    serializer_class = AssetAllocationSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy', 'recover'):
            return [IsITSpecialistOrSuperAdmin()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        with transaction.atomic():
            allocation = AssetAllocation(**serializer.validated_data)
            allocation.assigned_by = self.request.user
            allocation.status = 'active'
            allocation.full_clean()
            allocation.save()
            # Generate QR code
            generate_qr_code(allocation)
            allocation.save()
            # Update asset status
            asset = allocation.asset
            asset.status = 'assigned'
            asset.save(update_fields=['status'])

    def perform_update(self, serializer):
        with transaction.atomic():
            old_allocation = self.get_object()
            old_asset = old_allocation.asset
            old_status = old_allocation.status

            allocation = serializer.save()
            allocation.full_clean()
            allocation.save()

            old_asset_id = getattr(old_asset, 'id', None)
            if old_status == 'active' and old_asset_id:
                if old_asset_id != allocation.asset_id:
                    old_asset.status = 'available'
                    old_asset.save(update_fields=['status'])

            if allocation.status == 'active':
                allocation.asset.status = 'assigned'
                allocation.asset.save(update_fields=['status'])
            elif allocation.status == 'recovered':
                allocation.asset.status = 'available'
                allocation.asset.save(update_fields=['status'])

    @action(detail=True, methods=['post'], url_path='recover')
    def recover(self, request, pk=None):
        """
        Mark the allocation as recovered and return the asset based on its condition.
        """
        allocation = self.get_object()

        if allocation.status == 'recovered':
            return Response(
                {'detail': 'Allocation is already recovered.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        condition_value = str(request.data.get('condition') or '').strip() or 'Good'
        condition_normalized = condition_value.lower()
        is_ok_condition = condition_normalized in {'good', 'ok', 'okay', 'fair'}
        availability_value = 'In Stock' if is_ok_condition else 'Under Repair'
        asset_status = 'available' if is_ok_condition else 'maintenance'

        with transaction.atomic():
            allocation.status = 'recovered'
            allocation.recovered_by = request.user
            allocation.recovered_date = timezone.now().date()
            allocation.save(update_fields=['status', 'recovered_by', 'recovered_date'])

            asset = allocation.asset
            attribute_values = dict(asset.attribute_values or {})
            condition_label = 'Good' if condition_normalized in {'good', 'ok', 'okay'} else 'Fair' if condition_normalized == 'fair' else condition_value
            attribute_values['condition'] = condition_label
            attribute_values['10'] = availability_value
            attribute_values['Availability Status'] = availability_value

            # Return asset to the right pool based on condition
            asset = allocation.asset
            asset.status = asset_status
            asset.attribute_values = attribute_values
            asset.save(update_fields=['status', 'attribute_values'])

        return Response(
            {
                'detail': 'Asset recovered successfully.',
                'allocation': AssetAllocationSerializer(
                    allocation, context={'request': request}
                ).data,
            },
            status=status.HTTP_200_OK,
        )

    def destroy(self, request, *args, **kwargs):
        """
        Delete an allocation. If it is still active, release the asset back to available.
        """
        with transaction.atomic():
            allocation = self.get_object()
            asset = allocation.asset
            should_release_asset = allocation.status == 'active'
            allocation.delete()

            if should_release_asset:
                asset.status = 'available'
                asset.save(update_fields=['status'])

        return Response(status=status.HTTP_204_NO_CONTENT)


class LicenseAllocationViewSet(viewsets.ModelViewSet):
    """
    CRUD for software licence allocations.
    On create: decrements SoftwareLicense.available_seats.
    revoke action: increments available_seats back.
    Write: IT specialist or super_admin. Read: all authenticated.
    """

    queryset = LicenseAllocation.objects.select_related(
        'license',
        'employee',
        'assigned_by',
        'revoked_by',
    ).all()
    serializer_class = LicenseAllocationSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy', 'revoke'):
            return [IsITSpecialistOrSuperAdmin()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        license_obj = serializer.validated_data['license']
        if license_obj.available_seats <= 0:
            from rest_framework.exceptions import ValidationError
            raise ValidationError('No available seats for this licence.')
        allocation = LicenseAllocation(**serializer.validated_data)
        allocation.assigned_by = self.request.user
        allocation.status = 'active'
        allocation.full_clean()
        allocation.save()
        # Decrement available seats
        license_obj.available_seats -= 1
        license_obj.save(update_fields=['available_seats'])

    @action(detail=True, methods=['post'], url_path='revoke')
    def revoke(self, request, pk=None):
        """
        Revoke the licence allocation and return the seat to the pool.
        """
        allocation = self.get_object()

        if allocation.status == 'revoked':
            return Response(
                {'detail': 'Allocation is already revoked.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        allocation.status = 'revoked'
        allocation.revoked_by = request.user
        allocation.revoked_date = timezone.now().date()
        allocation.save()

        # Return seat to licence pool
        license_obj = allocation.license
        license_obj.available_seats += 1
        license_obj.save(update_fields=['available_seats'])

        return Response(
            {
                'detail': 'Licence allocation revoked successfully.',
                'allocation': LicenseAllocationSerializer(
                    allocation, context={'request': request}
                ).data,
            },
            status=status.HTTP_200_OK,
        )


@api_view(['GET'])
@permission_classes([AllowAny])
def scan_qr(request, qr_uuid):
    """
    GET /allocation/scan/<uuid>/
    Public endpoint for QR code scanning — returns allocation info.
    """
    try:
        allocation = AssetAllocation.objects.select_related(
            'asset__asset_type',
            'employee',
            'assigned_by',
        ).get(qr_uuid=qr_uuid)
    except AssetAllocation.DoesNotExist:
        return Response(
            {'detail': 'No allocation found for this QR code.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    return Response(
        AssetAllocationSerializer(allocation, context={'request': request}).data,
        status=status.HTTP_200_OK,
    )
