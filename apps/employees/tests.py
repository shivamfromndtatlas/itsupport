from django.test import TestCase
from apps.employees.models import Employee
from apps.organisations.models import Organisation
from apps.employees.serializers import EmployeeSerializer


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
