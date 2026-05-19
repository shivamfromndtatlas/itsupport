from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('employees', '0002_employee_core_process_columns'),
    ]

    operations = [
        migrations.AddField(
            model_name='employee',
            name='status',
            field=models.CharField(
                choices=[
                    ('active', 'Active'),
                    ('inactive', 'Inactive'),
                    ('on_leave', 'On Leave'),
                ],
                default='active',
                max_length=20,
            ),
        ),
        migrations.RemoveField(
            model_name='employee',
            name='is_active',
        ),
    ]
