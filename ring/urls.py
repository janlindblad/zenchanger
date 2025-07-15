from django.urls import path
from .views import StorePublicKeyView

urlpatterns = [
    path('store_public_key/', StorePublicKeyView.as_view(), name='store_public_key'),
]
