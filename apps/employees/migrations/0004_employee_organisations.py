from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('employees', '0003_employee_status'),
        ('organisations', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='employee',
            name='organisations',
            field=models.ManyToManyField(blank=True, related_name='members', to='organisations.organisation'),
        ),
    ]
