from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('employees', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='employee',
            name='core_process_code',
            field=models.CharField(
                blank=True,
                choices=[
                    ('01AOS', 'AEIS Operating Process'),
                    ('02BDP', 'Business Development Process'),
                    ('03HRP', 'Peoples Process'),
                    ('04OPS', 'Operations Management Process'),
                    ('05QCP', 'Quality Assurance & Compliance Process'),
                    ('06TMP', 'Technology Management Process'),
                    ('07FIN', 'Finance Process'),
                    ('08TRD', 'Training & Development Process'),
                    ('09ILP', 'Innovation Lab Process'),
                ],
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name='employee',
            name='core_process_name',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.RemoveField(
            model_name='employee',
            name='core_process',
        ),
    ]
