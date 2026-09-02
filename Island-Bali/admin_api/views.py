from datetime import timedelta
from decimal import Decimal
from django.db import models
from django.db.models import Count, Sum, Avg, Q
from django.shortcuts import get_object_or_404
from django.utils.timezone import now
from rest_framework import status, viewsets, permissions, filters
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken
from django_filters.rest_framework import DjangoFilterBackend

from users.models import CustomUser
from coffee_shop.models import City, CoffeeShop, CrmSystem, Acquiring
from menu_coffee_product.models import Category, Product, Addon, AdditiveFlavors
from orders.models import Orders, CheckOrder
from staff.models import Staff, Shift
from reviews.models import ReviewsCoffeeShop
from franchise.models import FranchiseRequest
from bonus_system.models import DiscountCard
from notifications.main import send_push_notification

from .models import AdminActivityLog
from .audit import log_admin_activity
from .permissions import (
    IsSuperAdmin, IsAdminRole, IsModeratorRole, IsAnyAdminUser,
    IsAdminOrReadOnly, IsModeratorOrReadOnly,
)
from .serializers import (
    AdminUserSerializer, AdminUserDetailSerializer,
    AdminCitySerializer, AdminCoffeeShopSerializer, AdminCrmSystemSerializer, AdminAcquiringSerializer,
    AdminCategorySerializer, AdminProductSerializer, AdminAddonSerializer, AdminAdditiveFlavorsSerializer,
    AdminOrderSerializer, AdminStaffSerializer, AdminShiftSerializer,
    AdminReviewSerializer, AdminFranchiseRequestSerializer, AdminDiscountCardSerializer,
    AdminActivityLogSerializer, AdminNotificationBroadcastSerializer
)


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 200


