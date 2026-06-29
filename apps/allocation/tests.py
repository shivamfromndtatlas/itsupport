from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.employees.models import Employee
from apps.inventory.models import Asset, AssetType
from apps.allocation.models import AssetAllocation
from apps.organisations.models import Organisation


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
        self.base_org = Organisation.objects.create(
            name='Base Org',
            address='Base Address',
            city='Base City',
            country='India',
            is_base=True,
        )
        self.client_org = Organisation.objects.create(
            name='Client Org',
            address='Client Address',
            city='Client City',
            country='India',
            is_base=False,
        )

        self.asset_type = AssetType.objects.create(name='Headset', asset_type='hardware')
        self.asset = Asset.objects.create(
            asset_id='WH3022_999',
            asset_type=self.asset_type,
            status='assigned',
            organisation=self.client_org,
        )
        self.employee = Employee.objects.create(
            employee_id='E-100',
            full_name='Test Employee',
            official_email='employee@example.com',
        )
        self.employee.organisations.add(self.client_org)
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

    def test_client_org_asset_can_be_assigned_to_client_employee(self):
        other_asset = Asset.objects.create(
            asset_id='WH3022_100',
            asset_type=self.asset_type,
            organisation=self.client_org,
            status='available',
        )
        response = self.client.post(
            '/api/allocation/assets/',
            {
                'asset': other_asset.id,
                'employee': self.employee.id,
                'assigned_date': '2026-06-25',
                'notes': 'Issued to client employee',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        other_asset.refresh_from_db()
        self.assertEqual(other_asset.status, 'assigned')

    def test_cross_org_asset_assignment_is_rejected(self):
        base_asset = Asset.objects.create(
            asset_id='WH3022_101',
            asset_type=self.asset_type,
            organisation=self.base_org,
            status='available',
        )
        response = self.client.post(
            '/api/allocation/assets/',
            {
                'asset': base_asset.id,
                'employee': self.employee.id,
                'assigned_date': '2026-06-25',
                'notes': 'Should fail',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('asset organisation', str(response.data).lower())
