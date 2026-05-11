from django.db import models


class NewJoinerRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('rejected', 'Rejected'),
    ]

    full_name = models.CharField(max_length=200)
    employee_id = models.CharField(max_length=50)
    contact_number = models.CharField(max_length=20)
    personal_email = models.EmailField()
    complete_address = models.TextField()
    designation = models.CharField(max_length=200)
    core_process = models.CharField(max_length=200)
    alias_name = models.CharField(max_length=100, blank=True)
    date_of_joining = models.DateField()
    line_manager = models.CharField(max_length=200)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    submitted_by = models.ForeignKey(
        'users.User', on_delete=models.SET_NULL, null=True, related_name='onboarding_requests'
    )
    confirmed_by = models.ForeignKey(
        'users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='confirmed_onboardings'
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'onboarding_requests'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.full_name} - {self.status}'
