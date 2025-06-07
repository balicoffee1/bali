from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_yasg import openapi

from coffee_shop.models import CoffeeShop
from menu_coffee_product.models import Addon, Product, AdditiveFlavors

from .models import CartItem, ShoppingCart
from .serializers import (
    AddToCartSerializer, CartItemSerializer,
    ChangeCartSerializer, CartSerializer,
    RemoveProductFromCartSerializer,
    UpdateCartItemSerializer
)

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
            addons = validated_data.get("addons")
            size = validated_data.get("size")
            user = request.user
            flavors = validated_data.get("flavors")

            if not user.is_authenticated:
                return Response({"error": "Необходимо авторизоваться (Передайте токен пользователя)"},
                                status=status.HTTP_401_UNAUTHORIZED)

            try:
                coffee_shop = CoffeeShop.objects.get(city__name=city_name, street=street_name)
                product = Product.objects.get(product=product_name)
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
            selected_flavors = []
            if addons:
                for addon_obj in addons:
                    try:
                        addon = Addon.objects.get(id=addon_obj.id)
                        selected_addons.append(addon)
                    except Addon.DoesNotExist:
                        return Response({"error": "Добавка не найдена"}, status=status.HTTP_400_BAD_REQUEST)
                    
            if flavors:
                for flavor_id in flavors:
                    try:
                        flavor = AdditiveFlavors.objects.get(id=flavor_id.id)
                        if any(flavor in addon.flavors.all() for addon in selected_addons):
                            selected_flavors.append(flavor)
                        else:
                            return Response({"error": f"Вкус с ID {flavor_id} не доступен для выбранных добавок"},
                                            status=status.HTTP_400_BAD_REQUEST)
                    except AdditiveFlavors.DoesNotExist:
                        return Response({"error": f"Вкус добавки с ID {flavor_id} не найден"},
                                        status=status.HTTP_400_BAD_REQUEST)

            cart, created = ShoppingCart.objects.get_or_create(user=user, is_active=True)
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
            cart_item.flavors.set(selected_flavors)

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
                product = Product.objects.get(product=product_name)
                cart_item = CartItem.objects.get(product=product, cart__user=user)
                cart_item.amount = int(quantity)
                cart_item.save()
                cart = ShoppingCart.objects.get(items=cart_item)
                if not cart:
                    return Response({"error": "Корзина не найдена"}, status=status.HTTP_404_NOT_FOUND)
                cart_serializer = CartSerializer(cart)  

                return Response({
                    "Сообщение": f"Количество товара '{product_name}' изменено на {quantity}",
                    "data": cart_serializer.data
                }, status=status.HTTP_200_OK)
            except CartItem.DoesNotExist:
                return Response({"error": f"Товар '{product_name}' не найден в корзине пользователя"}, status=status.HTTP_404_NOT_FOUND)
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
        cart = ShoppingCart.objects.get(user=user, is_active=True)
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
            cart = ShoppingCart.objects.get(user=user, is_active=True)
        except ShoppingCart.DoesNotExist:
            return Response({"error": "Корзина не найдена"}, status=status.HTTP_404_NOT_FOUND)

        cart_items = cart.items.all()
        serializer = CartItemSerializer(cart_items, many=True)
        total_cart_price = sum(item['item_total_price'] for item in serializer.data)

        response_data = {
            'cart_id': cart.id,
            'basket': serializer.data,
            'total_cart_price': total_cart_price
        }
        return Response(response_data, status=status.HTTP_200_OK)


class DeactivateCartView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Метод используется для деактивации корзины.",
        responses={200: "OK", 400: "Bad Request"},
        tags=["Корзина пользователя"],
        operation_id="Деактивировать корзину",
    )
    def delete(self, request, pk):
        user = request.user
        try:
            cart = ShoppingCart.objects.get(user=user, pk=pk)
            cart.is_active = False
            cart.save()
            return Response({"message": "Корзина деактивирована"}, status=status.HTTP_204_NO_CONTENT)
        except ShoppingCart.DoesNotExist:
            return Response({"error": "Корзина не найдена"}, status=status.HTTP_404_NOT_FOUND)


