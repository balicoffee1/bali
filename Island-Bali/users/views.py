from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from coffee_shop.models import CoffeeShop, CrmSystem
from subtotal_api.connection_api import SubtotalClient
from users import db_communication as db
from users import utils
from users.utils import search_clients
from users.utils import send_phone_reset


from .models import CustomUser, UserCard
from .serializers import UserCardSerializer, UsersSerializer

TAGS_USER = ['Пользователи']


@permission_classes([AllowAny])
@swagger_auto_schema(
    method='post',
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=['login'],
        properties={
            'login': openapi.Schema(type=openapi.TYPE_STRING)
        }
    ),
    responses={
        status.HTTP_200_OK: openapi.Response(
            description="Статус отправки смс сообщения и сам код",
            schema=openapi.Schema(type=openapi.TYPE_OBJECT, properties={
                "code": openapi.Schema(type=openapi.TYPE_INTEGER),
                "text": openapi.Schema(type=openapi.TYPE_STRING),
                "is_registered": openapi.Schema(type=openapi.TYPE_BOOLEAN)})),
        status.HTTP_400_BAD_REQUEST: openapi.Response(
            description="Ошибка неверного запроса",
            schema=openapi.Schema(type=openapi.TYPE_OBJECT, properties={
                "error": openapi.Schema(type=openapi.TYPE_STRING)})),
        status.HTTP_500_INTERNAL_SERVER_ERROR: openapi.Response(
            description="Внутренняя ошибка сервера",
            schema=openapi.Schema(type=openapi.TYPE_OBJECT, properties={
                "error": openapi.Schema(type=openapi.TYPE_STRING)})),
    },
    operation_description="Получение смс кода для регистрации пользователя "
                          "или аутентификации пользователя.",
    operation_id="Получение смс кода",
    tags=TAGS_USER,
)
@api_view(["POST"])
def registration_get_code(request):
    try:
        values = request.data
        if not utils.is_phone_number(values["login"]):
            return Response(
                "login must be phone number",
                status=status.HTTP_400_BAD_REQUEST
            )
        phone = values["login"]
        is_registered = False
        if CustomUser.objects.filter(phone_number__exact=phone):
            is_registered = True
        # code, text = utils.send_phone_reset(phone)
        code = "1234"
        text = "test"
        return Response(
            {
                "code": code,
                "text": text,
                "is_registered": is_registered,
            }
        )
    except Exception as ex:
        return Response(
            {"error": f"Something goes wrong: {ex}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@swagger_auto_schema(
    method='post',
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=['login'],
        properties={
            'login': openapi.Schema(type=openapi.TYPE_STRING)
        }
    ),
    responses={
        status.HTTP_200_OK: openapi.Response(
            description="Статус регистрации пользователя",
            schema=openapi.Schema(type=openapi.TYPE_OBJECT, properties={
                "is_registered": openapi.Schema(type=openapi.TYPE_BOOLEAN)})),
        status.HTTP_400_BAD_REQUEST: openapi.Response(
            description="Ошибка неверного запроса",
            schema=openapi.Schema(type=openapi.TYPE_OBJECT, properties={
                "error": openapi.Schema(type=openapi.TYPE_STRING)})),
        status.HTTP_500_INTERNAL_SERVER_ERROR: openapi.Response(
            description="Внутренняя ошибка сервера",
            schema=openapi.Schema(type=openapi.TYPE_OBJECT, properties={
                "error": openapi.Schema(type=openapi.TYPE_STRING)})),
    },
    operation_description="Проверка регистрации пользователя.",
    operation_id="Проверка регистрации пользователя.",
    tags=TAGS_USER,
)
@api_view(["POST"])
@permission_classes([AllowAny])
def check_registration(request):
    try:
        values = request.data
        login = values["login"]
        is_registered = False
        if not utils.is_phone_number(login):
            return Response(
                "login must be phone number or email",
                status=status.HTTP_400_BAD_REQUEST,
            )

        if utils.is_phone_number(login) and CustomUser.objects.filter(
                phone_number__exact=login
        ):
            is_registered = True
        return Response(
            {
                "is_registered": is_registered,
            }
        )
    except Exception as ex:
        return Response(
            {"error": f"Something goes wrong: {ex}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@swagger_auto_schema(
    method='post',
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=[
                  'login',],
        properties={
            
            'login': openapi.Schema(type=openapi.TYPE_STRING),
        }
    ),
    responses={
        status.HTTP_201_CREATED: openapi.Response(
            description="Данные регистрации пользователя",
            schema=openapi.Schema(type=openapi.TYPE_OBJECT, properties={
                "token": openapi.Schema(type=openapi.TYPE_STRING),
                "id": openapi.Schema(type=openapi.TYPE_INTEGER)})),
        status.HTTP_400_BAD_REQUEST: openapi.Response(
            description="Ошибка неверного запроса",
            schema=openapi.Schema(type=openapi.TYPE_OBJECT, properties={
                "error": openapi.Schema(type=openapi.TYPE_STRING)})),
        status.HTTP_500_INTERNAL_SERVER_ERROR: openapi.Response(
            description="Внутренняя ошибка сервера",
            schema=openapi.Schema(type=openapi.TYPE_OBJECT, properties={
                "error": openapi.Schema(type=openapi.TYPE_STRING)})),
    },
    operation_description="Регистрация нового пользователя или аутентификация"
                          " существующего.",
    operation_id="Регистарция",
    tags=TAGS_USER,
)
@api_view(["POST"])
@permission_classes([AllowAny])
def registration(request):
    try:
        values = request.data
        login = values.get("login")
        if not utils.is_phone_number(login):
            return Response(
                "login must be phone number",
                status=status.HTTP_400_BAD_REQUEST
            )
        elif utils.is_phone_number(login):
            token, user = db.get_or_add_user(values)
            user.create_activation_code()
            send_phone_reset(user.login, user.fcm_token)
            return Response(
                {
                    "token": token,
                    "id": user.id,
                    "fcm_token": user.fcm_token,
                    "auth_type": user.role,
                    "is_staff": user.is_staff
                },
                status=status.HTTP_201_CREATED,
            )
        else:
            return Response(
                {"error": "Invalid registration request"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    except Exception as ex:
        return Response(
            {"error": f"Something goes wrong: {ex}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@swagger_auto_schema(
    method='post',
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=['login', 'fcm_token'],
        properties={
            'login': openapi.Schema(type=openapi.TYPE_STRING,
                                    description="Номер телефона пользователя"),
            'fcm_token': openapi.Schema(type=openapi.TYPE_STRING,
                                        description="Firebase Cloud Messaging "
                                                    "(FCM) токен устройства"),
        }
    ),
    responses={
        status.HTTP_200_OK: openapi.Response(
            description="Успешная авторизация",
            schema=openapi.Schema(type=openapi.TYPE_OBJECT, properties={
                "authorized": openapi.Schema(type=openapi.TYPE_BOOLEAN,
                                             description="True, если "
                                                         "авторизация успешна "
                                                         "иначе False"),
                "token": openapi.Schema(type=openapi.TYPE_OBJECT,
                                        description="Токены доступа и "
                                                    "обновления"),
                "id": openapi.Schema(type=openapi.TYPE_INTEGER,
                                     description="Идентификатор "
                                                 "пользователя")})),
        status.HTTP_400_BAD_REQUEST: openapi.Response(
            description="Ошибка некорректного запроса",
            schema=openapi.Schema(type=openapi.TYPE_OBJECT, properties={
                "error": openapi.Schema(type=openapi.TYPE_STRING)})),
        status.HTTP_500_INTERNAL_SERVER_ERROR: openapi.Response(
            description="Внутренняя ошибка сервера",
            schema=openapi.Schema(type=openapi.TYPE_OBJECT, properties={
                "error": openapi.Schema(type=openapi.TYPE_STRING)})),
    },
    operation_description="Авторизация пользователя.",
    operation_id="Авторизация",
    tags=TAGS_USER,
)
@api_view(["POST"])
@permission_classes([AllowAny])
def auth(request):
    try:
        values = request.data
        login = values.get("login")
        fcm_token = values.get("fcm_token")
        user = None
        if not utils.is_phone_number(login):
            return Response(
                {"error": "Login must be phone number"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if utils.is_phone_number(login):
            user = db.get_user(login=login)
        if user is None:
            return Response(
                {"authorized": False,
                 "error": "User with such login does not exists"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        elif utils.is_phone_number(login):
            user.fcm_token = fcm_token
            user.save()
            refresh = RefreshToken.for_user(user)
            token = {"access": str(refresh.access_token),
                     "refresh": str(refresh)}
            return Response(
                {
                    "authorized": True,
                    "token": token,
                    "id": user.id,
                }
            )
        else:
            return Response(
                {"authorized": False, "error": "Wrong credentials"},
                status=status.HTTP_400_BAD_REQUEST,
            )
    except Exception as ex:
        return Response(
            {"error": f"Something goes wrong: {ex}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@permission_classes([IsAuthenticated])
@swagger_auto_schema(
    methods=["GET", "PUT", "DELETE"],
    operation_description="Получить, обновить или удалить профиль "
                          "пользователя.",
    responses={
        status.HTTP_200_OK: openapi.Response(
            description="Данные пользователя"),
        status.HTTP_204_NO_CONTENT: openapi.Response(
            description="Успешное удаление пользователя"),
        status.HTTP_400_BAD_REQUEST: "Bad Request",
        status.HTTP_404_NOT_FOUND: "Not Found",
        status.HTTP_500_INTERNAL_SERVER_ERROR: "Internal Server Error",
    },
    operation_id="Получить, обновить или удалить профиль",
    tags=TAGS_USER,
)
@api_view(["GET", "PUT", "DELETE"])
def user_profile(request):
    try:
        user = request.user

        if user is None:
            return Response(
                {"error": "Can't find user"},
                status=status.HTTP_404_NOT_FOUND
            )

        if request.method == "GET":
            serializer = UsersSerializer(user)
            serializer_data = serializer.data
            return Response(serializer_data)

        elif request.method == "PUT":
            serializer = UsersSerializer(user,
                                         data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors,
                            status=status.HTTP_400_BAD_REQUEST)

        elif request.method == "DELETE":
            user.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
    except Exception as ex:
        return Response(
            {"error": f"Something goes wrong: {ex}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@swagger_auto_schema(
    method="PUT",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["photo"],
        properties={
            "photo": openapi.Schema(type=openapi.TYPE_STRING,
                                    description="Фотография пользователя "
                                                "в формате base64"),
        },
    ),
    responses={
        status.HTTP_200_OK: openapi.Response(
            description="Успешное обновление фотографии пользователя"),
        status.HTTP_500_INTERNAL_SERVER_ERROR: openapi.Response(
            description="Внутренняя ошибка сервера",
            schema=openapi.Schema(type=openapi.TYPE_OBJECT, properties={
                "error": openapi.Schema(type=openapi.TYPE_STRING)})),
    },
    operation_description="Изменение фотографии пользователя.",
    operation_id="Изменение фотографии пользователя.",
    tags=TAGS_USER,
)
@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def change_photo(request):
    try:
        user = request.user
        values = request.data
        db.change_photo(user, values.get("photo"))

        serializer = UsersSerializer(user)
        return Response(serializer.data, status.HTTP_200_OK)

    except Exception as ex:
        return Response(
            {"error": f"Something goes wrong: {ex}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class BankCardManager(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["card_number", "expiration_date"],
            properties={
                "card_number": openapi.Schema(type=openapi.TYPE_STRING,
                                              description="Номер банковской "
                                                          "карты"),
                "expiration_date": openapi.Schema(type=openapi.TYPE_STRING,
                                                  format=openapi.FORMAT_DATE,
                                                  description="Дата истечения "
                                                              "срока действия "
                                                              "карты в формате"
                                                              " YYYY-MM-DD"),
            },
        ),
        responses={
            status.HTTP_201_CREATED: openapi.Response(
                description="Карта успешно добавлена"),
            status.HTTP_400_BAD_REQUEST: openapi.Response(
                description="Ошибка запроса"),
        },
        operation_description="Добавление новой банковской карты "
                              "пользователю.",
        operation_id="Добавление банковской карты",
        tags=TAGS_USER,
    )
    def post(self, request):
        try:
            user = request.user
            card_data = request.data

            card_number = card_data["card_number"]
            expiration_date = card_data["expiration_date"]

            UserCard.create_new_card(user, card_number, expiration_date)

            return Response("Card added successfully",
                            status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response(f"Error: {e}",
                            status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        responses={
            status.HTTP_200_OK: openapi.Response(
                description="Список банковских карт пользователя"),
            status.HTTP_400_BAD_REQUEST: openapi.Response(
                description="Ошибка запроса"),
        },
        operation_description="Получение списка банковских карт пользователя.",
        operation_id="Получение списка банковских карт",
        tags=TAGS_USER,
    )
    def get(self, request):
        try:
            user = request.user
            
            user_cards = UserCard.objects.filter(user=user)
            serializer = UserCardSerializer(user_cards, many=True)

            serialized_data = serializer.data
            return Response(serialized_data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(f"Error: {e}",
                            status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["card_id"],
            properties={
                "card_id": openapi.Schema(type=openapi.TYPE_INTEGER,
                                          description="Идентификатор "
                                                      "удаляемой карты"),
            },
        ),
        responses={
            status.HTTP_204_NO_CONTENT: openapi.Response(
                description="Карта успешно удалена"),
            status.HTTP_404_NOT_FOUND: openapi.Response(
                description="Карта не найдена или отсутствуют"
                            " права на удаление"),
            status.HTTP_400_BAD_REQUEST: openapi.Response(
                description="Ошибка запроса"),
        },
        operation_description="Удаление банковской карты пользователя.",
        operation_id="Удаление банковской карты",
        tags=TAGS_USER,
    )
    def delete(self, request):
        try:
            user = request.user
            values = request.data
            card_id = values["card_id"]
            card = UserCard.objects.get(id=card_id, user=user)
            card.delete()
            return Response("Card deleted successfully",
                            status=status.HTTP_204_NO_CONTENT)
        except UserCard.DoesNotExist:
            return Response(
                "Card does not "
                "exist or you don't have permission to delete it",
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(f"Error: {e}", status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='get',
    manual_parameters=[
        openapi.Parameter('id_shop', openapi.IN_PATH,
                          type=openapi.TYPE_INTEGER,
                          description='Идентификатор кофейни'),
        openapi.Parameter('phone', openapi.IN_QUERY,
                          type=openapi.TYPE_STRING,
                          description='Номер телефона пользователя')
    ],
    responses={
        200: "Скидка пользователя",
        404: "Not Found",
        500: "Internal Server Error"
    },
    operation_description="Получает скидку пользователя, переданного в "
                          "запросе.",
    operation_id="Скидка пользователя",
    tags=TAGS_USER
)
@api_view(['GET'])
def get_discount_for_user(request, id_shop: int):
    if request.method == 'GET':
        coffee_shop: CoffeeShop = CoffeeShop.objects.get(id=id_shop)
        crm_system_for_shop: CrmSystem = coffee_shop.crm_system
        phone = request.GET['phone']
        email = crm_system_for_shop.login
        password = crm_system_for_shop.password
        if str(crm_system_for_shop) == "QuickRestoApi":
            discount_in_quick = search_clients(phone, login=email,
                                               password=password)
            return Response(discount_in_quick)

        client_subtotal = SubtotalClient(email=email, password=password)
        discount_in_sub = client_subtotal.get_discount_for_phone_number(
            phone_number=phone)
        return Response(discount_in_sub)





class ActivationView(APIView):
    permission_classes = (AllowAny,)

    def get(self, request, fcm_token):
        try:
            user = CustomUser.objects.get(fcm_token=fcm_token)
            user.is_active = True
            user.activation_code = ""
            user.save()
            return Response({
                "msg": "activated"
            },
            status=200
                            
            )
        except Exception:
            return Response({"msg": 'user not found'}, status=400)