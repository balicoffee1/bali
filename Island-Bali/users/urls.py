from django.urls import path

from . import views
from . import qr_code_view
from users.views import ActivationView, RegisterFCMToken

app_name = "users"

urlpatterns = [
    path(
        "registration_get_code/",
        views.registration_get_code,
        name="registration_get_code",
    ),
    path("check_registration/", views.check_registration,
         name="check_registration"),
    path("get_or_create_user/", views.registration, name="get_or_create_user"),
    path("auth/", views.auth, name="authentication"),
    path("user_profile/", views.user_profile, name="user_profile"),
    path("change_photo/", views.change_photo, name="change_photo"),
    path("bank_cards/", views.BankCardManager.as_view(), name="bank-cards"),
    path("get_discount/<int:id_shop>/", views.get_discount_for_user,
         name="get_discount"),
    
    path("qr_code/", qr_code_view.GenerateQRCodeView.as_view(), name='qr_code'),
    path("activate/", ActivationView.as_view(), name='activate'),
    path("/fcm/register/", RegisterFCMToken.as_view()),
]
