from django.urls import reverse
from rest_framework.test import APITestCase

from apps.employees.models import Employee
from apps.users.models import User

from .models import NewJoinerRequest


class NewJoinerRequestViewSetTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='admin@example.com',
            password='password',
            full_name='Admin User',
            role='super_admin',
        )
        self.client.force_authenticate(self.user)

    def create_request(self, employee_id, status):
        return NewJoinerRequest.objects.create(
            full_name=f'Employee {employee_id}',
            employee_id=employee_id,
            contact_number='1234567890',
            personal_email=f'{employee_id.lower()}@example.com',
            designation='Engineer',
            date_of_joining='2026-05-28',
            status=status,
            submitted_by=self.user,
        )

    def test_list_filters_by_pending_status(self):
        self.create_request('EMP001', 'pending')
        self.create_request('EMP002', 'confirmed')
        self.create_request('EMP003', 'rejected')

        response = self.client.get(reverse('onboarding-list'), {'status': 'pending'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['status'], 'pending')

    def test_list_returns_no_rows_for_unknown_status(self):
        self.create_request('EMP001', 'pending')

        response = self.client.get(reverse('onboarding-list'), {'status': 'unknown'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 0)


class NewJoinerRequestAliasTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='admin2@example.com',
            password='password',
            full_name='Admin User',
            role='super_admin',
        )
        self.client.force_authenticate(self.user)

    def test_create_rejects_alias_with_middle_name(self):
        response = self.client.post(
            reverse('onboarding-list'),
            {
                'full_name': 'Ajay Kumar',
                'employee_id': 'EMP600',
                'contact_number': '1234567890',
                'personal_email': 'ajay@example.com',
                'designation': 'Engineer',
                'date_of_joining': '2026-05-28',
                'alias_name': 'Andrew James King',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('alias_name', response.data)

    def test_confirm_creates_employee_with_derived_client_email(self):
        request = NewJoinerRequest.objects.create(
            full_name='Ajay Kumar',
            employee_id='EMP601',
            contact_number='1234567890',
            personal_email='ajay2@example.com',
            designation='Engineer',
            date_of_joining='2026-05-28',
            alias_name='Andrew King',
            status='pending',
            submitted_by=self.user,
        )

        response = self.client.post(reverse('onboarding-confirm', kwargs={'pk': request.pk}))

        self.assertEqual(response.status_code, 200)
        employee = Employee.objects.get(employee_id='EMP601')
        self.assertEqual(employee.client_email, 'aking@aeis.com')

    def test_confirm_rejects_alias_colliding_with_existing_employee(self):
        Employee.objects.create(
            employee_id='EMP602',
            full_name='Amit Jones',
            alias_name='Amy Jones',
            client_email='ajones@aeis.com',
            official_email='amit4@example.com',
            status='active',
        )
        request = NewJoinerRequest.objects.create(
            full_name='Arjun Jones',
            employee_id='EMP603',
            contact_number='1234567890',
            personal_email='arjun2@example.com',
            designation='Engineer',
            date_of_joining='2026-05-28',
            alias_name='Alan Jones',
            status='pending',
            submitted_by=self.user,
        )

        response = self.client.post(reverse('onboarding-confirm', kwargs={'pk': request.pk}))

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Employee.objects.filter(employee_id='EMP603').exists())
