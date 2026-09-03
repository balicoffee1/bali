from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from datetime import datetime, timedelta
from django.utils.timezone import now
from django.db import models

from orders.models import Orders
from staff.models import Staff, Shift
from staff.serializers import (CancelOrderSerializer, CompleteOrdersSerializer,
                               CreateOrderSerializer,
                               FilterOrdersByStatusSerializer,
                               PatchOrderSerializer,
                               PendingOrdersAcceptSerializer, ShiftSerializer,
                               ShiftToggleRequestSerializer,
                               ShiftToggleResponseSerializer,
                               UploadReceiptPhotoRequestSerializer,
                               UploadReceiptPhotoResponseSerializer)

from .serializers import StaffSerializer
from .utils import (change_receipt_photo,
                    close_shift, filter_orders_by_status, get_completed_orders,
                    get_order_if_pending, get_order_if_new, is_staff_for_order,
                    is_valid_order_status, open_shift)
from notifications.main import send_push_notification
from orders.state_machine import OrderTransitionError

TAGS_STAFF = ['Персонал']

# class NewOrdersView(APIView):
#     permission_classes = [IsAuthenticated]

#     @staticmethod
#     @swagger_auto_schema(
#         operation_description="Просмотр списка новых заказов",
#         tags=TAGS_STAFF,
#         operation_id="Просмотр новых заказов",
#         responses={200: openapi.Response(description="Успешный запрос",
#                                          schema=PendingOrdersAcceptSerializer),
#                    400: "Некорректный запрос"}
#     )
#     def get(request: Request):
#         """
#         Просмотр списка новых заказов
#         query_params:
#         - city: Фильтр по городу (необязательный)
#         - name: Фильтр по имени клиента (необязательный)
#         """
#         city = request.query_params.get('city', None)
#         name = request.query_params.get('name', None)
#         one_hour_ago = now() - timedelta(hours=1)
#         orders = Orders.objects.filter(status_orders="New", created_at__gte=one_hour_ago, city).order_by("-created_at")
#         serializer = PendingOrdersAcceptSerializer(orders, many=True)
#         return Response(serializer.data)


