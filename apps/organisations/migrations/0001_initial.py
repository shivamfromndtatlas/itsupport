from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Organisation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, unique=True)),
                ('logo', models.ImageField(blank=True, null=True, upload_to='organisation_logos/')),
                ('address', models.TextField()),
                ('city', models.CharField(max_length=100)),
                ('country', models.CharField(max_length=100)),
                ('is_base', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'organisations',
                'ordering': ['name'],
            },
        ),
    ]
