from django.urls import path

from .views import CityViewSet, CoffeeShopViewSet

urlpatterns = [
    path('list_shop/', CoffeeShopViewSet.as_view()),
    path('list_city/', CityViewSet.as_view()),
]
