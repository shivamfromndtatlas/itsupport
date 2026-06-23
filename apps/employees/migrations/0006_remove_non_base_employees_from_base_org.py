from django.db import migrations


def remove_non_base_employees_from_base_org(apps, schema_editor):
    Employee = apps.get_model('employees', 'Employee')
    Organisation = apps.get_model('organisations', 'Organisation')

    base_org = Organisation.objects.filter(is_base=True).first()
    if not base_org:
        return

    employees_to_remove = Employee.objects.filter(organisations=base_org).exclude(employee_id__startswith='ANDT')
    for employee in employees_to_remove:
        employee.organisations.remove(base_org)


class Migration(migrations.Migration):

    dependencies = [
        ('employees', '0005_alter_employee_contact_number'),
    ]

    operations = [
        migrations.RunPython(remove_non_base_employees_from_base_org, migrations.RunPython.noop),
    ]
