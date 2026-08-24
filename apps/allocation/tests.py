from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.employees.models import Employee
from apps.inventory.models import Asset, AssetType, SoftwareLicense
from apps.allocation.models import AssetAllocation, LicenseAllocation
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


class LicenseAllocationTests(TestCase):
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
        self.employee = Employee.objects.create(
            employee_id='E-200',
            full_name='License Test Employee',
            official_email='license.employee@example.com',
        )
        self.license = SoftwareLicense.objects.create(
            software_name='TestSoft',
            total_seats=5,
            available_seats=5,
        )

    def test_assign_license_to_employee(self):
        # The request body key must be `license` to match LicenseAllocation's
        # field name and LicenseAllocationSerializer's `fields` - a payload
        # keyed `software_license` (as the frontend once sent) is rejected as
        # a missing required field before perform_create ever runs.
        response = self.client.post(
            '/api/allocation/licenses/',
            {
                'employee': self.employee.id,
                'license': self.license.id,
                'assigned_date': '2026-07-10',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(LicenseAllocation.objects.filter(employee=self.employee, license=self.license).exists())
        self.license.refresh_from_db()
        self.assertEqual(self.license.available_seats, 4)

    def test_assign_license_with_wrong_field_name_is_rejected(self):
        response = self.client.post(
            '/api/allocation/licenses/',
            {
                'employee': self.employee.id,
                'software_license': self.license.id,
                'assigned_date': '2026-07-10',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('license', response.data)

    def test_unlimited_license_ignores_seat_count(self):
        unlimited_license = SoftwareLicense.objects.create(
            software_name='Adobe Reader',
            is_unlimited=True,
            total_seats=0,
            available_seats=0,
        )

        response = self.client.post(
            '/api/allocation/licenses/',
            {
                'employee': self.employee.id,
                'license': unlimited_license.id,
                'assigned_date': '2026-07-10',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        unlimited_license.refresh_from_db()
        # Seats stay untouched - there's no cap to enforce or decrement.
        self.assertEqual(unlimited_license.available_seats, 0)

        allocation = LicenseAllocation.objects.get(employee=self.employee, license=unlimited_license)
        revoke_response = self.client.post(f'/api/allocation/licenses/{allocation.id}/revoke/')
        self.assertEqual(revoke_response.status_code, 200)
        unlimited_license.refresh_from_db()
        self.assertEqual(unlimited_license.available_seats, 0)
