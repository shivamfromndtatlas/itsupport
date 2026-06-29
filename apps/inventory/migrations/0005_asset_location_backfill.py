from django.db import migrations, models
import django.db.models.deletion


def backfill_asset_location(apps, schema_editor):
    Organisation = apps.get_model('organisations', 'Organisation')
    OrganisationLocation = apps.get_model('organisations', 'OrganisationLocation')
    Asset = apps.get_model('inventory', 'Asset')

    base_org = Organisation.objects.filter(is_base=True).first()
    if not base_org:
        return

    location, _ = OrganisationLocation.objects.get_or_create(
        organisation=base_org,
        name='F91 Surajpur Location',
        defaults={
            'address': base_org.address or '',
            'city': base_org.city or '',
            'country': base_org.country or '',
            'notes': 'Default base asset location',
        },
    )

    Asset.objects.filter(asset_type__asset_type='hardware').update(
        organisation=base_org,
        location=location,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0004_rename_installed_a_normali_58ad48_idx_installed_a_normali_cadd36_idx_and_more'),
        ('organisations', '0003_add_organisation_location'),
    ]

    operations = [
        migrations.AddField(
            model_name='asset',
            name='location',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='assets',
                to='organisations.organisationlocation',
            ),
        ),
        migrations.RunPython(backfill_asset_location, migrations.RunPython.noop),
    ]
