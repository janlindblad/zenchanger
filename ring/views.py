import json, base64
from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponse
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.utils.decorators import method_decorator
from django.utils.crypto import get_random_string
from django.shortcuts import get_object_or_404
from django.views import View
from django.template.loader import render_to_string
from .models import UserKey, RingKey, Ring, Secret

@require_GET
@require_GET
def create_magic_link(request):
    print(f"=== CREATE_MAGIC_LINK DEBUG ===")
    print(f"Request user: {request.user} (ID: {request.user.id})")
    print(f"User authenticated: {request.user.is_authenticated}")
    
    ring_id = request.GET.get('ring_id')
    print(f"Requested ring_id: {ring_id}")
    
    if not ring_id:
        return JsonResponse({'error': 'ring_id required'}, status=400)
    
    try:
        ring = Ring.objects.get(id=ring_id)
        print(f"Ring found: {ring.name} (ID: {ring.id})")
        
        # Check if user is a member with detailed logging
        try:
            ring_key = RingKey.objects.get(ring=ring, user=request.user)
            print(f"RingKey found: {ring_key}")
            print(f"RingKey details: Ring={ring_key.ring.id}, User={ring_key.user.id}")
            
            # Generate a unique token
            token = get_random_string(32)
            
            # Store the encrypted key in session with the token
            session_key = f'key_token_{token}'
            request.session[session_key] = ring_key.encrypted_key
            
            # Create the magic link
            base_url = request.build_absolute_uri('/')
            magic_link = f"{base_url}ring/import_key/?token={token}"
            
            print(f"Generated magic link: {magic_link}")
            
            return JsonResponse({'link': magic_link})
            
        except RingKey.DoesNotExist:
            print(f"RingKey NOT found for ring={ring_id}, user={request.user.id}")
            
            # Let's see what RingKeys DO exist for this ring
            existing_keys = RingKey.objects.filter(ring=ring)
            print(f"Existing RingKeys for ring {ring_id}:")
            for rk in existing_keys:
                print(f"  User {rk.user.id} ({rk.user.username})")
                
            return JsonResponse({'error': 'You are not member of this ring.'}, status=400)
        
    except Ring.DoesNotExist:
        return JsonResponse({'error': 'Ring not found'}, status=404)
    
@require_GET
def get_encrypted_key(request):
    token = request.GET.get('token')
    encrypted_key = request.session.pop(f'key_token_{token}', None)
    if not encrypted_key:
        return HttpResponseBadRequest("Invalid or expired token")

    return JsonResponse({"encrypted_key": encrypted_key})

@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(login_required, name='dispatch')
class StorePublicKeyView(View):
    def post(self, request):
        data = json.loads(request.body)
        pubkey = data.get('public_key')
        if not pubkey:
            return HttpResponseBadRequest("Missing public key")

        UserKey.objects.update_or_create(user=request.user, defaults={"public_key": json.dumps(pubkey)})
        return JsonResponse({"status": "success"})

def register_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, 'Account created successfully! Please generate your keypair.')
            login(request, user)  # Log the user in after registration
            return render(request, 'ring/register_complete.html', {'user': user})
    else:
        form = UserCreationForm()
    
    return render(request, 'ring/register.html', {'form': form})

@login_required
def get_user_public_key(request):
    print(f"=== get_user_public_key called ===")
    print(f"User authenticated: {request.user.is_authenticated}")
    print(f"User: {request.user}")
    print(f"Request method: {request.method}")
    print(f"Request path: {request.path}")
    
    try:
        user_key = UserKey.objects.get(user=request.user)
        print(f"Found user key for {request.user}")
        response_data = {'public_key': user_key.public_key}
        print(f"Returning successful response")
        return JsonResponse(response_data)
    except UserKey.DoesNotExist:
        print(f"No UserKey found for user {request.user.id}")
        error_response = JsonResponse({'error': f'No public key found for user {request.user.id}'}, status=404)
        print(f"Returning 404 response")
        return error_response
    except Exception as e:
        print(f"Unexpected error: {e}")
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def get_ring_key(request, ring_id):
    try:
        ring_key = RingKey.objects.get(ring_id=ring_id, user=request.user)
        return JsonResponse({'encrypted_key': ring_key.encrypted_key})
    except RingKey.DoesNotExist:
        return JsonResponse({'error': 'Ring key not found'}, status=404)
    
    from django.shortcuts import render, redirect

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

@login_required
def get_ring_key(request, ring_id):
    try:
        ring_key = RingKey.objects.get(ring_id=ring_id, user=request.user)
        return JsonResponse({'encrypted_key': ring_key.encrypted_key})
    except RingKey.DoesNotExist:
        return JsonResponse({'error': 'Ring key not found'}, status=404)
    




    # Temporarily add this to your ring/views.py for debugging
from django.conf import settings
from django.urls import get_resolver

def debug_urls(request):
    urlconf = __import__(settings.ROOT_URLCONF, {}, {}, [''])
    resolver = get_resolver(urlconf)
    
    def list_urls(lis, acc=None):
        if acc is None:
            acc = []
        if not lis:
            return
        l = lis[0]
        if hasattr(l, 'url_patterns'):
            list_urls(l.url_patterns, acc)
        else:
            acc.append(l.pattern.regex.pattern)
        list_urls(lis[1:], acc)
        return acc
    
    patterns = list_urls(resolver.url_patterns)
    return JsonResponse({'urls': patterns})