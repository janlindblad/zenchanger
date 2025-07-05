from django.shortcuts import render
from core.models import Organization

def my_Organizations(request):
    if not request.user.is_authenticated:
        return render(request, "home/home.html", {"Organizations": None})
    Organizations = Organization.objects.filter(admins=request.user)
    return render(request, "home/home.html", {"Organizations": Organizations})