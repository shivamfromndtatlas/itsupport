from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sop', '0002_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sopstep',
            name='step_type',
            field=models.CharField(
                choices=[
                    ('manual', 'Manual'),
                    ('automated', 'Automated'),
                    ('checklist', 'Checklist'),
                    ('approval', 'Approval'),
                ],
                default='manual',
                max_length=20,
            ),
        ),
    ]
