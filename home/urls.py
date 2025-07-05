from django.urls import path
from .login_view import login_view, logout_view
from .setup_view import setup_db
from .home_view import home_view

urlpatterns = [
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),

    path('setup-db/', setup_db, name='setup_db'),
    path('home/', home_view, name='home'),
]