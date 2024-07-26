from drf_yasg.utils import swagger_auto_schema
from rest_framework import generics
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from menu_coffee_product.models import Category, Product
from menu_coffee_product.serializers import (CategorySerializer,
                                             ProductSerializer)
from menu_coffee_product.utils import get_weather

TAGS_MENU = ['Меню заведений']


class CategoryViewSet(generics.ListAPIView):
    # TODO Реализовать просмотр категорий в отдельной кофейне,
    #  а в данный момент выходят все категории из всех кофейн
    queryset = Category.objects.all()
    serializer_class = CategorySerializer

    @swagger_auto_schema(
        operation_description="С помощью этого метода можно "
                              "просмотреть все категории ",

        responses={201: "Created", 400: "Bad Request"},
        tags=TAGS_MENU,
        operation_id="Просмотр категорий"
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class ProductViewSet(generics.ListAPIView):
    serializer_class = ProductSerializer

    def get_queryset(self):
        queryset = Product.objects.all()
        city_name = self.request.query_params.get('city', None)
        street_name = self.request.query_params.get('street', None)

        if city_name is not None:
            queryset = queryset.filter(coffee_shop__city__name=city_name)
        if street_name is not None:
            queryset = queryset.filter(coffee_shop__street=street_name)
        return queryset

    @swagger_auto_schema(
        operation_description="Просмотр меню в определенной кофейни"
                              "api/menu_coffee_product/menu/?city=Альметьевск"
                              "& street = Заслонова",
        responses={201: "Created", 400: "Bad Request"},
        tags=TAGS_MENU,
        operation_id="Просмотр меню"
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class ProductListInCategory(generics.ListAPIView):
    # TODO как по мне по id товара получать информацию это неправильно,
    #  нужно подумать как переделать
    serializer_class = ProductSerializer

    def get_queryset(self):
        category_id = self.kwargs.get('id')
        category = get_object_or_404(Category, id=category_id)
        return Product.objects.filter(category=category)

    @swagger_auto_schema(
        operation_description="Используя id товара можно посмотреть "
                              "подробную информацию по товару",
        responses={201: "Created", 400: "Bad Request"},
        tags=TAGS_MENU,
        operation_id="Просмотр товара"
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class WeatherView(APIView):
    # TODO Убрать в отдельное приложение
    @swagger_auto_schema(
        operation_description="Получить погоду в городе",
        responses={201: "Created", 400: "Bad Request"},
        tags=TAGS_MENU,
        operation_id="Погода в городе"
    )
    def post(self, request):
        city_name = request.data.get('city')
        if not city_name:
            return Response({"error": "Необходимо "
                                      "указать название города"},
                            status=400)

        weather_data = get_weather(city_name)
        if weather_data == "Город не найден":
            return Response({"error": "Город не найден"}, status=404)

        temperature, weather_description = weather_data
        return Response(
            {f"Температура в {city_name}": temperature,
             "Описание погоды": weather_description})
