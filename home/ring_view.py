from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse
from ring.models import Ring, RingKey, UserKey

@login_required
def ring_view(request):
    # Handle POST requests for creating new rings
    if request.method == 'POST':
        ring_name = request.POST.get('ring_name', '').strip()
        if ring_name:
            try:
                # Create new ring
                ring = Ring.objects.create(name=ring_name)
                
                # Add user as member of the ring
                RingKey.objects.create(
                    ring=ring,
                    user=request.user,
                    encrypted_key=""  # Will be populated when keys are generated
                )
                
                messages.success(request, f'Ring "{ring_name}" created successfully!')
                return redirect('ring_view')
            except Exception as e:
                messages.error(request, f'Error creating ring: {str(e)}')
        else:
            messages.error(request, 'Ring name cannot be empty')
    
    # Get rings where user is a member
    user_ring_keys = RingKey.objects.filter(user=request.user).select_related('ring')
    
    ring_data = []
    for ring_key in user_ring_keys:
        ring = ring_key.ring
        # Get all members of this ring
        members = User.objects.filter(ringkey__ring=ring).distinct()
        
        ring_data.append({
            'ring': ring,
            'members': members,
            'member_count': members.count()
        })
    
    return render(request, 'home/ring_view.html', {
        'ring_data': ring_data
    })

@login_required
def ring_add_view(request, ring_id):
    ring = get_object_or_404(Ring, id=ring_id)
    
    # Check if current user is a member of this ring
    if not RingKey.objects.filter(ring=ring, user=request.user).exists():
        messages.error(request, 'You must be a member of this ring to add others.')
        return redirect('ring_view')
    
    # Handle POST request for adding member
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        if user_id:
            try:
                user_to_add = User.objects.get(id=user_id)
                
                # Check if user already is a member
                if RingKey.objects.filter(ring=ring, user=user_to_add).exists():
                    messages.error(request, f'{user_to_add.username} is already a member of this ring.')
                else:
                    # Add user to ring
                    RingKey.objects.create(
                        ring=ring,
                        user=user_to_add,
                        encrypted_key=""  # Will be populated when keys are generated
                    )
                    messages.success(request, f'{user_to_add.username} has been added to {ring.name}!')
                    return redirect('ring_view')
                    
            except User.DoesNotExist:
                messages.error(request, 'Selected user not found.')
        else:
            messages.error(request, 'Please select a user to add.')
    
    # Get users that have UserKeys but are not members of this ring
    existing_member_ids = RingKey.objects.filter(ring=ring).values_list('user_id', flat=True)
    eligible_users = User.objects.filter(
        userkey__isnull=False  # Has a UserKey
    ).exclude(
        id__in=existing_member_ids  # Not already a member
    ).order_by('username')
    
    # Get current members for display
    current_members = User.objects.filter(ringkey__ring=ring).order_by('username')
    
    return render(request, 'home/ring_add.html', {
        'ring': ring,
        'eligible_users': eligible_users,
        'current_members': current_members
    })
