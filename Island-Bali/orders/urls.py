from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    view_orders, 
    CheckoutView, 
    get_status_payment_for_cart, 
    OrderViewSet, 
    NotificationViewSet, 
    OrderStatusUpdateView, 
    PaymentView,
    CheckOrderViewSet,
    UpdateThankYouDialogView,
    UpdateOrderCancelledView
)

# Создаем роутер для ViewSets
router = DefaultRouter()
router.register('orders', OrderViewSet, basename='orders')
router.register('notifications', NotificationViewSet, basename='notifications')
router.register('check_orders', CheckOrderViewSet, basename='check_orders')

urlpatterns = [
    path('', include(router.urls)),
    path('orders/view/', view_orders, name='view_orders'),
    path('checkout/', CheckoutView.as_view(), name='checkout'),
    path('payment/status/', get_status_payment_for_cart, name='payment_status'),
    path('orders/<int:pk>/status/', OrderStatusUpdateView.as_view(), name='order_status_update'),
    path('orders/<int:pk>/pay/', PaymentView.as_view(), name='order_pay'),
    path('update-thank-you-dialog/<int:order_id>/', UpdateThankYouDialogView.as_view(), name='update_thank_you_dialog'),
    path('update-order-cancelled/<int:order_id>/', UpdateOrderCancelledView.as_view(), name='update_order_cancelled'),
]
