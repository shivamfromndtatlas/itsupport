from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('employees', '0005_alter_employee_contact_number'),
        ('organisations', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='OrganisationMemberProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('employee_code', models.CharField(blank=True, max_length=50)),
                ('full_name', models.CharField(blank=True, max_length=200)),
                ('alias_name', models.CharField(blank=True, max_length=100)),
                ('official_email', models.EmailField(blank=True, max_length=254)),
                ('contact_number', models.CharField(blank=True, max_length=20)),
                ('designation', models.CharField(blank=True, max_length=200)),
                ('core_process_code', models.CharField(blank=True, max_length=10)),
                ('date_of_joining', models.DateField(blank=True, null=True)),
                ('status', models.CharField(blank=True, max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('employee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='organisation_profiles', to='employees.employee')),
                ('organisation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='member_profiles', to='organisations.organisation')),
            ],
            options={
                'db_table': 'organisation_member_profiles',
                'ordering': ['employee__full_name'],
                'unique_together': {('organisation', 'employee')},
            },
        ),
    ]
