import datetime
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
from cron_converter import Cron
from .models import Source, Record
from .collect_base import Collector

# Imports required for plugin registration to happen
from .collect_fffse import Collect_fffse 

@csrf_exempt
@require_GET
def run_collect_plugin(request, source_id):
    try:
        result = {}
        source = Source.objects.get(id=source_id)
        result = Collector.dispatch(source)
        Record.objects.create(
            source=source,
            result=result,
            timestamp=datetime.datetime.now(tz=datetime.timezone.utc)
        )
        source.last_run = datetime.datetime.now(tz=datetime.timezone.utc)
        source.save()
        return JsonResponse({"status": "success", "result": result})
    except Exception as e:
        Record.objects.create(
            source=source,
            result={"error": str(e)},
            timestamp=datetime.datetime.now(tz=datetime.timezone.utc)
        )
        return JsonResponse({"status": "error", "error": str(e)}, status=500)
    
def run_collect_all(request):
    for source in Source.objects.all():
        try:
            if not source.enabled:
                continue
            if source.plugin == "disabled":
                continue
            next_run = Cron(
                            source.cron_expression, 
                            start_date=datetime.datetime.now(tz=datetime.timezone.utc)
                        ).next()
            if source.next_run != next_run:
                source.next_run = next_run
                source.save()
                run_collect_plugin(request, source.id)
        except Exception as e:
            Record.objects.create(
                source=source,
                result={"error": str(e)},
                timestamp=datetime.now()
            )
    return JsonResponse({"status": "success", "message": "All plugins collected."})
