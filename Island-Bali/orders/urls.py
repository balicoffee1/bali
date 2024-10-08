from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    view_orders, 
    CheckoutView, 
    get_status_payment_for_cart, 
    OrderViewSet, 
    NotificationViewSet, 
    OrderStatusUpdateView, 
    PaymentView
)

# Создаем роутер для ViewSets
router = DefaultRouter()
router.register(r'orders', OrderViewSet, basename='orders')
router.register(r'notifications', NotificationViewSet, basename='notifications')

urlpatterns = [
    # Маршруты для ViewSets
    path('', include(router.urls)),
    
    # Эндпоинты для отдельных APIViews и функций
    path('orders/view/', view_orders, name='view_orders'),
    path('checkout/', CheckoutView.as_view(), name='checkout'),
    path('payment/status/', get_status_payment_for_cart, name='payment_status'),
    path('orders/<int:pk>/status/', OrderStatusUpdateView.as_view(), name='order_status_update'),
    path('orders/<int:pk>/pay/', PaymentView.as_view(), name='order_pay'),
]
