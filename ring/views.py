import json, base64
from django.shortcuts import render
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
from .models import UserKey, RingKey

@require_GET
@login_required
def create_magic_link(request):
    user = request.user
    ring_id = request.GET.get('ring_id')
    ring_key_obj = get_object_or_404(RingKey, ring=ring_id, user=user.id)
    if not ring_key_obj.encrypted_key:
        return HttpResponseBadRequest("You are not member of this ring.")

    token = get_random_string(48)
    request.session[f'key_token_{token}'] = ring_key_obj.encrypted_key
    return JsonResponse({"link": f"https://yourdomain.com/import_key?token={token}"})

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
