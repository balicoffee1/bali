from django.urls import path

from .views import get_discount_card_from_user

urlpatterns = [
    path("", get_discount_card_from_user),
]
