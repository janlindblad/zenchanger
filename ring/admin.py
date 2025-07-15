from django.contrib import admin
from .models import Ring, RingKey, UserKey

admin.site.register(Ring)
admin.site.register(RingKey)
admin.site.register(UserKey)
