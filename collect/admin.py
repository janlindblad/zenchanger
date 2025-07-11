from django.contrib import admin
from .models import Source, Record, LocationImportMapping

admin.site.register(Source)
admin.site.register(Record)
admin.site.register(LocationImportMapping)