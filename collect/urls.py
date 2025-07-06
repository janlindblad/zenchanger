from django.urls import path
from .source_view import source_view
from .trigger_view import run_collect_plugin, run_collect_all

urlpatterns = [
    path('', source_view, name='source_view'),
    path('all/', run_collect_all, name='run_collect_all'),
    path('trig/<str:source_id>/', run_collect_plugin, name='run_collect_plugin'),
]