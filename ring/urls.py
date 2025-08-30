from django.urls import path
from .views import StorePublicKeyView, get_user_public_key, get_ring_key
from .views import debug_urls

urlpatterns = [
    path('store_public_key/', StorePublicKeyView.as_view(), name='store_public_key'),
    path('get_user_public_key/', get_user_public_key, name='get_user_public_key'),
    path('get_ring_key/<int:ring_id>/', get_ring_key, name='get_ring_key'),
    path('debug_urls/', debug_urls, name='debug_urls'),  # Add this line

]
