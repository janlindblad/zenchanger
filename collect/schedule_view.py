from django.shortcuts import render

from django.shortcuts import render
from .models import Schedule

def schedule_view(request):
    schedules = Schedule.objects.select_related('source').prefetch_related('source__records').all()
    # For each schedule, get the last 3 records for its source
    schedule_data = []
    for schedule in schedules:
        records = schedule.source.records.order_by('-timestamp')[:3]
        schedule_data.append({
            "schedule": schedule,
            "source": schedule.source,
            "records": records,
        })
    return render(request, "collect/schedule.html", {"schedule_data": schedule_data})