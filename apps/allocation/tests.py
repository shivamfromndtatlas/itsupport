from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.employees.models import Employee
from apps.inventory.models import Asset, AssetType
from apps.allocation.models import AssetAllocation


class AssetAllocationDeleteTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        User = get_user_model()
        self.user = User.objects.create_user(
            email='admin@example.com',
            password='pass1234',
            full_name='Admin User',
            role='super_admin',
        )
        self.client.force_authenticate(user=self.user)

        self.asset_type = AssetType.objects.create(name='Headset', asset_type='hardware')
        self.asset = Asset.objects.create(
            asset_id='WH3022_999',
            asset_type=self.asset_type,
            status='assigned',
        )
        self.employee = Employee.objects.create(
            employee_id='E-100',
            full_name='Test Employee',
            official_email='employee@example.com',
        )
        self.allocation = AssetAllocation.objects.create(
            asset=self.asset,
            employee=self.employee,
            assigned_by=self.user,
            assigned_date='2026-06-24',
            status='active',
        )

    def test_delete_allocation_releases_asset(self):
        response = self.client.delete(f'/api/allocation/assets/{self.allocation.id}/')

        self.assertEqual(response.status_code, 204)
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.status, 'available')
        self.assertFalse(AssetAllocation.objects.filter(id=self.allocation.id).exists())
