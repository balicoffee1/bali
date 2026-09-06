from django.urls import path

from .views import get_discount_card_from_user, get_loyalty_status_for_user

urlpatterns = [
    path("", get_discount_card_from_user),
    path("loyalty/", get_loyalty_status_for_user, name="loyalty-status"),
]
