from drf_yasg.utils import swagger_auto_schema
from rest_framework import generics
from rest_framework.permissions import AllowAny

from .utils import send_reset_password
from .models import FranchiseInfo, FranchiseRequest
from .serializers import FranchiseInfoSerializer, FranchiseRequestSerializer


# M0 п.3.1: обе вьюхи ниже — публичная маркетинговая форма заявки на франшизу
# и публичная информация о франшизе. После флипа DEFAULT_PERMISSION_CLASSES
# на IsAuthenticated их нужно явно оставить публичными, иначе анонимный
# посетитель сайта/приложения не сможет отправить заявку на франшизу.
class FranchiseRequestViewSet(generics.CreateAPIView):
    queryset = FranchiseRequest.objects.all()
    serializer_class = FranchiseRequestSerializer
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_description="Создание новой заявки на франшизу",
        responses={201: "Created", 400: "Bad Request"},
        tags=["Франшиза"],
        operation_id="Создание заявки на франшизу"
    )
    def post(self, request, *args, **kwargs):
        text = f"""
        ФИО - {request.data.get("name")}
        Номер телефона - {request.data.get("number_phone")}
        Текст: {request.data.get("text")}
        """
        send_reset_password(text)
        return super().post(request, *args, **kwargs)


class FranchiseRequestDetailView(generics.ListAPIView):
    queryset = FranchiseInfo.objects.all()
    serializer_class = FranchiseInfoSerializer
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_description="Получение информации о франшизе",
        responses={200: "OK", 400: "Bad Request"},
        tags=["Франшиза"],
        operation_id="Получение информации о франшизе"
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
