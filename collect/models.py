from django.db import models
from simple_history.models import HistoricalRecords

class Source(models.Model):
    id = models.CharField(max_length=255, primary_key=True)
    url = models.URLField()
    settings = models.JSONField()
    plugin = models.CharField(max_length=255, default="disabled")
    cron_expression = models.CharField(max_length=255, null=True, blank=True)
    enabled = models.BooleanField(default=True)
    last_run = models.DateTimeField(null=True, blank=True, editable=False)
    next_run = models.DateTimeField(null=True, blank=True, editable=False)
    history = HistoricalRecords()

    def __str__(self):
        return f"Source {self.id}"

class Record(models.Model):
    source = models.ForeignKey(Source, on_delete=models.CASCADE, related_name='records')
    result = models.JSONField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Record from {self.source.id} at {self.timestamp}"
    
class LocationImportMapping(models.Model):
    source = models.ForeignKey(Source, on_delete=models.CASCADE, related_name='location_mappings')
    imported_name = models.CharField(max_length=255)
    location = models.ForeignKey('core.Location', null=True, blank=True, on_delete=models.CASCADE, related_name='location_mappings')
    history = HistoricalRecords()

    class Meta:
        unique_together = ('source', 'imported_name')

    def __str__(self):
        return f"Mapping for {self.source}:{self.imported_name} to {self.location.name if self.location else 'None'}"