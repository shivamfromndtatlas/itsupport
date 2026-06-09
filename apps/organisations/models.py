from django.db import models


class Organisation(models.Model):
    name = models.CharField(max_length=255, unique=True)
    logo = models.ImageField(upload_to='organisation_logos/', blank=True, null=True)
    address = models.TextField()
    city = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    is_base = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'organisations'
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({"Base" if self.is_base else "Client"})'

    def save(self, *args, **kwargs):
        if self.is_base and Organisation.objects.filter(is_base=True).exclude(pk=self.pk).exists():
            raise ValueError('Only one base organisation is allowed.')
        super().save(*args, **kwargs)


class OrganisationMemberProfile(models.Model):
    organisation = models.ForeignKey(
        Organisation,
        on_delete=models.CASCADE,
        related_name='member_profiles',
    )
    employee = models.ForeignKey(
        'employees.Employee',
        on_delete=models.CASCADE,
        related_name='organisation_profiles',
    )
    employee_code = models.CharField(max_length=50, blank=True)
    full_name = models.CharField(max_length=200, blank=True)
    alias_name = models.CharField(max_length=100, blank=True)
    official_email = models.EmailField(blank=True)
    contact_number = models.CharField(max_length=20, blank=True)
    designation = models.CharField(max_length=200, blank=True)
    core_process_code = models.CharField(max_length=10, blank=True)
    date_of_joining = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'organisation_member_profiles'
        unique_together = ('organisation', 'employee')
        ordering = ['employee__full_name']

    def __str__(self):
        return f'{self.employee} profile for {self.organisation}'
