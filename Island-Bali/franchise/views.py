from drf_yasg.utils import swagger_auto_schema
from rest_framework import generics

from .models import FranchiseInfo, FranchiseRequest
from .serializers import FranchiseInfoSerializer, FranchiseRequestSerializer


class FranchiseRequestViewSet(generics.CreateAPIView):
    queryset = FranchiseRequest.objects.all()
    serializer_class = FranchiseRequestSerializer

    @swagger_auto_schema(
        operation_description="Создание новой заявки на франшизу",
        responses={201: "Created", 400: "Bad Request"},
        tags=["Франшиза"],
        operation_id="Создание заявки на франшизу"
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class FranchiseRequestDetailView(generics.ListAPIView):
    queryset = FranchiseInfo.objects.all()
    serializer_class = FranchiseInfoSerializer

    @swagger_auto_schema(
        operation_description="Получение информации о франшизе",
        responses={200: "OK", 400: "Bad Request"},
        tags=["Франшиза"],
        operation_id="Получение информации о франшизе"
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
