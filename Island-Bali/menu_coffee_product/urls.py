from django.urls import path

from .views import (CategoryViewSet, ProductListInCategory, ProductViewSet,
                    WeatherView)

urlpatterns = [
    path("categories/", CategoryViewSet.as_view(), name='categories'),
    path("menu/", ProductViewSet.as_view(), name='menu'),
    path('categories/<int:id>/products/', ProductListInCategory.as_view(),
         name='category-products'),
    path('weather/', WeatherView.as_view(), name='weather'),

]
