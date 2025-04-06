from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView

from acquiring.views import (
    AlphaCreatePaymentOrderView,
    AlphaGetPaymentStatusView,
    TBCreateOrderView,
    TBGetOrderView,
    get_link,
    get_status_payment,
    RSBTransactionView
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
    path("api/applications/", include("applications.urls")),

    # Swagger
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),

    # Эквайринг
    path('api/alpha/<int:coffee_shop_id>/create-payment-order/', AlphaCreatePaymentOrderView.as_view(), name='create_payment_order'),
    path('api/alpha/<int:coffee_shop_id>/payment-status/<str:external_id>/', AlphaGetPaymentStatusView.as_view(), name='get_payment_status'),
    path('api/tinkoff/<int:coffee_shop_id>/create-order/', TBCreateOrderView.as_view(), name='create_order'),
    path('api/tinkoff/<int:coffee_shop_id>/order/<str:order_id>/', TBGetOrderView.as_view(), name='get_order'),
    path('api/rus_standart/<int:coffee_shop_id>/link/', get_link, name='get_link'),
    path('api/rus_standart/<int:coffee_shop_id>/status/<str:invoice_id>/', get_status_payment, name='get_status_payment'),
    path('api/rus_standart/<int:coffee_shop_id>/transaction/', RSBTransactionView.as_view(), name="payment_request"),
]

# Статические и медиафайлы в режиме DEBUG
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
