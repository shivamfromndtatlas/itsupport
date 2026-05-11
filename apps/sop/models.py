from django.db import models


class SOPCategory(models.Model):
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'sop_categories'
        verbose_name = 'SOP Category'

    def __str__(self):
        return self.name


class SOP(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.ForeignKey(SOPCategory, on_delete=models.CASCADE, related_name='sops')
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, related_name='created_sops')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sops'

    def __str__(self):
        return self.name


class SOPStep(models.Model):
    STEP_TYPE_CHOICES = [
        ('manual', 'Manual'),
        ('automated', 'Automated'),
        ('checklist', 'Checklist'),
        ('approval', 'Approval'),
    ]

    sop = models.ForeignKey(SOP, on_delete=models.CASCADE, related_name='steps')
    step_number = models.PositiveIntegerField()
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    step_type = models.CharField(max_length=20, choices=STEP_TYPE_CHOICES, default='action')
    is_required = models.BooleanField(default=True)
    responsible_role = models.CharField(max_length=50, blank=True)

    class Meta:
        db_table = 'sop_steps'
        ordering = ['step_number']

    def __str__(self):
        return f'{self.sop.name} - Step {self.step_number}: {self.title}'


class SOPChecklistItem(models.Model):
    step = models.ForeignKey(SOPStep, on_delete=models.CASCADE, related_name='checklist_items')
    item_text = models.CharField(max_length=500)
    is_required = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'sop_checklist_items'
        ordering = ['order']

    def __str__(self):
        return self.item_text


class SOPExecution(models.Model):
    STATUS_CHOICES = [
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    sop = models.ForeignKey(SOP, on_delete=models.CASCADE, related_name='executions')
    reference_type = models.CharField(max_length=100, blank=True)
    reference_id = models.PositiveIntegerField(null=True, blank=True)
    current_step = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='in_progress')
    started_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, related_name='sop_executions')
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'sop_executions'

    def __str__(self):
        return f'{self.sop.name} - {self.status}'


class SOPStepCompletion(models.Model):
    execution = models.ForeignKey(SOPExecution, on_delete=models.CASCADE, related_name='step_completions')
    step = models.ForeignKey(SOPStep, on_delete=models.CASCADE)
    completed_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True)
    completed_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)
    checklist_data = models.JSONField(default=dict)

    class Meta:
        db_table = 'sop_step_completions'
        unique_together = ['execution', 'step']
