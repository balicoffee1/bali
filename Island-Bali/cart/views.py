from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from coffee_shop.models import CoffeeShop
from menu_coffee_product.models import Addon, Product

from .models import CartItem, ShoppingCart
from .serializers import (AddToCartSerializer, CartItemSerializer,
                          ChangeCartSerializer,
                          RemoveProductFromCartSerializer)


class AddToCartView(APIView):
    @staticmethod
    @swagger_auto_schema(
        request_body=AddToCartSerializer,
        operation_description="Используется для добавления нового товара в "
                              "корзину или обновления количества"
                              "существующего "
                              "товара. Проверяет наличие продукта в меню"
                              "кофейни и, если продукт найден",

        responses={200: "OK", 400: "Bad Request"},
        tags=["Корзина пользователя"],
        operation_id="Добавляет товар в корзину")
    def post(request, city_name, street_name):
        serializer = AddToCartSerializer(data=request.data)
        if serializer.is_valid():
            validated_data = serializer.validated_data
            product_name = validated_data.get("product_name")
            quantity = validated_data.get("quantity")
            temperature_type = validated_data.get("temperature_type")
            addons = validated_data.get("addons")
            user = request.user

            if not product_name or not quantity:
                return Response(
                    {"error": "Введите название продукта и количество"},
                    status=status.HTTP_400_BAD_REQUEST)
            if not user.is_authenticated:
                return Response(
                    {
                        "error": "Необходимо авторизоваться "
                                 "(Передайте токен пользователя)"},
                    status=status.HTTP_401_UNAUTHORIZED)

            try:
                coffee_shop = CoffeeShop.objects.get(city__name=city_name,
                                                     street=street_name)
                product = Product.objects.get(product=product_name,
                                              coffee_shop=coffee_shop)
            except CoffeeShop.DoesNotExist:
                return Response({"error": "Coffee shop not found"},
                                status=status.HTTP_404_NOT_FOUND)
            except Product.DoesNotExist:
                return Response({"error": "Product not found in "
                                          "this coffee shop"},
                                status=status.HTTP_404_NOT_FOUND)

            if not product.availability:
                return Response({"error": "К сожалению продукт закончился"},
                                status=status.HTTP_400_BAD_REQUEST)

            if product.temperature_type == "All":
                return Response({
                    "error": "Выберите конкретную температуру напитка: "
                             "холодный или горячий"},
                    status=status.HTTP_400_BAD_REQUEST)

            if temperature_type not in [choice[0] for choice in
                                        Product.TEMPERATURE_TYPE_CHOICES]:
                return Response({
                    "error": "Выбранная температура недопустима для "
                             "этого продукта."
                             "В temperature_type Укажите либо Cold или Hot"},
                    status=status.HTTP_400_BAD_REQUEST)

            selected_addons = []
            if addons:
                for addon_id in addons:
                    try:
                        addon = Addon.objects.get(id=addon_id)
                        if addon in product.addons.all():
                            selected_addons.append(addon)
                        else:
                            return Response({
                                "error": "Выбранная добавка не доступна "
                                         "для данного продукта"},
                                status=status.HTTP_400_BAD_REQUEST)
                    except Addon.DoesNotExist:
                        pass

            cart, created = ShoppingCart.objects.get_or_create(user=user)
            cart_item, created = CartItem.objects.get_or_create(
                cart=cart,
                product=product)
            cart_item.amount += int(quantity)
            cart_item.temperature_type = temperature_type
            cart_item.save()
            product.addons.set(selected_addons)

            serializer = CartItemSerializer(cart_item)
            return Response({"Добавлен товар в корзину": serializer.data},
                            status=status.HTTP_200_OK)
        else:
            return Response(serializer.data,
                            status=status.HTTP_400_BAD_REQUEST)


class ChangeQuantityView(APIView):
    @swagger_auto_schema(
        request_body=ChangeCartSerializer,
        operation_description="Метод `change_quantity` используется "
                              "для изменения"
                              "количества товара в корзине.",

        responses={200: "OK", 400: "Bad Request"},
        tags=["Корзина пользователя"],
        operation_id="Изменяет количество определенного товара в корзине")
    def put(self, request):
        serializer = ChangeCartSerializer(data=request.data)
        if serializer.is_valid():
            validated_data = serializer.validated_data
            product_name = validated_data.get("product_name")
            quantity = validated_data.get("quantity")

            if not product_name or not quantity:
                return Response(
                    {"error": "Введите название продукта "
                              "и новое количество"},
                    status=status.HTTP_400_BAD_REQUEST)

            user = request.user
            if not user.is_authenticated:
                return Response({
                    "error": "Необходимо авторизоваться "
                             "(Передайте токен пользователя)"},
                    status=status.HTTP_401_UNAUTHORIZED)

            try:
                cart_item = CartItem.objects.get(product__product=product_name,
                                                 cart__user=user)
                cart_item.amount = int(quantity)
                cart_item.save()
                CartItemSerializer(cart_item)
                return Response({
                    "Сообщение": f"Количество товара {product_name} "
                                 f"изменено на "
                                 f"{quantity}"}, status=status.HTTP_200_OK)
            except CartItem.DoesNotExist:
                return Response({
                    "error": f"Товар {product_name} не "
                             f"найден в корзине пользователя"},
                    status=status.HTTP_404_NOT_FOUND)
        else:
            return Response(serializer.errors,
                            status=status.HTTP_400_BAD_REQUEST)


class RemoveFromCartView(APIView):
    @swagger_auto_schema(
        request_body=RemoveProductFromCartSerializer,
        operation_description="Метод `remove_from_cart` "
                              "используется для удаления "
                              "товара из корзины.",

        responses={200: "OK", 400: "Bad Request"},
        tags=["Корзина пользователя"],
        operation_id="Удаляет товар из корзины")
    def delete(self, request):
        serializer = RemoveProductFromCartSerializer
        if serializer.is_valid():
            validated_data = serializer.validated_data
            product_name = validated_data.get("product_name")

            try:
                product = Product.objects.get(product=product_name)
                cart_item = CartItem.objects.get(product=product)
                cart_item.delete()
                return Response({"message": "Товар удален из корзины"},
                                status=status.HTTP_204_NO_CONTENT)
            except Product.DoesNotExist:
                return Response({"error": "Такого товара в "
                                          "кофейне не существует"},
                                status=status.HTTP_404_NOT_FOUND)
            except CartItem.DoesNotExist:
                return Response(
                    {"error": "Товар в корзине "
                              "пользователя не найден"},
                    status=status.HTTP_404_NOT_FOUND)
        else:
            return Response(serializer.errors,
                            status=status.HTTP_400_BAD_REQUEST)


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
                "amount": cart_item.amount,
                "total_price": item_price
            }
            cart_items_data.append(cart_item_data)

        response_data = {
            'basket': cart_items_data,
            'total_cart_price': total_cart_price
        }
        return Response(response_data, status=status.HTTP_200_OK)
