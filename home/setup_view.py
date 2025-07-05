import os, pycountry
from django.shortcuts import render
from django.contrib.auth.models import User
from django.db import IntegrityError
from core.models import Country

def setup_db(request):
    if 'countries' in request.GET:
        return initialize_countries(request)
    elif 'superuser' in request.GET:
        return initialize_superuser(request)
    context = {}
    context['error'] = f"Unknown setup command."
    return render(request, 'home/setup_db.html', context)

def initialize_countries(request):
    context = {}
    for country in pycountry.countries:
        code = getattr(country, 'alpha_2', getattr(country, 'alpha_3', None))
        if code:
            Country.objects.get_or_create(
                code=code,
                defaults={'name': country.name}
            )
    context['success'] = f"{Country.objects.count()} Countries in database."
    return render(request, 'home/setup_db.html', context)

def initialize_superuser(request):
    username = os.environ.get('ZENCHANGER_SUPERUSER')
    password = os.environ.get('ZENCHANGER_SUPERPASS')
    context = {}
    if not username or not password:
        context['error'] = "Environment variables ZENCHANGER_SUPERUSER and ZENCHANGER_SUPERPASS must be set."
    else:
        try:
            User.objects.create_superuser(username=username, password=password, email='')
            context['success'] = f"Superuser '{username}' created successfully."
        except IntegrityError:
            context['error'] = f"Superuser '{username}' already exists."
        except Exception as e:
            context['error'] = str(e)
    return render(request, 'home/setup_db.html', context)