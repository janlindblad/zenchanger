import os
from django.shortcuts import render
from django.contrib.auth.models import User
from django.db import IntegrityError

def setup_db(request):
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