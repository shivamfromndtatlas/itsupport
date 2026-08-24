from django.test import TestCase
from django.urls import reverse

from apps.employees import alias_rules
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


class AliasRulesTests(TestCase):
    def test_derive_client_email_ignores_middle_name_and_lowercases(self):
        self.assertEqual(alias_rules.derive_client_email('Amy Jones'), 'ajones@aeis.com')
        self.assertEqual(alias_rules.derive_client_email('Andrew King'), 'aking@aeis.com')

    def test_rejects_alias_with_middle_name(self):
        with self.assertRaises(alias_rules.AliasError):
            alias_rules.split_two_word_name('Amy Jane Jones')

    def test_rejects_single_word_alias(self):
        with self.assertRaises(alias_rules.AliasError):
            alias_rules.split_two_word_name('Amy')

    def test_check_alias_rejects_mismatched_initials(self):
        with self.assertRaises(alias_rules.AliasError):
            alias_rules.check_alias('Ajay Kumar', 'Steven Miller')

    def test_check_alias_accepts_matching_initials(self):
        client_email = alias_rules.check_alias('Ajay Kumar', 'Andrew King')
        self.assertEqual(client_email, 'aking@aeis.com')

    def test_check_alias_rejects_global_collision_regardless_of_first_name(self):
        Employee.objects.create(
            employee_id='EMP400',
            full_name='Amit Jones',
            alias_name='Amy Jones',
            client_email='ajones@aeis.com',
            official_email='amit@example.com',
            status='active',
        )
        # A different employee, also initials A/J, whose alias would derive
        # to the same ajones@aeis.com must be rejected -- per rule 4, this
        # applies "irrespective of whatever be the first name".
        with self.assertRaises(alias_rules.AliasError):
            alias_rules.check_alias('Arjun Jones', 'Alan Jones')

    def test_check_alias_detects_collision_with_legacy_official_email(self):
        # Pre-existing records set their client-style email by hand in
        # official_email, before this checker existed. Those must still
        # block a new alias deriving to the same email.
        Employee.objects.create(
            employee_id='EMP404',
            full_name='Abhishek Poddar',
            alias_name='Alex Brooks',
            official_email='abrooks@aeis.com',
            status='active',
        )
        with self.assertRaises(alias_rules.AliasError):
            alias_rules.check_alias('', 'Alex Brooks')

    def test_check_alias_skips_initials_when_full_name_omitted(self):
        # The standalone Alias Name Checker looks up availability without an
        # employee attached, so initials-matching shouldn't be enforced.
        client_email = alias_rules.check_alias('', 'Steven Miller')
        self.assertEqual(client_email, 'smiller@aeis.com')

    def test_check_alias_still_enforces_uniqueness_when_full_name_omitted(self):
        Employee.objects.create(
            employee_id='EMP403',
            full_name='Amit Jones',
            alias_name='Amy Jones',
            client_email='ajones@aeis.com',
            official_email='amit5@example.com',
            status='active',
        )
        with self.assertRaises(alias_rules.AliasError):
            alias_rules.check_alias('', 'Alan Jones')

    def test_check_alias_excludes_own_record_on_update(self):
        employee = Employee.objects.create(
            employee_id='EMP401',
            full_name='Amit Jones',
            alias_name='Amy Jones',
            client_email='ajones@aeis.com',
            official_email='amit2@example.com',
            status='active',
        )
        # Re-validating the same alias for the same employee should not
        # collide with itself.
        client_email = alias_rules.check_alias(
            'Amit Jones', 'Amy Jones', exclude_employee_id=employee.pk
        )
        self.assertEqual(client_email, 'ajones@aeis.com')

    def test_suggest_aliases_matches_initials_and_excludes_taken_emails(self):
        Employee.objects.create(
            employee_id='EMP402',
            full_name='Andrew King Real',
            alias_name='Andrew King',
            client_email='aking@aeis.com',
            official_email='andrewking@example.com',
            status='active',
        )

        suggestions = alias_rules.suggest_aliases('Ajay Kumar')

        self.assertTrue(len(suggestions) > 0)
        emails = [s['client_email'] for s in suggestions]
        self.assertEqual(len(emails), len(set(emails)), 'suggestions must not share a derived email')
        for suggestion in suggestions:
            first, last = suggestion['alias_name'].split()
            self.assertEqual(first[0], 'A')
            self.assertEqual(last[0], 'K')
            self.assertNotEqual(suggestion['client_email'], 'aking@aeis.com')


class EmployeeSerializerAliasTests(TestCase):
    def test_create_derives_client_email_from_alias(self):
        data = {
            'employee_id': 'EMP500',
            'full_name': 'Ajay Kumar',
            'alias_name': 'Andrew King',
            'official_email': 'ajay@example.com',
            'status': 'active',
        }
        serializer = EmployeeSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        employee = serializer.save()
        self.assertEqual(employee.client_email, 'aking@aeis.com')

    def test_create_rejects_alias_with_mismatched_initials(self):
        data = {
            'employee_id': 'EMP501',
            'full_name': 'Ajay Kumar',
            'alias_name': 'Steven Miller',
            'official_email': 'ajay2@example.com',
            'status': 'active',
        }
        serializer = EmployeeSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('alias_name', serializer.errors)

    def test_second_employee_cannot_reuse_derived_email(self):
        Employee.objects.create(
            employee_id='EMP502',
            full_name='Amit Jones',
            alias_name='Amy Jones',
            client_email='ajones@aeis.com',
            official_email='amit3@example.com',
            status='active',
        )
        data = {
            'employee_id': 'EMP503',
            'full_name': 'Arjun Jones',
            'alias_name': 'Alan Jones',
            'official_email': 'arjun@example.com',
            'status': 'active',
        }
        serializer = EmployeeSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('alias_name', serializer.errors)

    def test_update_keeps_legacy_alias_with_mismatched_initials(self):
        # Alias set by hand before the initials-matching rule existed --
        # editing an unrelated field shouldn't be blocked by it.
        employee = Employee.objects.create(
            employee_id='EMP504',
            full_name='Saveek Singh',
            alias_name='Steve Ross',
            client_email='sross@aeis.com',
            official_email='saveek@example.com',
            status='active',
        )
        serializer = EmployeeSerializer(
            employee, data={'status': 'inactive'}, partial=True
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        updated = serializer.save()
        self.assertEqual(updated.status, 'inactive')
        self.assertEqual(updated.alias_name, 'Steve Ross')
        self.assertEqual(updated.client_email, 'sross@aeis.com')

    def test_update_still_validates_a_newly_changed_alias(self):
        employee = Employee.objects.create(
            employee_id='EMP505',
            full_name='Saveek Singh',
            alias_name='Steve Ross',
            client_email='sross@aeis.com',
            official_email='saveek2@example.com',
            status='active',
        )
        serializer = EmployeeSerializer(
            employee, data={'alias_name': 'Ryan Miles'}, partial=True
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('alias_name', serializer.errors)
