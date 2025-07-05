from django.db import models
from django.contrib.auth.models import User
from simple_history.models import HistoricalRecords

# Create your models here.

class Organization(models.Model):
    name = models.CharField(max_length=255)
    parent = models.ForeignKey('self', null=True, blank=True, related_name='children', on_delete=models.SET_NULL)
    admins = models.ManyToManyField(User, related_name='admin_organizations')
    history = HistoricalRecords()

    def __str__(self):
        return self.name
