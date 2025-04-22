from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    CategoryViewSet, ProductListInCategory, ProductViewSet,
    WeatherView, SeasonMenuViewSet, AddonList,
    AdditiveFlavorsList
)

router = DefaultRouter()
router.register(r'season-menus', SeasonMenuViewSet)

urlpatterns = [
    path("categories/", CategoryViewSet.as_view(), name='categories'),
    path("menu/", ProductViewSet.as_view(), name='menu'),
    path('categories/<int:id>/products/', ProductListInCategory.as_view(),
         name='category-products'),
    path('weather/', WeatherView.as_view(), name='weather'),
    path('', include(router.urls)),
    path('api/addons/', AddonList.as_view(), name='addon-list'),
    path('api/additive_flavors/', AdditiveFlavorsList.as_view(),
         name='additive-flavors-list'),
    
]