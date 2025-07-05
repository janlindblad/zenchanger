from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('home')  # Change 'home' to your desired redirect
        else:
            messages.error(request, 'Invalid username or password.')
    return render(request, 'home/login.html')

def logout_view(request):
    if request.method == "POST":
        logout(request)
        return render(request, "home/logout.html")
    return redirect("home")