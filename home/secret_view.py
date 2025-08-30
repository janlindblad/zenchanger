from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from ring.models import Ring, RingKey, Secret

@login_required
def secret_view(request):
    # Handle POST request for adding new secret
    if request.method == 'POST':
        ring_id = request.POST.get('ring_id')
        encrypted_content = request.POST.get('encrypted_content')
        
        if ring_id and encrypted_content:
            try:
                ring = Ring.objects.get(id=ring_id)
                
                # Check if user is a member of this ring
                if RingKey.objects.filter(ring=ring, user=request.user).exists():
                    Secret.objects.create(
                        ring=ring,
                        content=encrypted_content
                    )
                    messages.success(request, f'Secret added to {ring.name}!')
                else:
                    messages.error(request, 'You are not a member of this ring.')
                    
            except Ring.DoesNotExist:
                messages.error(request, 'Ring not found.')
        else:
            messages.error(request, 'Ring and content are required.')
            
        return redirect('secret_view')
    
    # Get all secrets
    all_secrets = Secret.objects.select_related('ring').order_by('-created_at')
    
    # Get rings where user is a member
    user_rings = Ring.objects.filter(ringkey__user=request.user).distinct()
    
    # Get user's ring keys for decryption
    user_ring_keys = {
        rk.ring.id: rk.encrypted_key 
        for rk in RingKey.objects.filter(user=request.user).select_related('ring')
    }
    
    return render(request, 'home/secret_view.html', {
        'all_secrets': all_secrets,
        'user_rings': user_rings,
        'user_ring_keys': user_ring_keys
    })
