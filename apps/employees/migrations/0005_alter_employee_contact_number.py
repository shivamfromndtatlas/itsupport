from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('employees', '0004_employee_organisations'),
    ]

    operations = [
        migrations.AlterField(
            model_name='employee',
            name='contact_number',
            field=models.CharField(blank=True, max_length=20),
        ),
    ]
