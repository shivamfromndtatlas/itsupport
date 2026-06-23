from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('inventory', '0002_softwarelicense_license_type'),
    ]

    operations = [
        migrations.CreateModel(
            name='InstalledAppReportImport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file_name', models.CharField(max_length=255)),
                ('imported_at', models.DateTimeField(auto_now_add=True)),
                ('device_count', models.PositiveIntegerField(default=0)),
                ('app_count', models.PositiveIntegerField(default=0)),
                ('imported_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='installed_app_report_imports', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'installed_app_report_imports',
                'ordering': ['-imported_at'],
            },
        ),
        migrations.CreateModel(
            name='InstalledApplication',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('device_name', models.CharField(max_length=200)),
                ('normalized_device_name', models.CharField(db_index=True, max_length=200)),
                ('application_package', models.TextField(blank=True)),
                ('application_name', models.TextField()),
                ('application_type', models.CharField(blank=True, max_length=100)),
                ('user_name', models.CharField(blank=True, max_length=200)),
                ('application_version', models.CharField(blank=True, max_length=200)),
                ('signature_key_hash', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('report_import', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='applications', to='inventory.installedappreportimport')),
            ],
            options={
                'db_table': 'installed_applications',
                'ordering': ['application_name'],
                'indexes': [models.Index(fields=['normalized_device_name'], name='installed_a_normali_58ad48_idx')],
            },
        ),
    ]
