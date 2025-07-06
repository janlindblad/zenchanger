from django.shortcuts import render, get_object_or_404, redirect
from .models import Source
from .collect_base import Collector

def source_view(request):
    if request.method == "POST":
        source_id = request.POST.get("source_id")
        action = request.POST.get("action")
        source = get_object_or_404(Source, id=source_id)
        if action == "collect":
            Collector.dispatch(source)
        elif action == "clear":
            Collector.dispatch(source, ops=["clear"])
        return redirect("source_view")

    sources = Source.objects.all()
    source_data = []
    for source in sources:
        records = source.records.order_by('-timestamp')[:6]
        source_data.append({
            "isrc": source,
            "irec": records,
        })
    return render(request, "collect/source_view.html", {"source_data": source_data})
