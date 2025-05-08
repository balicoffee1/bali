from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import ColorModelViewSet, MarkdownModelViewSet

router = DefaultRouter()
router.register(r'color', ColorModelViewSet)
router.register(r'markdown', MarkdownModelViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
