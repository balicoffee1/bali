from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_yasg import openapi

from coffee_shop.models import CoffeeShop
from menu_coffee_product.models import Addon, Product

from .models import CartItem, ShoppingCart
from .serializers import (AddToCartSerializer, CartItemSerializer,
                          ChangeCartSerializer,
                          RemoveProductFromCartSerializer)


class AddToCartView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        request_body=AddToCartSerializer,
        operation_description="Добавляет новый товар в корзину или обновляет количество существующего товара.",
        responses={200: "OK", 400: "Bad Request", 401: "Unauthorized", 404: "Not Found"},
        tags=["Корзина пользователя"],
        operation_id="Добавляет товар в корзину"
    )
    def post(self, request, city_name, street_name):
        serializer = AddToCartSerializer(data=request.data)
        if serializer.is_valid():
            validated_data = serializer.validated_data
            product_name = validated_data.get("product_name")
            quantity = validated_data.get("quantity")
            temperature_type = validated_data.get("temperature_type")
            addons = validated_data.get("addon")
            size = validated_data.get("size")
            user = request.user

            if not user.is_authenticated:
                return Response({"error": "Необходимо авторизоваться (Передайте токен пользователя)"},
                                status=status.HTTP_401_UNAUTHORIZED)

            try:
                coffee_shop = CoffeeShop.objects.get(city__name=city_name, street=street_name)
                product = Product.objects.get(product=product_name, coffee_shop=coffee_shop)
            except CoffeeShop.DoesNotExist:
                return Response({"error": "Кофейня не найдена"}, status=status.HTTP_404_NOT_FOUND)
            except Product.DoesNotExist:
                return Response({"error": "Продукт не найден в этой кофейне"}, status=status.HTTP_404_NOT_FOUND)

            if not product.availability:
                return Response({"error": "К сожалению продукт закончился"}, status=status.HTTP_400_BAD_REQUEST)

            if product.temperature_type == "All" and not temperature_type:
                return Response({"error": "Выберите конкретную температуру напитка: холодный или горячий"},
                                status=status.HTTP_400_BAD_REQUEST)

            if temperature_type and temperature_type not in dict(Product.TEMPERATURE_TYPE_CHOICES):
                return Response({"error": "Выбранная температура недопустима для этого продукта"},
                                status=status.HTTP_400_BAD_REQUEST)

            selected_addons = []
            if addons:
                addon_ids = addons.split(",")  # Assuming `addons` is a comma-separated list of IDs
                for addon_id in addon_ids:
                    try:
                        addon = Addon.objects.get(id=addon_id)
                        if addon in product.addons.all():
                            selected_addons.append(addon)
                        else:
                            return Response({"error": "Выбранная добавка не доступна для данного продукта"},
                                            status=status.HTTP_400_BAD_REQUEST)
                    except Addon.DoesNotExist:
                        return Response({"error": "Добавка не найдена"}, status=status.HTTP_400_BAD_REQUEST)

            cart, created = ShoppingCart.objects.get_or_create(user=user)
            cart_item, created = CartItem.objects.get_or_create(
                cart=cart,
                product=product,
                size=size,
                defaults={'amount': quantity}
            )

            if not created:
                cart_item.amount += int(quantity)
            cart_item.temperature_type = temperature_type
            cart_item.save()
            cart_item.addons.set(selected_addons)

            serializer = CartItemSerializer(cart_item)
            return Response({"Добавлен товар в корзину": serializer.data}, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ChangeQuantityView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        request_body=ChangeCartSerializer,
        operation_description="Метод `change_quantity` используется для изменения количества товара в корзине.",
        responses={200: "OK", 400: "Bad Request"},
        tags=["Корзина пользователя"],
        operation_id="Изменяет количество определенного товара в корзине"
    )
    def put(self, request):
        serializer = ChangeCartSerializer(data=request.data)
        if serializer.is_valid():
            validated_data = serializer.validated_data
            product_name = validated_data.get("product_name")
            quantity = validated_data.get("quantity")

            if not product_name or not quantity:
                return Response({"error": "Введите название продукта и новое количество"}, status=status.HTTP_400_BAD_REQUEST)

            user = request.user
            if not user.is_authenticated:
                return Response({"error": "Необходимо авторизоваться (Передайте токен пользователя)"}, status=status.HTTP_401_UNAUTHORIZED)

            try:
                cart_item = CartItem.objects.get(product__product=product_name, cart__user=user)
                cart_item.amount = int(quantity)
                cart_item.save()
                serializer = CartItemSerializer(cart_item)
                return Response({"Сообщение": f"Количество товара {product_name} изменено на {quantity}"}, status=status.HTTP_200_OK)
            except CartItem.DoesNotExist:
                return Response({"error": f"Товар {product_name} не найден в корзине пользователя"}, status=status.HTTP_404_NOT_FOUND)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RemoveFromCartView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        request_body=RemoveProductFromCartSerializer,
        operation_description="Метод `remove_from_cart` используется для удаления товара из корзины.",
        responses={200: "OK", 400: "Bad Request"},
        tags=["Корзина пользователя"],
        operation_id="Удаляет товар из корзины"
    )
    def delete(self, request):
        serializer = RemoveProductFromCartSerializer(data=request.data)
        if serializer.is_valid():
            validated_data = serializer.validated_data
            product_name = validated_data.get("product_name")

            try:
                product = Product.objects.get(product=product_name)
                cart_item = CartItem.objects.get(product=product, cart__user=request.user)
                cart_item.delete()
                return Response({"message": "Товар удален из корзины"}, status=status.HTTP_204_NO_CONTENT)
            except Product.DoesNotExist:
                return Response({"error": "Такого товара в кофейне не существует"}, status=status.HTTP_404_NOT_FOUND)
            except CartItem.DoesNotExist:
                return Response({"error": "Товар в корзине пользователя не найден"}, status=status.HTTP_404_NOT_FOUND)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ViewCartView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Метод используется"
                              "для просмотра содержимого корзины.",

        responses={200: "OK", 400: "Bad Request"},
        tags=["Корзина пользователя"],
        operation_id="Просмотреть корзину",
    )
    def get(self, request):
        user = request.user
        cart = ShoppingCart.objects.get(user=user)
        cart_items = cart.items.all()

        cart_items_data = []
        total_cart_price = 0

        for cart_item in cart_items:
            item_price = cart_item.item_total_price
            total_cart_price += item_price

            cart_item_data = {
                "product": cart_item.product.product,
                "addon": cart_item.product.addons,
                "amount": cart_item.amount,
                "size": cart_item.size,
                "total_price": item_price,
            }
            cart_items_data.append(cart_item_data)

        response_data = {
            'basket': cart_items_data,
            'total_cart_price': total_cart_price
        }
        return Response(response_data, status=status.HTTP_200_OK)


class ViewCartView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Метод используется для просмотра содержимого корзины.",
        responses={200: "OK", 400: "Bad Request"},
        tags=["Корзина пользователя"],
        operation_id="Просмотреть корзину",
    )
    def get(self, request):
        user = request.user
        try:
            cart = ShoppingCart.objects.get(user=user)
        except ShoppingCart.DoesNotExist:
            return Response({"error": "Корзина не найдена"}, status=status.HTTP_404_NOT_FOUND)

        cart_items = cart.items.all()
        serializer = CartItemSerializer(cart_items, many=True)
        total_cart_price = sum(item['item_total_price'] for item in serializer.data)

        response_data = {
            'basket': serializer.data,
            'total_cart_price': total_cart_price
        }
        return Response(response_data, status=status.HTTP_200_OK)
