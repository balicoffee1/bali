from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    AdminAuthLoginView, AdminAuthMeView, AdminDashboardStatsView,
    AdminUsersViewSet, AdminCitiesViewSet, AdminCoffeeShopsViewSet,
    AdminCategoriesViewSet, AdminProductsViewSet, AdminAddonsViewSet, AdminAdditiveFlavorsViewSet,
    AdminOrdersViewSet, AdminStaffViewSet, AdminShiftsViewSet,
    AdminReviewsViewSet, AdminFranchiseRequestsViewSet, AdminDiscountCardsViewSet,
    AdminNotificationBroadcastView, AdminActivityLogViewSet
)

router = DefaultRouter()
router.register(r'users', AdminUsersViewSet, basename='admin-users')
router.register(r'cities', AdminCitiesViewSet, basename='admin-cities')
router.register(r'coffee-shops', AdminCoffeeShopsViewSet, basename='admin-coffee-shops')
router.register(r'categories', AdminCategoriesViewSet, basename='admin-categories')
router.register(r'products', AdminProductsViewSet, basename='admin-products')
router.register(r'addons', AdminAddonsViewSet, basename='admin-addons')
router.register(r'flavors', AdminAdditiveFlavorsViewSet, basename='admin-flavors')
router.register(r'orders', AdminOrdersViewSet, basename='admin-orders')
router.register(r'staff', AdminStaffViewSet, basename='admin-staff')
router.register(r'shifts', AdminShiftsViewSet, basename='admin-shifts')
router.register(r'reviews', AdminReviewsViewSet, basename='admin-reviews')
router.register(r'franchise-requests', AdminFranchiseRequestsViewSet, basename='admin-franchise-requests')
router.register(r'discount-cards', AdminDiscountCardsViewSet, basename='admin-discount-cards')
router.register(r'audit-logs', AdminActivityLogViewSet, basename='admin-audit-logs')

urlpatterns = [
    # Auth
    path('auth/login/', AdminAuthLoginView.as_view(), name='admin-auth-login'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='admin-auth-refresh'),
    path('auth/me/', AdminAuthMeView.as_view(), name='admin-auth-me'),

    # Dashboard stats
    path('dashboard/stats/', AdminDashboardStatsView.as_view(), name='admin-dashboard-stats'),

    # Push broadcasting
    path('notifications/broadcast/', AdminNotificationBroadcastView.as_view(), name='admin-notifications-broadcast'),

    # CRUD Viewsets
    path('', include(router.urls)),
]
