from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json

def register_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, 'Account created successfully! Please generate your keypair.')
            login(request, user)  # Log the user in after registration
            return render(request, 'home/register_complete.html', {'user': user})
    else:
        form = UserCreationForm()
    
    return render(request, 'home/register.html', {'form': form})

@csrf_exempt
def store_public_key(request):
    if request.method == 'POST' and request.user.is_authenticated:
        try:
            data = json.loads(request.body)
            public_key = data.get('public_key')
            
            # Store the public key in user profile or create a separate model
            # For now, we'll store it in the user's profile (you may need to create a Profile model)
            request.user.profile.public_key = json.dumps(public_key)
            request.user.profile.save()
            
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    
    return JsonResponse({'status': 'error', 'message': 'Unauthorized'})