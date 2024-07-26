from django.urls import path

from orders import views
from orders.views import CreateOrderView

urlpatterns = [
    path('create_order/', CreateOrderView.as_view(), name='create_order'),
    path('view_orders/', views.view_orders, name='view-orders'),
    path('payment_order/', views.CheckoutView.as_view(), name='checkout'),
    path('get-status-payment/',
         views.get_status_payment_for_cart, name='get_status_payment'),
]
