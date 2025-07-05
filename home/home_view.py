from django.shortcuts import render
from core.models import Organization

def my_organizations(request):
    if not request.user.is_authenticated:
        return render(request, "home/home.html", {"organizations": None})
    organizations = Organization.objects.filter(admins=request.user)
    return render(request, "home/home.html", {"organizations": organizations})