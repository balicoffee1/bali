from django.shortcuts import get_object_or_404
from drf_yasg.utils import swagger_auto_schema
from rest_framework import generics
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import City, CoffeeShop
from .serializers import CitySerializer, CoffeeShopSerializer

TAGS_COFFEE_SHOP = ["Кофейня и все связанное с ней"]


class CityViewSet(generics.ListAPIView):
    queryset = City.objects.all().order_by("name")
    serializer_class = CitySerializer
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_description="Получение городов",
        responses={200: "OK", 400: "Bad Request"},
        tags=TAGS_COFFEE_SHOP,
        operation_id="Города")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class CoffeeShopViewSet(generics.ListAPIView):
    queryset = CoffeeShop.objects.all()
    serializer_class = CoffeeShopSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        city_name = self.request.query_params.get('city', None)
        queryset = CoffeeShop.objects.all()
        if city_name:
            city = get_object_or_404(City, name=city_name)
            queryset = queryset.filter(city=city)
        return queryset

    @swagger_auto_schema(
        operation_description="Получение информации о "
                              "кофейнях в определенном городе",
        responses={200: "OK", 400: "Bad Request"},
        tags=TAGS_COFFEE_SHOP,
        operation_id="Список кофеен в городе")
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = CoffeeShopSerializer(queryset, many=True)
        return Response(serializer.data)
