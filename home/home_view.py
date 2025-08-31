from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from core.models import Organization, Event
from ring.models import Ring, RingKey

@login_required
def home_view(request):
    # Get existing events logic
    events = []  # Your existing events logic here
    
    # Get rings where user is a member
    user_rings = Ring.objects.filter(ringkey__user=request.user).distinct()
    
    # Add detailed debugging
    print(f"=== HOME VIEW DEBUG ===")
    print(f"Request user: {request.user} (ID: {request.user.id})")
    print(f"User authenticated: {request.user.is_authenticated}")
    print(f"User rings found: {list(user_rings.values('id', 'name'))}")
    
    # Check ring memberships more specifically
    for ring in user_rings:
        ring_key = RingKey.objects.filter(ring=ring, user=request.user).first()
        print(f"  Ring {ring.id} ({ring.name}): RingKey exists = {ring_key is not None}")
    
    return render(request, 'home/home.html', {
        'events': events,
        'user_rings': user_rings
    })