# -------------------------------------------------------------
# 1. AUTHENTICATION
# -------------------------------------------------------------
class AdminAuthLoginView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'admin_login'

    def post(self, request):
        login_input = request.data.get("login") or request.data.get("phone") or request.data.get("email")
        password = request.data.get("password")

        if not login_input or not password:
            return Response({"error": "Введите логин и пароль."}, status=status.HTTP_400_BAD_REQUEST)

        # Поиск пользователя по логину, телефону или email
        user = CustomUser.objects.filter(
            Q(login__iexact=login_input) | Q(phone_number__exact=login_input) | Q(email__iexact=login_input)
        ).first()

        # Единый ответ не позволяет подбирать зарегистрированные логины.
        if not user or not user.is_active or not user.check_password(password):
            return Response({"error": "Неверный логин или пароль."}, status=status.HTTP_401_UNAUTHORIZED)

        # Проверка прав доступа в панель
        has_admin_access = user.is_superuser or user.role in ['owner', 'admin', 'moderator', 'support']
        if not has_admin_access:
            return Response({"error": "У вас нет прав для доступа к Admin Panel."}, status=status.HTTP_403_FORBIDDEN)

        refresh = RefreshToken.for_user(user)
        refresh['role'] = user.role
        refresh['is_staff'] = user.is_staff
        refresh['is_superuser'] = user.is_superuser

        log_admin_activity(
            request,
            action='LOGIN',
            entity_name='CustomUser',
            entity_id=str(user.id),
            summary="Вход в админ-панель",
            actor=user,
        )

        return Response({
            "token": {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            "user": AdminUserSerializer(user).data,
            "permissions": {
                "is_super_admin": user.is_superuser or user.role == 'owner',
                "is_admin": user.is_superuser or user.role in ['owner', 'admin'],
                "is_moderator": user.is_superuser or user.role in ['owner', 'admin', 'moderator'],
                "is_support": user.is_superuser or user.role in ['owner', 'admin', 'support'],
            }
        }, status=status.HTTP_200_OK)


class AdminAuthMeView(APIView):
    permission_classes = [IsAnyAdminUser]

    def get(self, request):
        user = request.user
        return Response({
            "user": AdminUserSerializer(user).data,
            "permissions": {
                "is_super_admin": user.is_superuser or user.role == 'owner',
                "is_admin": user.is_superuser or user.role in ['owner', 'admin'],
                "is_moderator": user.is_superuser or user.role in ['owner', 'admin', 'moderator'],
                "is_support": user.is_superuser or user.role in ['owner', 'admin', 'support'],
            }
        })


# -------------------------------------------------------------
# 2. DASHBOARD & ANALYTICS
# -------------------------------------------------------------
class AdminDashboardStatsView(APIView):
    permission_classes = [IsModeratorRole]

    def get(self, request):
        today = now().date()
        coffee_shop_id = request.query_params.get('coffee_shop_id')
        city_id = request.query_params.get('city_id')

        orders_qs = Orders.objects.all()
        if coffee_shop_id:
            orders_qs = orders_qs.filter(coffee_shop_id=coffee_shop_id)
        if city_id:
            orders_qs = orders_qs.filter(city_choose_id=city_id)

        # Метрики за сегодня
        today_orders = orders_qs.filter(created_at__date=today)
        today_completed = today_orders.filter(status_orders="Completed")
        today_revenue = today_completed.aggregate(total=Sum('full_price'))['total'] or Decimal('0.00')
        today_canceled = today_orders.filter(status_orders="Canceled").count()
        today_total_count = today_orders.count()

        # Вчерашний день для сравнения
        yesterday = today - timedelta(days=1)
        yesterday_completed = orders_qs.filter(created_at__date=yesterday, status_orders="Completed")
        yesterday_revenue = yesterday_completed.aggregate(total=Sum('full_price'))['total'] or Decimal('0.00')

        revenue_growth = 0.0
        if yesterday_revenue > 0:
            revenue_growth = round(float((today_revenue - yesterday_revenue) / yesterday_revenue * 100), 1)

        # Общие показатели
        total_users = CustomUser.objects.count()
        new_users_today = CustomUser.objects.filter(is_active=True).count() # approx or registered today
        active_shifts = Shift.objects.filter(status_shift="Open").count()
        avg_check = today_completed.aggregate(avg=Avg('full_price'))['avg'] or Decimal('0.00')

        # Статистика за последние 7 дней (график)
        chart_data = []
        for i in range(6, -1, -1):
            day_date = today - timedelta(days=i)
            day_orders = orders_qs.filter(created_at__date=day_date)
            day_completed = day_orders.filter(status_orders="Completed")
            day_rev = day_completed.aggregate(total=Sum('full_price'))['total'] or Decimal('0.00')
            chart_data.append({
                "date": day_date.strftime("%d.%m"),
                "revenue": float(day_rev),
                "orders_count": day_orders.count(),
                "completed_count": day_completed.count(),
            })

        # Топ 5 популярных товаров
        top_products = Product.objects.filter(availability=True)[:5]
        top_products_data = [
            {"id": p.id, "name": p.product, "price": float(p.price or 0), "category": p.category.name if p.category else ""}
            for p in top_products
        ]

        # Недавние отзывы с низкой оценкой (≤ 3)
        recent_low_reviews = ReviewsCoffeeShop.objects.filter(evaluation__lte=3).order_by('-id')[:5]

        return Response({
            "kpi": {
                "today_revenue": float(today_revenue),
                "revenue_growth": revenue_growth,
                "today_orders_count": today_total_count,
                "today_completed_count": today_completed.count(),
                "today_canceled_count": today_canceled,
                "average_check": float(round(avg_check, 2)),
                "total_users": total_users,
                "active_shifts": active_shifts,
            },
            "chart_data": chart_data,
            "top_products": top_products_data,
            "low_rating_reviews_count": recent_low_reviews.count(),
        })


# -------------------------------------------------------------
# 3. USERS MANAGEMENT
# -------------------------------------------------------------
class AdminUsersViewSet(viewsets.ModelViewSet):
    queryset = CustomUser.objects.all().order_by('-id')
    serializer_class = AdminUserSerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['role', 'is_active', 'is_staff']
    search_fields = ['login', 'first_name', 'last_name', 'phone_number', 'email']
    ordering_fields = ['id', 'first_name', 'role']

    def get_serializer_class(self):
        if self.action in ['retrieve', 'update', 'partial_update']:
            return AdminUserDetailSerializer
        return AdminUserSerializer

    def perform_update(self, serializer):
        user = serializer.save()
        log_admin_activity(self.request, 'UPDATE', 'CustomUser', user.id, f"Обновлен профиль пользователя {user.login}")

    @action(detail=True, methods=['post'], permission_classes=[IsAdminRole])
    def toggle_block(self, request, pk=None):
        user = self.get_object()
        user.is_active = not user.is_active
        user.save()
        status_text = "разблокирован" if user.is_active else "заблокирован"
        log_admin_activity(request, 'STATUS_CHANGE', 'CustomUser', user.id, f"Пользователь {user.login} {status_text}")
        return Response({"status": f"Пользователь успешно {status_text}", "is_active": user.is_active})

    @action(detail=True, methods=['post'], permission_classes=[IsSuperAdmin])
    def set_role(self, request, pk=None):
        user = self.get_object()
        new_role = request.data.get("role")
        if new_role not in [c[0] for c in CustomUser.ROLE_CHOICES]:
            return Response({"error": f"Недопустимая роль. Доступные: {[c[0] for c in CustomUser.ROLE_CHOICES]}"}, status=400)
        old_role = user.role
        user.role = new_role
        user.is_staff = new_role in ['owner', 'admin']
        user.save()
        log_admin_activity(request, 'UPDATE', 'CustomUser', user.id, f"Смена роли с {old_role} на {new_role}", changes={"old": old_role, "new": new_role})
        return Response({"status": "Роль успешно изменена", "role": user.role})


# -------------------------------------------------------------
# 4. COFFEE SHOPS & CITIES
# -------------------------------------------------------------
class AdminCitiesViewSet(viewsets.ModelViewSet):
    queryset = City.objects.all().order_by('name')
    serializer_class = AdminCitySerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name']


class AdminCoffeeShopsViewSet(viewsets.ModelViewSet):
    queryset = CoffeeShop.objects.all().order_by('id')
    serializer_class = AdminCoffeeShopSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['city']
    search_fields = ['street', 'building_number', 'email', 'phone_number']

    def perform_create(self, serializer):
        shop = serializer.save()
        log_admin_activity(self.request, 'CREATE', 'CoffeeShop', shop.id, f"Создана кофейня {shop}")

    def perform_update(self, serializer):
        shop = serializer.save()
        log_admin_activity(self.request, 'UPDATE', 'CoffeeShop', shop.id, f"Обновлена кофейня {shop}")

    def perform_destroy(self, instance):
        log_admin_activity(self.request, 'DELETE', 'CoffeeShop', instance.id, f"Удалена кофейня {instance}")
        instance.delete()


# -------------------------------------------------------------
# 5. MENU, CATEGORIES, PRODUCTS, ADDONS
# -------------------------------------------------------------
class AdminCategoriesViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all().order_by('id')
    serializer_class = AdminCategorySerializer
    permission_classes = [IsModeratorOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['coffee_shop', 'which_menu']
    search_fields = ['name']

    def perform_create(self, serializer):
        cat = serializer.save()
        log_admin_activity(self.request, 'CREATE', 'Category', cat.id, f"Создана категория {cat.name}")

    def perform_update(self, serializer):
        cat = serializer.save()
        log_admin_activity(self.request, 'UPDATE', 'Category', cat.id, f"Обновлена категория {cat.name}")


class AdminProductsViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all().order_by('id')
    serializer_class = AdminProductSerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = [IsModeratorOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['coffee_shop', 'category', 'availability', 'product_type', 'which_menu']
    search_fields = ['product']
    ordering_fields = ['id', 'product', 'price', 'availability']

    def perform_create(self, serializer):
        prod = serializer.save()
        log_admin_activity(self.request, 'CREATE', 'Product', prod.id, f"Создан товар {prod.product}")

    def perform_update(self, serializer):
        prod = serializer.save()
        log_admin_activity(self.request, 'UPDATE', 'Product', prod.id, f"Обновлен товар {prod.product}")

    @action(detail=True, methods=['post'])
    def toggle_availability(self, request, pk=None):
        prod = self.get_object()
        prod.availability = not prod.availability
        prod.save()
        status_text = "в наличии" if prod.availability else "в стоп-листе"
        log_admin_activity(request, 'STATUS_CHANGE', 'Product', prod.id, f"Товар {prod.product} переведен в статус: {status_text}")
        return Response({"status": f"Товар теперь {status_text}", "availability": prod.availability})


class AdminAddonsViewSet(viewsets.ModelViewSet):
    queryset = Addon.objects.all().order_by('id')
    serializer_class = AdminAddonSerializer
    permission_classes = [IsModeratorOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['coffee_shop']
    search_fields = ['name']


class AdminAdditiveFlavorsViewSet(viewsets.ModelViewSet):
    queryset = AdditiveFlavors.objects.all().order_by('name')
    serializer_class = AdminAdditiveFlavorsSerializer
    permission_classes = [IsModeratorOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['coffee_shop']
    search_fields = ['name']


# -------------------------------------------------------------
# 6. ORDERS & LIVE DESK
# -------------------------------------------------------------
class AdminOrdersViewSet(viewsets.ModelViewSet):
    queryset = Orders.objects.all().order_by('-created_at').select_related('user', 'city_choose', 'coffee_shop', 'staff', 'cart')
    serializer_class = AdminOrderSerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status_orders', 'payment_status', 'coffee_shop', 'city_choose', 'issued']
    search_fields = ['id', 'user__login', 'user__first_name', 'user__phone_number']
    ordering_fields = ['id', 'created_at', 'full_price']

    @action(detail=True, methods=['patch'])
    def update_status(self, request, pk=None):
        """
        M1 п.23: единственный путь изменения status_orders/payment_status из
        админки — OrderStateService.admin_override. Раньше писал поля
        напрямую (`order.status_orders = new_status; order.save()`), без
        select_for_update/atomic и без проверки допустимости перехода (можно
        было, например, вернуть Completed-заказ обратно в Waiting) — audit
        log при этом уже писался (log_admin_activity), поэтому сохранена та
        же обязательность причины при отмене, но сама мутация теперь идёт
        через сервис, который и делает audit-запись сам.
        """
        order = self.get_object()
        new_status = request.data.get("status_orders")
        new_payment_status = request.data.get("payment_status")
        cancellation_reason = request.data.get("cancellation_reason", "")
        reason = request.data.get("reason") or cancellation_reason

        if not new_status and not new_payment_status:
            return Response({"error": "Укажите status_orders и/или payment_status"}, status=400)
        if new_status == Orders.CANCELED and not cancellation_reason.strip():
            return Response({"error": "Для отмены укажите причину."}, status=status.HTTP_400_BAD_REQUEST)
        if not reason or not reason.strip():
            return Response({"error": "Для admin override обязательна причина (reason)."}, status=status.HTTP_400_BAD_REQUEST)

        from orders.services import OrderStateService
        from orders.state_machine import OrderTransitionError

        old_status = order.status_orders
        try:
            order = OrderStateService.admin_override(
                order.id,
                admin_user=request.user,
                new_order_status=new_status or None,
                new_payment_status=new_payment_status or None,
                reason=reason,
                request=request,
            )
        except OrderTransitionError as exc:
            return Response({"error": exc.code, "message": exc.message}, status=status.HTTP_400_BAD_REQUEST)

        # Отправка пуш-уведомления клиенту
        status_messages = {
            Orders.WAITING: "Ваш заказ переведен в ожидание",
            Orders.IN_PROGRESS: "Ваш заказ готовится",
            Orders.COMPLETED: "Ваш заказ готов к выдаче!",
            Orders.CANCELED: f"Заказ отменен: {cancellation_reason or 'Не указано'}",
        }
        if new_status in status_messages and order.user:
            send_push_notification(order.user, "Статус заказа изменен", status_messages[new_status])

        return Response({"status": "Статус заказа обновлен", "order": AdminOrderSerializer(order).data})


# -------------------------------------------------------------
# 7. STAFF & SHIFTS
# -------------------------------------------------------------
class AdminStaffViewSet(viewsets.ModelViewSet):
    queryset = Staff.objects.all().select_related('users', 'place_of_work')
    serializer_class = AdminStaffSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['place_of_work']
    search_fields = ['users__first_name', 'users__last_name', 'users__phone_number']


class AdminShiftsViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Shift.objects.all().order_by('-start_time').select_related('staff__users', 'staff__place_of_work')
    serializer_class = AdminShiftSerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = [IsAdminRole]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status_shift', 'staff']
    ordering_fields = ['start_time', 'amount_closed_orders', 'number_orders_closed']


# -------------------------------------------------------------
# 8. REVIEWS, FRANCHISE, LOYALTY, NOTIFICATIONS
# -------------------------------------------------------------
class AdminReviewsViewSet(viewsets.ModelViewSet):
    queryset = ReviewsCoffeeShop.objects.all().order_by('-id').select_related('user', 'coffee_shop', 'orders')
    serializer_class = AdminReviewSerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = [IsModeratorOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['evaluation', 'coffee_shop', 'very_tasty', 'wide_range', 'nice_prices']
    ordering_fields = ['id', 'evaluation']

    def get_permissions(self):
        if self.action == 'destroy':
            return [IsSuperAdmin()]
        return super().get_permissions()


class AdminFranchiseRequestsViewSet(viewsets.ModelViewSet):
    queryset = FranchiseRequest.objects.all().order_by('-id')
    serializer_class = AdminFranchiseRequestSerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'number_phone', 'text']


class AdminDiscountCardsViewSet(viewsets.ModelViewSet):
    queryset = DiscountCard.objects.all().order_by('-id').select_related('user', 'coffee_shop')
    serializer_class = AdminDiscountCardSerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = [IsAdminRole]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['is_active', 'coffee_shop']
    search_fields = ['user__login', 'user__first_name', 'qr_code']


class AdminNotificationBroadcastView(APIView):
    permission_classes = [IsAdminRole]

    def post(self, request):
        serializer = AdminNotificationBroadcastSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        title = data.get('title')
        message = data.get('message')
        city_id = data.get('city_id')
        coffee_shop_id = data.get('coffee_shop_id')
        user_id = data.get('user_id')

        recipients_qs = CustomUser.objects.filter(is_active=True)
        if user_id:
            recipients_qs = recipients_qs.filter(id=user_id)
        elif coffee_shop_id:
            # Users who made orders in this coffee shop
            user_ids = Orders.objects.filter(coffee_shop_id=coffee_shop_id).values_list('user_id', flat=True).distinct()
            recipients_qs = recipients_qs.filter(id__in=user_ids)
        elif city_id:
            user_ids = Orders.objects.filter(city_choose_id=city_id).values_list('user_id', flat=True).distinct()
            recipients_qs = recipients_qs.filter(id__in=user_ids)

        sent_count = 0
        for user in recipients_qs:
            try:
                send_push_notification(user, title, message)
                sent_count += 1
            except Exception:
                pass

        log_admin_activity(request, 'CREATE', 'Notification', "", f"Рассылка push-уведомлений: '{title}'. Получателей: {sent_count}")

        return Response({
            "status": "Рассылка успешно выполнена",
            "recipients_count": sent_count
        }, status=status.HTTP_200_OK)


# -------------------------------------------------------------
# 9. AUDIT LOGS
# -------------------------------------------------------------
class AdminActivityLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AdminActivityLog.objects.all().order_by('-created_at').select_related('user')
    serializer_class = AdminActivityLogSerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = [IsAdminRole]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['action', 'entity_name', 'user']
    search_fields = ['summary', 'entity_id', 'ip_address']

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.is_superuser or user.role == 'owner':
            return queryset
        return queryset.filter(user=user)
