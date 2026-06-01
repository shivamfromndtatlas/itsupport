from django.urls import reverse
from rest_framework.test import APITestCase

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
