from django.urls import path

from .views import (
    AddToCartView, ChangeQuantityView, RemoveFromCartView,
    ViewCartView, DeactivateCartView
)

urlpatterns = [
    path(
        'add_to_cart/<str:city_name>/<str:street_name>/',
        AddToCartView.as_view(),
        name='add_to_cart'
    ),
    path('change_quantity/', ChangeQuantityView.as_view(),
         name='change_quantity'),
    path('remove_from_cart/', RemoveFromCartView.as_view(),
         name='remove_from_cart'),
    path('view_cart/', ViewCartView.as_view(), name='view_cart'),
    path('deactivate_cart/', DeactivateCartView.as_view(),
         name='deactivate_cart'
    ),
]