class PendingOrdersAcceptView(APIView):
    permission_classes = [IsAuthenticated]

    @staticmethod
    @swagger_auto_schema(
        operation_description="Просмотр списка заказов в статусе Waiting",
        tags=TAGS_STAFF,
        operation_id="Просмотр списка заказов",
        responses={200: openapi.Response(description="Успешный запрос",
                                         schema=PendingOrdersAcceptSerializer),
                   400: "Некорректный запрос"}
    )
    def get(request: Request):
        """
        Просмотр списка заказов в статусе "Waiting"
        """
        city_id = request.query_params.get('city_id', None)
        coffee_shop_id = request.query_params.get('coffee_shop_id', None)
        sorting_time = request.query_params.get('sorting_time',)
        if sorting_time:
            orders = Orders.objects.filter(
                status_orders="Waiting",
                time_is_finish__gte=sorting_time,
                city_choose=city_id,
                coffee_shop=coffee_shop_id
            ).order_by("-created_at")
        else:
            orders = Orders.objects.filter(
                status_orders="Waiting",
                city_choose=city_id,
                coffee_shop=coffee_shop_id
            ).order_by("-created_at")
        serializer = PendingOrdersAcceptSerializer(orders, many=True)
        return Response(serializer.data)

    @staticmethod
    @swagger_auto_schema(
        request_body=CreateOrderSerializer,
        operation_description="Принять заказ",
        responses={200: openapi.Response(description="Успешный запрос",
                                         schema=PendingOrdersAcceptSerializer),
                   400: "Некорректный запрос"},
        tags=TAGS_STAFF,
        operation_id="Принять заказ"
    )
    def post(request: Request):
        """
        Принять заказ
        Пример
        {
        "order_id": 1
        }
        """
        serializers = CreateOrderSerializer(data=request.data)
        if not serializers.is_valid():
            return Response(serializers.errors,
                            status=status.HTTP_400_BAD_REQUEST)
        data = serializers.validated_data
        if not data['order_id']:
            return Response({"error": "Нужен order_id"},
                            status=status.HTTP_400_BAD_REQUEST)

        order, error = get_order_if_new(data['order_id'])

        if error:
            return Response({"error": error},
                            status=status.HTTP_400_BAD_REQUEST)

        # M0 п.3.2 (IDOR): раньше любой аутентифицированный пользователь мог
        # принять чужой заказ, зная его id — теперь требуется реальное
        # членство в Staff той же кофейни.
        if not is_staff_for_order(request.user, order):
            return Response({"error": "Вы не являетесь сотрудником этой кофейни"},
                            status=status.HTTP_403_FORBIDDEN)

        from orders.services import OrderStateService

        try:
            # M1 п.18: раньше update_order_status(order) безусловно писал
            # status_orders="Waiting" даже поверх Completed/Canceled заказа.
            # accept() сам проверяет допустимость перехода.
            order = OrderStateService.accept(order.id, staff_user=request.user)
        except OrderTransitionError as exc:
            return Response({"error": exc.message}, status=status.HTTP_400_BAD_REQUEST)

        send_push_notification(order.user, "Новое сообщение", "Ваш заказ подтвержден")
        send_push_notification(order.user, "Новое сообщение", "Оплатите заказ в течение 1,5 минут")

        serializer = PendingOrdersAcceptSerializer(order)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @staticmethod
    @swagger_auto_schema(
        request_body=PatchOrderSerializer,
        operation_description="Частичное обновление данных заказа.",
        responses={200: openapi.Response(description="Успешный запрос",
                                         schema=PendingOrdersAcceptSerializer),
                   400: "Bad Request", 404: "Not Found",
                   500: "Internal Server Error"},
        tags=TAGS_STAFF,
        operation_id="Частичное обновление заказа"
    )
    def patch(request: Request):
        serializer = PatchOrderSerializer(data=request.data)
        if serializer.is_valid():
            order_id = serializer.validated_data.get('order_id')

            try:
                order = Orders.objects.get(id=order_id)
            except Orders.DoesNotExist:
                return Response({"error": "Order not found"},
                                status=status.HTTP_404_NOT_FOUND)

            if not is_staff_for_order(request.user, order):
                return Response({"error": "Вы не являетесь сотрудником этой кофейни"},
                                status=status.HTTP_403_FORBIDDEN)

            try:
                # PatchOrderSerializer.update_order не трогает status_orders/
                # payment_status (только время/комментарии/UI-флаги) — вне
                # инварианта единой точки мутации бизнес-статуса (M1 п.1),
                # поэтому остаётся как есть.
                serializer.update_order(order, serializer.validated_data)

                serializer = PendingOrdersAcceptSerializer(order)
                send_push_notification(order.user, "Новое сообщение", "Ваш заказ изменен")

                return Response(serializer.data, status=status.HTTP_200_OK)

            except Exception as e:
                return Response({"error": str(e)},
                                status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @staticmethod
    @swagger_auto_schema(
        request_body=CancelOrderSerializer,
        operation_description="Отмена заказа с возможностью добавления "
                              "комментариев персонала.",
        responses={200: "OK", 400: "Bad Request", 404: "Not Found",
                   500: "Internal Server Error"},
        tags=TAGS_STAFF,
        operation_id="Отмена заказа"
    )
    def delete(request: Request):
        serializer = CancelOrderSerializer(data=request.data)
        if serializer.is_valid():
            order_id = serializer.validated_data.get("order_id")
            cancellation_reason = serializer.validated_data.get("cancellation_reason",
                                                           "")

            try:
                order = Orders.objects.get(id=order_id)
            except Orders.DoesNotExist:
                return Response({"error": "Order not found"},
                                status=status.HTTP_404_NOT_FOUND)

            if not is_staff_for_order(request.user, order):
                return Response({"error": "Вы не являетесь сотрудником этой кофейни"},
                                status=status.HTTP_403_FORBIDDEN)

            from orders.services import OrderStateService

            try:
                # M1 п.18: раньше cancel_order_with_comment безусловно писал
                # status_orders=CANCELED даже поверх Completed — cancel()
                # сам не даёт отменить уже терминальный заказ.
                order = OrderStateService.cancel(order.id, actor_type="staff", reason=cancellation_reason)
            except OrderTransitionError as exc:
                return Response({"error": exc.message}, status=status.HTTP_400_BAD_REQUEST)

            serializer = PendingOrdersAcceptSerializer(order)
            send_push_notification(order.user, "Новое сообщение", "Ваш заказ отменен")

            return Response(serializer.data, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CompleteOrdersView(APIView):
    permission_classes = [IsAuthenticated]

    @staticmethod
    @swagger_auto_schema(
        operation_description="Просмотр списка выполненных заказов.",
        tags=TAGS_STAFF,
        operation_id="Просмотр выполненных заказов",
        responses={200: openapi.Response(
            description="Успешный запрос. Возвращает список выполненных "
                        "заказов.",
            schema=PendingOrdersAcceptSerializer)}
    )
    def get(request: Request):
        """
        Просмотр списка заказов в статусе "Completed"
        """
        sorting_datevalue = request.query_params.get('sorting_date', None)
        if sorting_datevalue:
            orders = get_completed_orders(sorting_datevalue)
        else:
            orders = Orders.objects.filter(status_orders="Completed").order_by(
                "-created_at", "time_is_finish"
            )
        serializer = PendingOrdersAcceptSerializer(orders, many=True)
        return Response(serializer.data)

    @staticmethod
    @swagger_auto_schema(
        request_body=CompleteOrdersSerializer,
        operation_description="Перевод заказа в статус выполненного.",
        responses={200: "OK", 400: "Bad Request", 404: "Not Found"},
        tags=TAGS_STAFF,
        operation_id="Перевод заказа в статус выполненного"
    )
    def post(request: Request):
        """
        Перевод заказа в статус выполненного
        Ожидаемые данные:
        {
            "order_id": 1
        }
        """
        serializer = CompleteOrdersSerializer(data=request.data)
        if serializer.is_valid():
            order_id = serializer.validated_data.get("order_id")
            try:
                order = Orders.objects.get(id=order_id)
            except Orders.DoesNotExist:
                return Response({"error": "Order not found"}, status=status.HTTP_404_NOT_FOUND)

            if not is_staff_for_order(request.user, order):
                return Response({"error": "Вы не являетесь сотрудником этой кофейни"},
                                status=status.HTTP_403_FORBIDDEN)

            from orders.services import OrderStateService

            try:
                # change_order_status_to_completed уже проверял "In Progress",
                # но напрямую писал status_orders + отдельным order.save() —
                # теперь то же самое, но атомарно и через сервис (M1 п.18).
                order = OrderStateService.complete(order.id, staff_user=request.user)
            except OrderTransitionError as exc:
                return Response({"error": exc.message}, status=status.HTTP_400_BAD_REQUEST)

            serializer = PendingOrdersAcceptSerializer(order)
            send_push_notification(order.user, "Новое сообщение", "Ваш заказ готов")

            return Response(serializer.data, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class OrdersByTimeView(generics.ListAPIView):
    """
    Получение списка заказов, отсортированных по времени выполнения.

    Возвращает список заказов, отсортированных по времени завершения
    заказа,
    с дополнительной информацией о количестве
    заказов для каждого статуса (Expectation, In Progress, Completed,
    Canceled).
    query_params:
    - city_id: ID города для фильтрации заказов (необязательный)
    - coffee_shop_id: ID кофейни для фильтрации заказов (необязательный)
    """
    permission_classes = [IsAuthenticated]
    serializer_class = PendingOrdersAcceptSerializer

    def get_queryset(self):
        # M7: сам queryset живёт в staff/queries.py — из него же собирается
        # realtime-снапшот смены, чтобы состав экрана не зависел от транспорта.
        from staff.queries import orders_in_shift_window

        return orders_in_shift_window(
            city_id=self.request.query_params.get('city_id'),
            coffee_shop_id=self.request.query_params.get('coffee_shop_id'),
            sorting_time=self.request.query_params.get('sorting_time'),
        )

    @swagger_auto_schema(
        operation_description="Получение списка заказов, отсортированных по "
                              "времени выполнения",
        responses={
            200: PendingOrdersAcceptSerializer,
            400: "Bad Request",
            404: "Not Found"
        },
        tags=TAGS_STAFF,
        operation_id="Получение списка заказов"
    )
    def get(self, request: Request, *args, **kwargs):
        from staff.queries import shift_aggregates

        serialized_data = self.serializer_class(self.get_queryset(), many=True).data

        response_data = {"orders": serialized_data, **shift_aggregates()}

        return Response(response_data)


class FilterOrdersByStatus(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PendingOrdersAcceptSerializer

    @swagger_auto_schema(
        request_body=FilterOrdersByStatusSerializer,
        responses={200: PendingOrdersAcceptSerializer(many=True)},
        operation_description="Фильтрует заказы по указанному статусу",
        tags=TAGS_STAFF,
        operation_id="Фильтрует заказы"

    )
    def post(self, request: Request):
        """
        Фильтрует заказы по указанному статусу.
        Ожидаемые данные в теле запроса:
        {"status": "Waiting"}
        Возвращает список заказов с указанным статусом.
        В случае неверного статуса вернет ошибку.
        """
        city = request.query_params.get('city_id', None)
        coffee_shop = request.query_params.get('coffee_shop_id', None)
        
        serializer = FilterOrdersByStatusSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        order_status = serializer.validated_data.get("status")

        # M7: тот же общий слой, что и у realtime-снапшота (staff/queries.py).
        from staff.queries import orders_with_status

        filtered_orders = orders_with_status(
            city_id=city, coffee_shop_id=coffee_shop, status=order_status
        )
        serialized_data = self.serializer_class(filtered_orders, many=True).data

        return Response(serialized_data, status=status.HTTP_200_OK)


class ShiftToggleView(APIView):
    """Проверка и изменения статуса сотрудника на работе"""

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter('id', openapi.IN_QUERY,
                               description="ID пользователя",
                               type=openapi.TYPE_INTEGER)
        ],
        operation_description="Получение статуса сотрудника по его ID через GET-запрос.",
        responses={200: ShiftSerializer()},
        tags=TAGS_STAFF,
        operation_id="Получение статуса сотрудника GET"
    )
    def get(self, request):
        user_id = request.query_params.get('id')
        if user_id is None:
            user_id = request.user.id

        if user_id is None:
            return Response({"error": "ID пользователя не указан"},
                            status=status.HTTP_400_BAD_REQUEST)

        staff = self.get_staff(user_id)
        if staff:
            shift = Shift.objects.filter(staff=staff).order_by('-id').first()
            if not shift:
                shift = Shift.objects.create(staff=staff, status_shift="Closed")
            serializer = ShiftSerializer(shift)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response({"error": "Staff not found"},
                        status=status.HTTP_404_NOT_FOUND)

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['id'],
            properties={
                'id': openapi.Schema(type=openapi.TYPE_INTEGER,
                                     description="ID пользователя")
            },
        ),
        operation_description="Получение статуса сотрудника по его ID.",
        responses={200: ShiftSerializer()},
        tags=TAGS_STAFF,
        operation_id="Проверка статуса сотрудника"
    )
    def post(self, request):
        user_id = request.data.get('id')
        if user_id is None:
            return Response({"error": "ID пользователя не указан"},
                            status=status.HTTP_400_BAD_REQUEST)

        staff = self.get_staff(user_id)
        if staff:
            shift = Shift.objects.filter(staff=staff).order_by('-id').first()
            if not shift:
                # Если смен еще нет, создаем дефолтную закрытую
                shift = Shift.objects.create(staff=staff, status_shift="Closed")
            serializer = ShiftSerializer(shift)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response({"error": "Staff not found"},
                        status=status.HTTP_404_NOT_FOUND)

    @swagger_auto_schema(
        request_body=ShiftToggleRequestSerializer,
        responses={200: ShiftToggleResponseSerializer()},
        operation_description="Обновление статуса сотрудника",
        tags=TAGS_STAFF,
        operation_id="Обновление статуса"
    )
    def patch(self, request: Request):
        serializer = ShiftToggleRequestSerializer(data=request.data)
        if serializer.is_valid():
            user_id = serializer.validated_data['id']
            staff = self.get_staff(user_id)
            if staff:
                shift = self.toggle_staff_status(staff)
                response_serializer = ShiftToggleResponseSerializer({
                    "status_shift": shift.status_shift,
                    "users": staff.users.first_name
                })
                return Response(response_serializer.data,
                                status=status.HTTP_200_OK)
            return Response({"error": "Staff not found"},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def get_staff(self, user):
        try:
            return Staff.objects.get(users=user)
        except Staff.DoesNotExist:
            return None

    def toggle_staff_status(self, staff):
        shift = Shift.objects.filter(staff=staff).order_by('-id').first()
        if not shift or shift.status_shift == "Closed":
            # Открываем новую смену
            shift = Shift.objects.create(staff=staff, status_shift="Open", start_time=now())
        else:
            # Закрываем текущую смену
            shift.status_shift = "Closed"
            shift.end_time = now()
            shift.update_shift_statistics()
            shift.save()
        return shift


class UploadReceiptPhotoView(APIView):
    # M0 п.3.2: раньше AllowAny — любой неаутентифицированный запрос мог
    # прочитать URL фото чека ЛЮБОГО заказа (post) или пометить любой заказ
    # выданным и прикрепить фото (put), зная только order_id.
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter('order_id', openapi.IN_PATH,
                              type=openapi.TYPE_INTEGER,
                              description="ID заказа, для которого требуется "
                                          "получить фото чека.")
        ],
        responses={
            200: UploadReceiptPhotoResponseSerializer(),
            400: "Receipt photo not found for this order",
            404: "Order not found"
        },
        operation_description="Получить URL фото чека заказа по его ID.",
        operation_id="Получение фото чека",
        tags=TAGS_STAFF
    )
    def post(self, request):
        order_id = request.data.get('order_id')
        serializer = UploadReceiptPhotoRequestSerializer(
            data={'order_id': order_id})
        if serializer.is_valid():
            order_id = serializer.validated_data['order_id']
            try:
                order = Orders.objects.get(id=order_id)
                if not is_staff_for_order(request.user, order):
                    return Response({"error": "Вы не являетесь сотрудником этой кофейни"},
                                    status=status.HTTP_403_FORBIDDEN)
                if order.receipt_photo:
                    photo_url = order.receipt_photo.url
                    response_serializer = UploadReceiptPhotoResponseSerializer(
                        {'photo_url': photo_url})
                    return Response(response_serializer.data,
                                    status=status.HTTP_200_OK)
                else:
                    return Response(
                        {"error": "Receipt photo not found for this order"},
                        status=status.HTTP_404_NOT_FOUND)
            except Orders.DoesNotExist:
                return Response({"error": "Order not found"},
                                status=status.HTTP_404_NOT_FOUND)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @staticmethod
    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['order_id', 'photo'],
            properties={
                'order_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                'photo': openapi.Schema(type=openapi.TYPE_STRING,
                                        format=openapi.FORMAT_BINARY),
            },
        ),
        responses={
            status.HTTP_200_OK: PendingOrdersAcceptSerializer,
            status.HTTP_400_BAD_REQUEST: "Неверный запрос",
            status.HTTP_404_NOT_FOUND: "Не найдено",
            status.HTTP_500_INTERNAL_SERVER_ERROR: "Внутренняя ошибка сервера",
        },
        operation_description="Загрузка фотографии квитанции и отметка заказа "
                              "как оплаченного.",
        operation_id="Загрузка Фото Квитанции",
        tags=TAGS_STAFF,
    )
    def put(request: Request):
        try:
            order_id = request.data.get("order_id")
            if not order_id:
                return Response(
                    {"error": "Order ID is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            order = Orders.objects.get(id=order_id)
            if not is_staff_for_order(request.user, order):
                return Response({"error": "Вы не являетесь сотрудником этой кофейни"},
                                status=status.HTTP_403_FORBIDDEN)
            photo_data = request.data.get('photo')

            change_receipt_photo(order, photo_data)
            order.issued = True
            order.checkLoaded = True
            order.save()

            serializer = PendingOrdersAcceptSerializer(order)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Orders.DoesNotExist:
            return Response(
                {"error": "Order not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        except Exception as ex:
            return Response(
                {"error": f"Something went wrong: {ex}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ShiftCloseOpenView(APIView):
    @staticmethod
    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['start_time', 'end_time'],
            properties={
                'start_time': openapi.Schema(type=openapi.TYPE_STRING,
                                             format=openapi.FORMAT_DATETIME),
                'end_time': openapi.Schema(type=openapi.TYPE_STRING,
                                           format=openapi.FORMAT_DATETIME),
            }
        ),
        responses={
            status.HTTP_200_OK: openapi.Response(
                description="Сообщение об успешном открытии или закрытии "
                            "смены",
                schema=openapi.Schema(type=openapi.TYPE_OBJECT, properties={
                    "message": openapi.Schema(type=openapi.TYPE_STRING)})),
            status.HTTP_400_BAD_REQUEST: openapi.Response(
                description="Неверный запрос",
                schema=openapi.Schema(type=openapi.TYPE_OBJECT, properties={
                    "error": openapi.Schema(type=openapi.TYPE_STRING)})),
            status.HTTP_404_NOT_FOUND: openapi.Response(
                description="Не найдено",
                schema=openapi.Schema(type=openapi.TYPE_OBJECT, properties={
                    "error": openapi.Schema(type=openapi.TYPE_STRING)})),
        },
        operation_description="Обрабатывает открытие и закрытие смен через "
                              "POST-запрос.",
        operation_id="ShiftCloseOpen",
        tags=TAGS_STAFF,
    )
    def post(request: Request):
        start_time = request.data.get('start_time')
        end_time = request.data.get('end_time')
        staff = Staff.objects.get(users=request.user)

        if start_time and not end_time:
            shift = open_shift(start_time, staff)
            return Response({"message": "Shift opened"},
                            status=status.HTTP_200_OK)

        elif end_time:
            shift, error = close_shift(start_time, end_time, staff)
            if error:
                return Response({"error": error},
                                status=status.HTTP_404_NOT_FOUND)
            return Response({"message": "Shift closed"},
                            status=status.HTTP_200_OK)

        else:
            return Response({"error": "Start or end time is required"},
                            status=status.HTTP_400_BAD_REQUEST)


class StaffDetailView(APIView):
    """
    Представление для получения информации о сотруднике.
    """

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter('pk', openapi.IN_PATH,
                              description="Идентификатор сотрудника",
                              type=openapi.TYPE_INTEGER),
        ],
        responses={
            status.HTTP_200_OK: openapi.Response(
                description="Информация о сотруднике",
                schema=openapi.Schema(type=openapi.TYPE_OBJECT, properties={
                    "name": openapi.Schema(type=openapi.TYPE_STRING),
                    "position": openapi.Schema(type=openapi.TYPE_STRING)})),
            status.HTTP_404_NOT_FOUND: openapi.Response(
                description="Сотрудник не найден",
                schema=openapi.Schema(type=openapi.TYPE_OBJECT, properties={
                    "error": openapi.Schema(type=openapi.TYPE_STRING)})),
        },
        operation_description="Получение информации о сотруднике.",
        operation_id="StaffDetail",
        tags=TAGS_STAFF,
    )
    def get(self, request: Request, pk):
        try:
            staff = Staff.objects.get(pk=pk)
            serializer = StaffSerializer(staff)
            return Response(serializer.data)
        except Staff.DoesNotExist:
            return Response({"error": "Сотрудник не найден"},
                            status=status.HTTP_404_NOT_FOUND)


class GetCanceledOrdersView(APIView):
    """
    Представление для получения списка отмененных заказов.
    """

    @swagger_auto_schema(
        operation_description="Получение списка отмененных заказов.",
        responses={
            status.HTTP_200_OK: openapi.Response(
                description="Список отмененных заказов",
                schema=PendingOrdersAcceptSerializer(many=True)),
            status.HTTP_404_NOT_FOUND: "Не найдено"
        },
        tags=TAGS_STAFF,
        operation_id="GetCanceledOrders"
    )
    def get(self, request: Request):
        city_id = request.query_params.get('city_id', None)
        coffee_shop_id = request.query_params.get('coffee_shop_id', None)
        today = now().date()
        canceled_orders = Orders.objects.filter(
            status_orders="Canceled",
            created_at__date=today,
            city_choose=city_id,
            coffee_shop=coffee_shop_id
        ).order_by("-created_at")
        serializer = PendingOrdersAcceptSerializer(canceled_orders, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class GetStaffProfileView(APIView):
    """
    Представление для получения профиля сотрудника по токену.
    """
    permission_classes = [IsAuthenticated]

    # @swagger_auto_schema(
    #     responses={
    #         status.HTTP_200_OK: openapi.Response(
    #             description="Профиль сотрудника",
    #             schema=StaffSerializer()),
    #         status.HTTP_404_NOT_FOUND: openapi.Response(
    #             description="Сотрудник не найден",
    #             schema=openapi.Schema(type=openapi.TYPE_OBJECT, properties={
    #                 "error": openapi.Schema(type=openapi.TYPE_STRING)})),
    #     },
    # )
    def get(self, request: Request):
        try:
            user = request.user
            staff = Staff.objects.filter(users=user).first()
            serializer = StaffSerializer(staff)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Staff.DoesNotExist:
            return Response({"error": "Сотрудник не найден"},
                            status=status.HTTP_404_NOT_FOUND)