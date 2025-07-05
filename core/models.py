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
    history = HistoricalRecords()

    def __str__(self):
        return self.name

class Role(models.Model):
    name = models.CharField(max_length=255)
    history = HistoricalRecords()

    def __str__(self):
        return self.name

class Stakeholder(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='stakeholder_organizations')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='stakeholders')
    role = models.ForeignKey('Role', on_delete=models.CASCADE, related_name='stakeholders')
    history = HistoricalRecords()

    class Meta:
        unique_together = ('user', 'organization', 'role')

    def __str__(self):
        return f"{self.user.username} - {self.role.name} @ {self.organization.name}"

class Event(models.Model):
    id = models.CharField(max_length=255, primary_key=True)
    ext_data_src = models.CharField(max_length=255, null=True, blank=True)
    date = models.DateField()
    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name='events')
    location = models.ForeignKey(Location, null=True, blank=True, on_delete=models.SET_NULL, related_name='events')
    time_of_day = models.CharField(max_length=5)
    organizers = models.ManyToManyField(Organization, related_name='events')
    history = HistoricalRecords()

    def __str__(self):
        loc = f", {self.location}" if self.location else ""
        return f"Event on {self.date}{loc} in {self.country.code}"
