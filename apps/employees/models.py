from django.db import models


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
    official_email = models.EmailField(unique=True)
    contact_number = models.CharField(max_length=20)
    core_process_code = models.CharField(max_length=10, choices=CORE_PROCESS_CHOICES, blank=True)
    core_process_name = models.CharField(max_length=200, blank=True)
    designation = models.CharField(max_length=200, blank=True)
    line_manager = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL, related_name='subordinates'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    date_of_joining = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'employees'
        ordering = ['full_name']

    def __str__(self):
        return f'{self.full_name} ({self.employee_id})'
