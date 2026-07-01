from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0005_asset_location_backfill'),
    ]

    operations = [
        migrations.CreateModel(
            name='AssetTypeAttributeRequirement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('requirement', models.CharField(choices=[('mandatory', 'Mandatory'), ('optional', 'Optional'), ('hidden', 'Hidden')], default='optional', max_length=20)),
                ('notes', models.CharField(blank=True, max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('attribute', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='type_requirements', to='inventory.assetattribute')),
                ('asset_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attribute_requirements', to='inventory.assettype')),
            ],
            options={
                'db_table': 'asset_type_attribute_requirements',
                'ordering': ['asset_type__name', 'attribute__name'],
                'unique_together': {('asset_type', 'attribute')},
            },
        ),
    ]
