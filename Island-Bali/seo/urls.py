from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ColorModelViewSet

router = DefaultRouter()
router.register(r'color', ColorModelViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
