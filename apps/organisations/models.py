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
