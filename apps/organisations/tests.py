from django.urls import reverse
from rest_framework.test import APITestCase

from apps.employees.models import Employee
from apps.organisations.models import Organisation
from apps.users.models import User


class OrganisationTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='admin@example.com',
            password='password',
            full_name='Super Admin',
            role='super_admin',
        )
        self.client.force_authenticate(self.user)
        self.employee = Employee.objects.create(
            employee_id='EMP001',
            full_name='Existing Employee',
            alias_name='E1',
            official_email='existing@example.com',
            contact_number='1234567890',
        )

    def test_create_base_organisation_assigns_all_existing_employees(self):
        response = self.client.post(
            reverse('organisation-list'),
            {
                'name': 'Base Org',
                'address': '123 Corporate Street',
                'city': 'Mumbai',
                'country': 'India',
                'is_base': True,
            },
        )

        self.assertEqual(response.status_code, 201)
        base_org = Organisation.objects.get(is_base=True)
        self.assertEqual(base_org.name, 'Base Org')
        self.assertTrue(self.employee in base_org.members.all())

    def test_create_second_base_organisation_is_rejected(self):
        Organisation.objects.create(
            name='Base Org',
            address='123 Corporate Street',
            city='Mumbai',
            country='India',
            is_base=True,
        )

        response = self.client.post(
            reverse('organisation-list'),
            {
                'name': 'Another Base Org',
                'address': '321 Secondary Street',
                'city': 'Delhi',
                'country': 'India',
                'is_base': True,
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('A base organisation already exists.', str(response.data))

    def test_create_client_organisation_and_add_members(self):
        base_org = Organisation.objects.create(
            name='Base Org',
            address='123 Corporate Street',
            city='Mumbai',
            country='India',
            is_base=True,
        )
        employee = Employee.objects.create(
            employee_id='EMP002',
            full_name='Base Member',
            alias_name='E2',
            official_email='member2@example.com',
            contact_number='0987654321',
        )
        employee.organisations.add(base_org)

        response = self.client.post(
            reverse('organisation-list'),
            {
                'name': 'Client Org',
                'address': '55 Client Lane',
                'city': 'Bengaluru',
                'country': 'India',
                'is_base': False,
            },
        )

        self.assertEqual(response.status_code, 201)
        client_org = Organisation.objects.get(name='Client Org')

        add_response = self.client.post(
            reverse('organisation-add-members', kwargs={'pk': client_org.id}),
            {
                'employee_ids': [employee.id],
                'new_members': [
                    {
                        'employee_id': 'EMP003',
                        'full_name': 'New Client Employee',
                        'official_email': 'newclient@example.com',
                        'contact_number': '1122334455',
                    }
                ],
            },
            format='json',
        )

        self.assertEqual(add_response.status_code, 200)
        self.assertTrue(employee in client_org.members.all())
        self.assertTrue(
            Employee.objects.filter(employee_id='EMP003', organisations=client_org).exists()
        )
