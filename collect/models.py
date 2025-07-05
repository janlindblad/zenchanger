from django.db import models
from simple_history.models import HistoricalRecords

class Source(models.Model):
    id = models.CharField(max_length=255, primary_key=True)
    url = models.URLField()
    settings = models.JSONField()
    plugin = models.CharField(max_length=255, default="disabled")
    history = HistoricalRecords()

    def __str__(self):
        return self.id

class Schedule(models.Model):
    source = models.ForeignKey(Source, on_delete=models.CASCADE, related_name='schedules')
    cron_expression = models.CharField(max_length=255)
    enabled = models.BooleanField(default=True)
    last_run = models.DateTimeField(null=True, blank=True)
    history = HistoricalRecords()

    def __str__(self):
        return f"Schedule for {self.source.id} - {'Enabled' if self.enabled else 'Disabled'}"

class Record(models.Model):
    source = models.ForeignKey(Source, on_delete=models.CASCADE, related_name='records')
    result = models.JSONField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Record from {self.source.id} at {self.timestamp}"