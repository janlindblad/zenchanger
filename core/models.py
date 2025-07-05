from django.db import models
from django.contrib.auth.models import User
from simple_history.models import HistoricalRecords

class Country(models.Model):
    class Visibility(models.TextChoices):
        DEFAULT = "DEFT", "Default"
        NODETAILS = "NODE", "NoDetails"
        HIDDEN = "HIDE", "Hidden"

    code = models.CharField(max_length=3, primary_key=True)
    name = models.CharField(max_length=255, unique=True)
    visibility = models.CharField(
        max_length=4,
        choices=Visibility.choices,
        default=Visibility.DEFAULT
    )
    history = HistoricalRecords()

    def save(self, *args, **kwargs):
        self.name = self.name.lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name.title()}"

class Location(models.Model):
    name = models.CharField(max_length=255, unique=True)
    in_country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name='locations')
    in_location = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='sublocations')
    lat = models.FloatField()
    lon = models.FloatField()
    history = HistoricalRecords()

    def save(self, *args, **kwargs):
        self.name = self.name.lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name.title()} ({self.in_country.code})"

class Organization(models.Model):
    name = models.CharField(max_length=255)
    parent = models.ForeignKey('self', null=True, blank=True, related_name='children', on_delete=models.SET_NULL)
    admins = models.ManyToManyField(User, related_name='admin_Organization')
    history = HistoricalRecords()

    def __str__(self):
        return self.name

