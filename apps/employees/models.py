from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

from .base_org_assignment import should_assign_base_org


class Employee(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('on_leave', 'On Leave'),
    ]

    CORE_PROCESS_CHOICES = [
        ('01AOS', 'AEIS Operating Process'),
        ('02BDP', 'Business Development Process'),
        ('03HRP', 'Peoples Process'),
        ('04OPS', 'Operations Management Process'),
        ('05QCP', 'Quality Assurance & Compliance Process'),
        ('06TMP', 'Technology Management Process'),
        ('07FIN', 'Finance Process'),
        ('08TRD', 'Training & Development Process'),
        ('09ILP', 'Innovation Lab Process'),
    ]

    employee_id = models.CharField(max_length=50, unique=True)
    full_name = models.CharField(max_length=200)
    alias_name = models.CharField(max_length=100, blank=True)
    client_email = models.EmailField(null=True, blank=True, unique=True)
    official_email = models.EmailField(unique=True)
    contact_number = models.CharField(max_length=20, blank=True)
    core_process_code = models.CharField(max_length=10, choices=CORE_PROCESS_CHOICES, blank=True)
    core_process_name = models.CharField(max_length=200, blank=True)
    designation = models.CharField(max_length=200, blank=True)
    line_manager = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL, related_name='subordinates'
    )
    organisations = models.ManyToManyField(
        'organisations.Organisation', blank=True, related_name='members'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    date_of_joining = models.DateField(null=True, blank=True)
    date_of_separation = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'employees'
        ordering = ['full_name']

    def __str__(self):
        return f'{self.full_name} ({self.employee_id})'


@receiver(post_save, sender=Employee)
def ensure_base_organisation_membership(sender, instance, created, **kwargs):
    if not should_assign_base_org():
        return

    if instance.organisations.count() == 0:
        from apps.organisations.models import Organisation

        base_org = Organisation.objects.filter(is_base=True).first()
        if base_org:
            instance.organisations.add(base_org)
