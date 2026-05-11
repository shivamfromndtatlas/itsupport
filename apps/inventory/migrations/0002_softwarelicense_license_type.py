from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='softwarelicense',
            name='license_type',
            field=models.CharField(
                choices=[
                    ('perpetual', 'Perpetual'),
                    ('subscription', 'Subscription'),
                    ('trial', 'Trial'),
                    ('open_source', 'Open Source'),
                ],
                default='perpetual',
                max_length=20,
            ),
        ),
    ]
