from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from ref_system.serializers import RefSystemSerializer

TAGS_REF = ['Реферальная система']


@swagger_auto_schema(
    method='post',
    request_body=RefSystemSerializer,
    operation_description="Предоставляет аутентифицированному пользователю "
                          "ссылку для реферальной программы. "
                          "user берется из токена аутентификации",
    tags=TAGS_REF,
    operation_id="Ссылка для приглашения",
    responses={
        201: openapi.Response(description="Ссылка успешно создана"),
        400: "Некорректный запрос"
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_ref_link(request: Request) -> Response:
    user_id = request.user.id
    user = {"id": user_id}
    serializer = RefSystemSerializer(data={"user": user})
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    referral_link = (f"https://play.google.com/store/apps/details?"
                     f"id=island_bali&referrer={user_id}")
    return Response({"referral_link": referral_link},
                    status=status.HTTP_200_OK)
