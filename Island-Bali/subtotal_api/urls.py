from django.urls import path

from subtotal_api.views import GetDiscountForUser

urlpatterns = [
    path('', GetDiscountForUser.as_view(), name='discount')
]
