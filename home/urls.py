from django.urls import path
from .login_view import CustomLoginView, logout_view
from .setup_view import setup_db
from .home_view import home_view
from .register_view import register_view
from .ring_view import ring_view, ring_add_user_view
from .secret_view import secret_view
from .event_views import (
    event_list_view, event_create_view, event_detail_view, 
    event_edit_view, event_delete_view, location_events_view,
    get_locations_by_country, search_locations, search_organizations
)

urlpatterns = [
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', logout_view, name='logout'),
    path('register/', register_view, name='register'),
    path('setup-db/', setup_db, name='setup_db'),
    path('home/', home_view, name='home'),
    path('rings/', ring_view, name='ring_view'),
    path('rings/<int:ring_id>/add/', ring_add_user_view, name='ring_add_user_view'),
    path('secrets/', secret_view, name='secret_view'),
    
    # Event URLs
    path('events/', event_list_view, name='event_list'),
    path('events/create/', event_create_view, name='event_create'),
    path('events/<str:event_id>/', event_detail_view, name='event_detail'),
    path('events/<str:event_id>/edit/', event_edit_view, name='event_edit'),
    path('events/<str:event_id>/delete/', event_delete_view, name='event_delete'),
    path('locations/<int:location_id>/events/', location_events_view, name='location_events'),
    
    # AJAX endpoints
    path('api/locations-by-country/', get_locations_by_country, name='get_locations_by_country'),
    path('api/search-locations/', search_locations, name='search_locations'),
    path('api/search-organizations/', search_organizations, name='search_organizations'),
]
