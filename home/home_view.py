from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from core.models import Organization, Event
from ring.models import Ring, RingKey

@login_required
def home_view(request):
    if not request.user.is_authenticated:
        return render(request, "home/home.html", {"events": None})
    organizations = Organization.objects.filter(stakeholders__user=request.user).distinct()
    events = Event.objects.filter(organizers__in=organizations).distinct()

    # Get rings where user is a member
    user_rings = Ring.objects.filter(ringkey__user=request.user).distinct()
    
    return render(request, 'home/home.html', {
        'events': events,
        'user_rings': user_rings
    })