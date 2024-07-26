from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.models import Orders
from staff.models import Staff
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
from .utils import (cancel_order_with_comment,
                    change_order_status_to_completed, change_receipt_photo,
                    close_shift, filter_orders_by_status, get_completed_orders,
                    get_order_if_pending, is_valid_order_status, open_shift,
                    update_order_status)

TAGS_STAFF = ['Персонал']


class PendingOrdersAcceptView(APIView):
    permission_classes = [IsAuthenticated]

    @staticmethod
    @swagger_auto_schema(
        operation_description="Просмотр списка заказов в статусе Expectation",
        tags=TAGS_STAFF,
        operation_id="Просмотр списка заказов",
        responses={200: openapi.Response(description="Успешный запрос",
                                         schema=PendingOrdersAcceptSerializer),
                   400: "Некорректный запрос"}
    )
    def get(request: Request):
        """
        Просмотр списка заказов в статусе "Expectation"
        """
        orders = Orders.objects.filter(status_orders="Expectation")
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

        order, error = get_order_if_pending(data['order_id'])

        if error:
            return Response({"error": error},
                            status=status.HTTP_400_BAD_REQUEST)

        order = update_order_status(order)

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
                serializer.update_order(order, serializer.validated_data)

                serializer = PendingOrdersAcceptSerializer(order)
                return Response(serializer.data, status=status.HTTP_200_OK)

            except Orders.DoesNotExist:
                return Response({"error": "Order not found"},
                                status=status.HTTP_404_NOT_FOUND)
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
            staff_comments = serializer.validated_data.get("staff_comments",
                                                           "")

            try:
                order = Orders.objects.get(id=order_id)
                order = cancel_order_with_comment(order, staff_comments)

                serializer = PendingOrdersAcceptSerializer(order)
                return Response(serializer.data, status=status.HTTP_200_OK)

            except Orders.DoesNotExist:
                return Response({"error": "Order not found"},
                                status=status.HTTP_404_NOT_FOUND)
            except Exception as e:
                return Response({"error": str(e)},
                                status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
        orders = get_completed_orders()
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
            order, error = change_order_status_to_completed(order_id)
            if error:
                status_code = (
                    status.HTTP_400_BAD_REQUEST
                    if error == "Order ID is required"
                    else status.HTTP_404_NOT_FOUND
                )
                return Response({"error": error}, status=status_code)

            serializer = PendingOrdersAcceptSerializer(order)
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
    """
    permission_classes = [IsAuthenticated]
    serializer_class = PendingOrdersAcceptSerializer

    def get_queryset(self):
        return Orders.objects.all().order_by('time_is_finish')

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
        queryset = self.get_queryset()
        serialized_data = self.serializer_class(queryset, many=True).data

        status_counts = {
            "Expectation": Orders.objects.filter(
                status_orders="Expectation").count(),
            "In Progress": Orders.objects.filter(
                status_orders="In Progress").count(),
            "Completed": Orders.objects.filter(
                status_orders="Completed").count(),
            "Canceled": Orders.objects.filter(status_orders="Canceled").count()
        }

        response_data = {
            "orders": serialized_data,
            "status_counts": status_counts
        }

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
        serializer = FilterOrdersByStatusSerializer(request.data)
        if not serializer.is_valid():
            return Response
        order_status = serializer.validated_data.get("status")

        if not order_status:
            return Response(
                {"error": "Status is required in the request body"},
                status=status.HTTP_400_BAD_REQUEST)

        if not is_valid_order_status(order_status):
            return Response({"error": "Invalid status provided"},
                            status=status.HTTP_400_BAD_REQUEST)

        filtered_orders = filter_orders_by_status(order_status)
        serialized_data = self.serializer_class(filtered_orders,
                                                many=True).data

        return Response(serialized_data, status=status.HTTP_200_OK)


class ShiftToggleView(APIView):
    """Проверка и изменения статуса сотрудника на работе"""

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
            serializer = ShiftSerializer(staff)
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
                self.toggle_staff_status(staff)
                response_serializer = ShiftToggleResponseSerializer({
                    "status_shift": staff.status_shift,
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
        if staff.status_shift == "Open":
            staff.status_shift = "Closed"
        else:
            staff.status_shift = "Open"
        staff.save()


class UploadReceiptPhotoView(APIView):
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
    def post(self, request, order_id):
        serializer = UploadReceiptPhotoRequestSerializer(
            data={'order_id': order_id})
        if serializer.is_valid():
            order_id = serializer.validated_data['order_id']
            try:
                order = Orders.objects.get(id=order_id)
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
            photo_data = request.data.get('photo')

            change_receipt_photo(order, photo_data)
            order.payment_status = "Paid"

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

        if start_time:
            shift = open_shift(start_time)
            return Response({"message": "Shift opened"},
                            status=status.HTTP_200_OK)

        elif end_time:
            shift, error = close_shift(start_time, end_time)
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
