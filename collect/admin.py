from django.contrib import admin
from .models import Source, Schedule, Record

admin.site.register(Source)
admin.site.register(Schedule)
admin.site.register(Record)
