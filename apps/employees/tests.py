from django.test import TestCase
from django.urls import reverse

from apps.employees.models import Employee
from apps.employees.base_org_assignment import skip_base_org_assignment
from apps.organisations.models import Organisation, OrganisationMemberProfile
from apps.employees.serializers import EmployeeSerializer
from apps.users.models import User
from rest_framework.test import APITestCase


class EmployeeOrganisationTests(TestCase):
    def setUp(self):
        # Create base organisation
        self.base_org = Organisation.objects.create(
            name="Base Org",
            address="123 Base St",
            city="Base City",
            country="Base Country",
            is_base=True
        )
        # Create another organisation
        self.client_org = Organisation.objects.create(
            name="Client Org",
            address="456 Client St",
            city="Client City",
            country="Client Country",
            is_base=False
        )

    def test_employee_signal_assigns_base_org(self):
        # Create employee without specifying organisation
        employee = Employee.objects.create(
            employee_id="EMP001",
            full_name="John Doe",
            official_email="john@example.com",
            status="active"
        )
        # Verify signal assigned base organisation
        self.assertEqual(employee.organisations.count(), 1)
        self.assertEqual(employee.organisations.first(), self.base_org)

    def test_serializer_create_with_organisations(self):
        data = {
            "employee_id": "EMP002",
            "full_name": "Jane Doe",
            "official_email": "jane@example.com",
            "status": "active",
            "organisations": [self.base_org.id, self.client_org.id]
        }
        serializer = EmployeeSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        employee = serializer.save()

        # Check organisations
        self.assertEqual(employee.organisations.count(), 2)
        orgs = list(employee.organisations.all())
        self.assertIn(self.base_org, orgs)
        self.assertIn(self.client_org, orgs)

    def test_serializer_update_organisations(self):
        # Create employee (automatically gets base org via signal)
        employee = Employee.objects.create(
            employee_id="EMP003",
            full_name="Bob Smith",
            official_email="bob@example.com",
            status="active"
        )

        data = {
            "organisations": [self.client_org.id]
        }
        serializer = EmployeeSerializer(instance=employee, data=data, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        updated_employee = serializer.save()

        # Check organisations changed from base_org to client_org
        self.assertEqual(updated_employee.organisations.count(), 1)
        self.assertEqual(updated_employee.organisations.first(), self.client_org)


class EmployeeApiScopeTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='admin@example.com',
            password='password',
            full_name='Super Admin',
            role='super_admin',
        )
        self.client.force_authenticate(user=self.user)
        self.base_org = Organisation.objects.create(
            name='Base Org',
            address='123 Base St',
            city='Base City',
            country='Base Country',
            is_base=True,
        )
        self.client_org = Organisation.objects.create(
            name='Client Org',
            address='456 Client St',
            city='Client City',
            country='Client Country',
            is_base=False,
        )
        self.base_employee = Employee.objects.create(
            employee_id='EMP100',
            full_name='Base Employee',
            official_email='base@example.com',
            status='active',
        )
        with skip_base_org_assignment():
            self.client_employee = Employee.objects.create(
                employee_id='EMP200',
                full_name='Client Employee',
                official_email='client@example.com',
                status='active',
            )
        self.client_employee.organisations.add(self.client_org)

    def test_employee_list_defaults_to_base_only(self):
        response = self.client.get(reverse('employee-list'))

        self.assertEqual(response.status_code, 200)
        employee_ids = [row['employee_id'] for row in response.data]
        self.assertIn('EMP100', employee_ids)
        self.assertNotIn('EMP200', employee_ids)

    def test_allocatable_employee_scope_includes_client_employees(self):
        response = self.client.get(reverse('employee-list'), {'scope': 'allocatable'})

        self.assertEqual(response.status_code, 200)
        employee_ids = [row['employee_id'] for row in response.data]
        self.assertIn('EMP100', employee_ids)
        self.assertIn('EMP200', employee_ids)

    def test_client_employee_detail_can_be_retrieved_and_patched(self):
        detail_url = reverse('employee-detail', kwargs={'pk': self.client_employee.id})

        retrieve_response = self.client.get(detail_url)
        self.assertEqual(retrieve_response.status_code, 200)
        self.assertEqual(retrieve_response.data['employee_id'], 'EMP200')

        patch_response = self.client.patch(detail_url, {'core_process_code': '02BDP'}, format='json')
        self.assertEqual(patch_response.status_code, 200)
        self.assertEqual(patch_response.data['core_process_code'], '02BDP')
        self.assertEqual(patch_response.data['core_process_name'], 'Business Development Process')

    def test_client_employee_employee_id_can_be_updated(self):
        detail_url = reverse('employee-detail', kwargs={'pk': self.client_employee.id})

        patch_response = self.client.patch(
            detail_url,
            {
                'employee_id': 'EMP200-UPDATED',
                'full_name': 'Client Employee',
                'official_email': 'client@example.com',
            },
            format='json',
        )

        self.assertEqual(patch_response.status_code, 200)
        self.assertEqual(patch_response.data['employee_id'], 'EMP200-UPDATED')
        self.client_employee.refresh_from_db()
        self.assertEqual(self.client_employee.employee_id, 'EMP200-UPDATED')

    def test_duplicate_employee_email_is_rejected(self):
        response = self.client.post(
            reverse('employee-list'),
            {
                'employee_id': 'EMP201',
                'full_name': 'Duplicate Email Employee',
                'official_email': 'client@example.com',
                'status': 'active',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('An employee with this email already exists.', str(response.data))


class EmployeeDashboardTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='admin@example.com',
            password='password',
            full_name='Super Admin',
            role='super_admin',
        )
        self.client.force_authenticate(user=self.user)
        self.base_org = Organisation.objects.create(
            name='Base Org',
            address='123 Base St',
            city='Base City',
            country='Base Country',
            is_base=True,
        )
        self.employee = Employee.objects.create(
            employee_id='EMP300',
            full_name='Dashboard Employee',
            official_email='dash@example.com',
            status='active',
        )

    def test_dashboard_works_without_member_profile(self):
        response = self.client.get(reverse('employee-dashboard', kwargs={'pk': self.employee.id}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['employee_id'], 'EMP300')
        self.assertEqual(response.data['base_email'], 'dash@example.com')

    def test_dashboard_prefers_client_profile_values(self):
        client_org = Organisation.objects.create(
            name='Client Org',
            address='456 Client St',
            city='Client City',
            country='Client Country',
            is_base=False,
        )
        self.employee.organisations.add(self.base_org, client_org)
        profile = OrganisationMemberProfile.objects.create(
            organisation=client_org,
            employee=self.employee,
            employee_code='CL-001',
            full_name='Dashboard Employee Client',
            alias_name='Client Alias',
            official_email='clientdash@example.com',
            designation='Client Lead',
            core_process_code='02BDP',
            date_of_joining='2024-01-15',
            status='inactive',
        )

        response = self.client.get(reverse('employee-dashboard', kwargs={'pk': self.employee.id}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['employee_id'], 'CL-001')
        self.assertEqual(response.data['full_name'], 'Dashboard Employee Client')
        self.assertEqual(response.data['alias_name'], 'Client Alias')
        self.assertEqual(response.data['official_email'], 'clientdash@example.com')
        self.assertEqual(response.data['designation'], 'Client Lead')
        self.assertEqual(response.data['core_process_name'], 'Business Development Process')
        self.assertEqual(response.data['status'], 'inactive')
        self.assertEqual(response.data['date_of_joining'], '2024-01-15')
