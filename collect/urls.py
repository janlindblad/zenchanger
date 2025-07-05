from django.urls import path
from .schedule_view import schedule_view

urlpatterns = [
    path('', schedule_view, name='schedule'),
]