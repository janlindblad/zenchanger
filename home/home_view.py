from django.shortcuts import render
from core.models import Organization, Event

def home_view(request):
    if not request.user.is_authenticated:
        return render(request, "home/home.html", {"events": None})
    organizations = Organization.objects.filter(stakeholders__user=request.user).distinct()
    events = Event.objects.filter(organizers__in=organizations).distinct()
    return render(request, "home/home.html", {"events": events})