from django.urls import path
from .login_view import CustomLoginView, logout_view
from .setup_view import setup_db
from .home_view import home_view
from .register_view import register_view
from .ring_view import ring_view, ring_add_view

urlpatterns = [
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', logout_view, name='logout'),
    path('register/', register_view, name='register'),

    path('setup-db/', setup_db, name='setup_db'),
    path('home/', home_view, name='home'),
    path('rings/', ring_view, name='ring_view'),
    path('rings/<int:ring_id>/add/', ring_add_view, name='ring_add_view'),
]
