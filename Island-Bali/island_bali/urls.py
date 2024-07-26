from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView

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
    # permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/token/refresh/", TokenRefreshView.as_view(),
         name="token_refresh"),
    path("api/token/verify/", TokenVerifyView.as_view(), name="token_verify"),
    path("api/users/", include("users.urls")),
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

    # Добавьте URL для Swagger
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0),
         name='schema-swagger-ui'),

    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0),
         name='schema-redoc'),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL,
                          document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL,
                          document_root=settings.MEDIA_ROOT)
