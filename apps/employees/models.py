from django.db import models


class Employee(models.Model):
    employee_id = models.CharField(max_length=50, unique=True)
    full_name = models.CharField(max_length=200)
    alias_name = models.CharField(max_length=100, blank=True)
    official_email = models.EmailField(unique=True)
    contact_number = models.CharField(max_length=20)
    core_process = models.CharField(max_length=200)
    designation = models.CharField(max_length=200, blank=True)
    line_manager = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL, related_name='subordinates'
    )
    is_active = models.BooleanField(default=True)
    date_of_joining = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'employees'
        ordering = ['full_name']

    def __str__(self):
        return f'{self.full_name} ({self.employee_id})'
