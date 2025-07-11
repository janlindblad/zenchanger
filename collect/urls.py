from django.urls import path
from .source_view import source_view
from .location_view import location_view, location_detail
from .trigger_view import run_collect_plugin, run_collect_all

urlpatterns = [
    path('', source_view, name='source_view'),
    path('all/', run_collect_all, name='run_collect_all'),
    path('trig/<str:source_id>/', run_collect_plugin, name='run_collect_plugin'),
    path('location/', location_view, name='location_view'),
    path('location/<int:pk>/', location_detail, name='location_detail'),
]