class UpdateCartView(APIView):
    """
    API для обновления корзины и её элементов по ID корзины.
    """
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        request_body=UpdateCartItemSerializer(many=True),
        operation_description="Обновляет элементы корзины по ID корзины.",
        responses={200: "OK", 400: "Bad Request", 404: "Not Found"},
        tags=["Корзина пользователя"],
        operation_id="Обновляет элементы корзины по ID корзины"
    )
    def patch(self, request, cart_id, *args, **kwargs):
        try:
            cart = ShoppingCart.objects.get(id=cart_id, user=request.user)
        except ShoppingCart.DoesNotExist:
            return Response({"error": "Корзина не найдена"}, status=status.HTTP_404_NOT_FOUND)

        items = request.data

        if not isinstance(items, list):
            return Response({"error": "Ожидается список элементов"}, status=status.HTTP_400_BAD_REQUEST)

        for item_data in items:
            serializer = UpdateCartItemSerializer(data=item_data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            validated_data = serializer.validated_data
            cart_item_id = validated_data.get("cart_item_id")
            new_product_id = validated_data.get("new_product_id")
            quantity = validated_data.get("quantity")
            size = validated_data.get("size")
            temperature_type = validated_data.get("temperature_type")
            addons = validated_data.get("addons")
            flavors = validated_data.get("flavors")

            try:
                cart_item = CartItem.objects.get(id=cart_item_id, cart=cart)
            except CartItem.DoesNotExist:
                return Response({"error": f"Элемент с ID {cart_item_id} не найден"}, status=status.HTTP_404_NOT_FOUND)

            # Обновление продукта
            if new_product_id:
                try:
                    new_product = Product.objects.get(id=new_product_id)
                    if not new_product.availability:
                        return Response({"error": "Выбранный продукт недоступен"}, status=status.HTTP_400_BAD_REQUEST)
                    cart_item.product = new_product
                except Product.DoesNotExist:
                    return Response({"error": f"Продукт с ID {new_product_id} не найден"}, status=status.HTTP_404_NOT_FOUND)

            product = cart_item.product  # Обновлённый или текущий

            # Проверка температуры
            if product.temperature_type == "All" and not temperature_type:
                return Response({"error": "Укажите температуру: горячий или холодный"}, status=status.HTTP_400_BAD_REQUEST)
            if temperature_type and temperature_type not in dict(Product.TEMPERATURE_TYPE_CHOICES):
                return Response({"error": "Недопустимая температура"}, status=status.HTTP_400_BAD_REQUEST)

            cart_item.temperature_type = temperature_type

            # Проверка и установка размера
            if size:
                if size not in dict(CartItem.SizeChoices.choices):
                    return Response({"error": f"Неверный размер: {size}"}, status=status.HTTP_400_BAD_REQUEST)
                cart_item.size = size

            # Обработка добавок
            selected_addons = []
            if addons:
                for addon_id in addons:
                    try:
                        addon = Addon.objects.get(id=addon_id)
                        selected_addons.append(addon)
                    except Addon.DoesNotExist:
                        return Response({"error": f"Добавка с ID {addon_id} не найдена"}, status=status.HTTP_400_BAD_REQUEST)

            # Обработка вкусов
            selected_flavors = []
            if flavors:
                for flavor_id in flavors:
                    try:
                        flavor = AdditiveFlavors.objects.get(id=flavor_id)
                        selected_flavors.append(flavor)
                    except AdditiveFlavors.DoesNotExist:
                        return Response({"error": f"Вкус с ID {flavor_id} не найден"}, status=status.HTTP_400_BAD_REQUEST)

            # Обновление количества
            if quantity == 0:
                cart_item.delete()
                continue
            else:
                cart_item.amount = quantity
                cart_item.save()

            # Обновление ManyToMany
            cart_item.addons.set(selected_addons)
            cart_item.flavors.set(selected_flavors)

        return Response({"message": "Элементы корзины обновлены"}, status=status.HTTP_200_OK)
