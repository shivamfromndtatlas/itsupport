from django.urls import reverse
from rest_framework.test import APITestCase

from apps.employees.models import Employee
from apps.organisations.models import Organisation, OrganisationLocation, OrganisationMemberProfile
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
        self.assertFalse(
            Employee.objects.filter(employee_id='EMP003', organisations__is_base=True).exists()
        )

        list_response = self.client.get(reverse('employee-list'))
        self.assertEqual(list_response.status_code, 200)
        employee_ids = [row['employee_id'] for row in list_response.data]
        self.assertNotIn('EMP003', employee_ids)

    def test_create_client_member_without_employee_id_generates_one(self):
        Organisation.objects.create(
            name='Base Org',
            address='123 Corporate Street',
            city='Mumbai',
            country='India',
            is_base=True,
        )
        client_org = Organisation.objects.create(
            name='Client Org',
            address='55 Client Lane',
            city='Bengaluru',
            country='India',
            is_base=False,
        )

        response = self.client.post(
            reverse('organisation-add-members', kwargs={'pk': client_org.id}),
            {
                'employee_ids': [],
                'new_members': [
                    {
                        'full_name': 'New Client Employee',
                        'official_email': 'newclient2@example.com',
                        'contact_number': '1122334455',
                    }
                ],
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        employee = Employee.objects.get(official_email='newclient2@example.com')
        self.assertTrue(employee.employee_id.startswith('AUTO-'))
        self.assertTrue(employee.organisations.filter(id=client_org.id).exists())
        self.assertTrue(
            OrganisationMemberProfile.objects.filter(organisation=client_org, employee=employee).exists()
        )

    def test_client_member_profile_update_does_not_change_employee_record(self):
        base_org = Organisation.objects.create(
            name='Base Org',
            address='123 Corporate Street',
            city='Mumbai',
            country='India',
            is_base=True,
        )
        client_org = Organisation.objects.create(
            name='Client Org',
            address='55 Client Lane',
            city='Bengaluru',
            country='India',
            is_base=False,
        )
        employee = Employee.objects.create(
            employee_id='EMP004',
            full_name='Anna Gray',
            alias_name='A Gray',
            official_email='agoel@ndtatlas.com',
            contact_number='',
        )
        employee.organisations.add(base_org, client_org)
        OrganisationMemberProfile.objects.create(organisation=client_org, employee=employee)

        response = self.client.patch(
            reverse('organisation-member-profiles', kwargs={'pk': client_org.id}),
            {
                'employee': employee.id,
                'official_email': 'agray@aeis.com',
                'designation': 'Client Lead',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['official_email'], 'agray@aeis.com')
        self.assertEqual(response.data['designation'], 'Client Lead')

        employee.refresh_from_db()
        self.assertEqual(employee.official_email, 'agoel@ndtatlas.com')
        self.assertEqual(employee.designation, '')

    def test_client_member_can_be_deleted_from_organisation(self):
        base_org = Organisation.objects.create(
            name='Base Org',
            address='123 Corporate Street',
            city='Mumbai',
            country='India',
            is_base=True,
        )
        client_org = Organisation.objects.create(
            name='Client Org',
            address='55 Client Lane',
            city='Bengaluru',
            country='India',
            is_base=False,
        )
        employee = Employee.objects.create(
            employee_id='EMP005',
            full_name='Delete Me',
            alias_name='DM',
            official_email='deleteme@example.com',
            contact_number='',
        )
        employee.organisations.add(base_org, client_org)
        OrganisationMemberProfile.objects.create(organisation=client_org, employee=employee)

        response = self.client.delete(
            reverse('organisation-member-profiles', kwargs={'pk': client_org.id}),
            {'employee': employee.id},
            format='json',
        )

        self.assertEqual(response.status_code, 204)
        employee.refresh_from_db()
        self.assertTrue(employee.organisations.filter(id=base_org.id).exists())
        self.assertFalse(employee.organisations.filter(id=client_org.id).exists())
        self.assertFalse(
            OrganisationMemberProfile.objects.filter(organisation=client_org, employee=employee).exists()
        )

    def test_update_location(self):
        Organisation.objects.create(
            name='Base Org',
            address='123 Corporate Street',
            city='Mumbai',
            country='India',
            is_base=True,
        )
        client_org = Organisation.objects.create(
            name='Client Org',
            address='55 Client Lane',
            city='Bengaluru',
            country='India',
            is_base=False,
        )
        location = OrganisationLocation.objects.create(
            organisation=client_org,
            name='Branch Office',
            address='H32B, Saket',
            city='New Delhi',
            country='India',
            notes='Old notes',
        )

        response = self.client.patch(
            reverse('organisation-update-location', kwargs={'pk': client_org.id, 'location_id': location.id}),
            {
                'name': 'Head Office',
                'address': 'H36A, Saket',
                'city': 'New Delhi',
                'country': 'India',
                'notes': 'Main office',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['name'], 'Head Office')
        self.assertEqual(response.data['address'], 'H36A, Saket')
        self.assertEqual(response.data['notes'], 'Main office')

        location.refresh_from_db()
        self.assertEqual(location.name, 'Head Office')
        self.assertEqual(location.address, 'H36A, Saket')
        self.assertEqual(location.notes, 'Main office')
