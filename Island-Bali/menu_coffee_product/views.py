from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import generics
from rest_framework.viewsets import ModelViewSet
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import permissions

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter
from .filters import SeasonMenuFilter
from .filters import AddonFilter

from menu_coffee_product.models import Category, Product, Addon
from menu_coffee_product.serializers import (CategorySerializer,
    ProductSerializer, AddonSerializer)
from menu_coffee_product.utils import get_weather
from .models import SeasonMenu
from .serializers import SeasonMenuSerializer
from .models import AdditiveFlavors
from .serializers import AdditiveFlavorsSerializer

TAGS_MENU = ['Меню заведений']


class CategoryViewSet(generics.ListAPIView):
    serializer_class = CategorySerializer
    queryset = Category.objects.all()
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['coffee_shop']  # Поле для фильтрации

    @swagger_auto_schema(
        operation_description="С помощью этого метода можно "
                              "просмотреть все категории, "
                              "фильтруя их по кофейне с помощью параметра `coffee_shop`.",
        manual_parameters=[
            openapi.Parameter(
                'coffee_shop',
                openapi.IN_QUERY,
                description="ID кофейни для фильтрации категорий",
                type=openapi.TYPE_INTEGER
            )
        ],
        responses={200: CategorySerializer(many=True)},
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
    permission_classes = [permissions.AllowAny]
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


class SeasonMenuViewSet(ModelViewSet):
    queryset = SeasonMenu.objects.all()
    serializer_class = SeasonMenuSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_class = SeasonMenuFilter


class AddonList(generics.ListAPIView):
    queryset = Addon.objects.all()
    serializer_class = AddonSerializer
    ilter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_class = AddonFilter
    
    
    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                'product_id',
                openapi.IN_QUERY,
                description="ID продукта для фильтрации добавок",
                type=openapi.TYPE_INTEGER
            ),
            openapi.Parameter(
                'coffee_shop_id',
                openapi.IN_QUERY,
                description="ID кофейни для фильтрации добавок",
                type=openapi.TYPE_INTEGER
            ),
            openapi.Parameter(
                'city_id',
                openapi.IN_QUERY,
                description="ID города для фильтрации добавок",
                type=openapi.TYPE_INTEGER
            ),
            openapi.Parameter(
                'coffee_shop',
                openapi.IN_QUERY,
                description="Улица кофейни для фильтрации добавок",
                type=openapi.TYPE_STRING
            )
        ],
        responses={200: CategorySerializer(many=True)},
        tags=TAGS_MENU,
        operation_id="Просмотр категорий"
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)



class AdditiveFlavorsList(generics.ListAPIView):
    queryset = AdditiveFlavors.objects.all().prefetch_related("additive_flavors")
    serializer_class = AdditiveFlavorsSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['addon'] 