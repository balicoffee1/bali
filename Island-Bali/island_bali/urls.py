from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView

from acquiring.views import (
    RussianStandardPaymentView, RussianStandardCheckPaymentView, AlphaCreatePaymentOrderView, \
    AlphaGetPaymentStatusView, TBCreateOrderView, TBGetOrderView, RSBTransactionView, SBPPaymentCreateView,
    create_invoice, lifepay_callback, get_lifepay_invoice_view, LifePayCallbackView
)

admin.site.site_header = 'Кофейня'
admin.site.site_title = 'Администрирование кофейни'
admin.site.index_title = 'Администрирование кофейни'

schema_view = get_schema_view(
    openapi.Info(
        title="API Island Bali",
        default_version='v1',
        description="API кофейни",
        terms_of_service="http://178.20.40.50/",
        contact=openapi.Contact(email="contact@example.com"),
        license=openapi.License(name="Apache License, Version 2.0"),
    ),
    public=True,
)

urlpatterns = [
    # Админка
    path("admin/", admin.site.urls),

    # Аутентификация
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/token/verify/", TokenVerifyView.as_view(), name="token_verify"),

    # Основные приложения
    path("api/users/", include("users.urls"), name="orders"),
    path("api/orders/", include("orders.urls")),
    path("api/coffee_shop/", include("coffee_shop.urls")),
    path("api/cart/", include("cart.urls")),
    path("api/menu_coffee_product/", include("menu_coffee_product.urls")),
    path("api/franchise/", include("franchise.urls")),
    path("api/bonus_system/", include("bonus_system.urls")),
    path("api/ref_system/", include("ref_system.urls")),
    path("api/staff/", include("staff.urls")),
    path("api/review/", include("reviews.urls")),
    path("api/music/", include("music_api.urls")),
    path("api/sub_total/", include("subtotal_api.urls")),
    path('api/quick-resto/', include("quickresto.urls")),
    path('api/seo/', include("seo.urls")),

    # Swagger
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),

    # Эквайринг
    path('api/payment/russian-standard/create/<int:coffee_shop_id>/', RussianStandardPaymentView.as_view(), name='create-payment'),
    path('api/payment/russian-standard/status/<int:coffee_shop_id>/<int:invoice_id>/', RussianStandardCheckPaymentView.as_view(), name='check-payment-status'),
    path('api/payment/alpha/create/<int:coffee_shop_id>/', AlphaCreatePaymentOrderView.as_view(), name='alpha-create-payment'),
    path('api/payment/alpha/status/<int:coffee_shop_id>/<str:external_id>/', AlphaGetPaymentStatusView.as_view(), name='alpha-payment-status'),
    path('api/payment/tinkoff/create/<int:coffee_shop_id>/', TBCreateOrderView.as_view(), name='tinkoff-create-order'),
    path('api/payment/tinkoff/order/<int:coffee_shop_id>/<str:order_id>/', TBGetOrderView.as_view(), name='tinkoff-get-order'),
    path('api/payment/rsb/transaction/<int:coffee_shop_id>/', RSBTransactionView.as_view(), name='rsb-transaction'),
    
    path('api/payment/sbp/<int:order_id>/', SBPPaymentCreateView.as_view(), name='sbp-create-payment'),
    path('create-invoice/', create_invoice, name='create-invoice'),
    path('lifepay-callback/', lifepay_callback, name='lifepay-callback'),
    path('lifepay-invoice/', get_lifepay_invoice_view, name='lifepay-invoice'),
    path("api/lifepay/callback/", LifePayCallbackView.as_view(), name="lifepay-callback"),
]

# Статические и медиафайлы в режиме DEBUG
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
