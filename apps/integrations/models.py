from django.db import models


class SureMDMConnection(models.Model):
    base_url = models.URLField(default='https://suremdm.42gears.com/api')
    username = models.CharField(max_length=200, blank=True)
    password = models.CharField(max_length=500, blank=True)
    api_key = models.CharField(max_length=500, blank=True)
    is_active = models.BooleanField(default=True)
    last_tested_at = models.DateTimeField(null=True, blank=True)
    last_test_status = models.CharField(max_length=20, blank=True)
    last_test_message = models.TextField(blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'suremdm_connections'

    def __str__(self):
        return f'SureMDM ({self.base_url})'
