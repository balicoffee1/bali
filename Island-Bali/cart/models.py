from django.db import models
from loguru import logger

from menu_coffee_product.models import Product, Addon
from users.models import CustomUser


class ShoppingCart(models.Model):
    user = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="cart", null=True,
        blank=True, verbose_name="Владелец корзины"
    )
    is_active = models.BooleanField(default=True, verbose_name="Активна ли корзина")

    class Meta:
        ordering = ['id']
        verbose_name = "Корзина"
        verbose_name_plural = "Корзины"

    def __str__(self):
        return f"Корзина пользователя: {self.user}"

    def resolve_coffee_shop(self):
        """Кофейня, которой принадлежит корзина, — по товарам, а не по клиенту.

        Клиент раньше присылал coffee_shop в теле запроса на создание заказа, и
        сервер ему верил. Приложение при этом не очищает корзину при смене
        точки: набрал в кофейне A, переключился на B — заказ уезжал в B вместе
        с позициями, которых у B нет в меню.

        Возвращает (coffee_shop, error): error заполнен, если корзина пуста или
        в ней товары разных кофеен.
        """
        shops = {
            item.product.coffee_shop
            for item in self.items.select_related("product__coffee_shop")
            if item.product_id is not None
        }
        if not shops:
            return None, "Корзина пуста"
        if len(shops) > 1:
            names = ", ".join(sorted(str(shop) for shop in shops))
            return None, (
                f"В корзине товары разных кофеен ({names}). "
                "Оформите заказы отдельно или очистите корзину."
            )
        return shops.pop(), None

    @property
    def cart_total_price(self):
        """Высчитывает полную стоимость корзины."""
        total_price = sum(item.item_total_price for item in self.items.all())
        return round(total_price, 2)

    def send_orders_for_confirmation_to_barista(self, user, city_choose,
                                                coffee_shop, client_comments,
                                                staff, time_is_finish, cart):
        """
        Метод для создания нового заказа и связывания его с текущей корзиной.
        """
        from orders.models import Orders
        order = Orders.objects.create(
            user=user,
            city_choose=city_choose,
            coffee_shop=coffee_shop,
            cart=cart,
            client_comments=client_comments,
            status_orders="Waiting",
            payment_status="Pending"
        )

        self.order = order
        self.save()

        return order


class CartItem(models.Model):
    class SizeChoices(models.TextChoices):
        S = "S", "Small"
        M = "M", "Medium"
        L = "L", "Large"

    class TemperatureChoices(models.TextChoices):
        HOT = "Hot", "Горячий"
        COLD = "Cold", "Холодный"

    cart = models.ForeignKey(
        ShoppingCart, on_delete=models.CASCADE, related_name="items",
        verbose_name="Корзина"
    )
    product = models.ForeignKey(
        Product, related_name="cart_items", on_delete=models.CASCADE,
        null=True, blank=True, verbose_name="Продукт"
    )
    addons = models.ManyToManyField(Addon, related_name='cart_items', blank=True, verbose_name="Добавки")
    flavors = models.ManyToManyField(
        'menu_coffee_product.AdditiveFlavors',
        related_name='cart_items',
        blank=True,
        verbose_name="Вкусовые добавки"
    )
    amount = models.PositiveIntegerField(default=0, verbose_name="Колличество")
    size = models.CharField(
        max_length=1,
        choices=SizeChoices.choices,
        default=SizeChoices.S,
        verbose_name="Размер"
    )
    temperature_type = models.CharField(
        max_length=4,
        choices=TemperatureChoices.choices,
        null=True,
        blank=True,
        verbose_name="Температура напитка",
        help_text="Выбор клиента для этой позиции. У товара в каталоге есть "
                  "своё поле temperature_type — оно говорит, какой выбор "
                  "вообще возможен, а не что выбрали.",
    )

    class Meta:
        ordering = ['id']
        verbose_name = "Продукт в корзине"
        verbose_name_plural = "Продукты в корзине"

    def __str__(self):
        return (f"Продукт {self.product.product} в "
                f"корзине пользователя: {self.cart.user}")

    def size_price(self):
        """Цена выбранного размера или None, если её у товара нет."""
        return {
            self.SizeChoices.S: self.product.price_s,
            self.SizeChoices.M: self.product.price_m,
            self.SizeChoices.L: self.product.price_l,
        }.get(self.size)

    def effective_addons(self):
        """Добавки, которые реально идут в заказ и оплачиваются.

        Добавка с вкусами — это, по сути, категория: «Сироп» сам по себе не
        заказывается, пока не выбран конкретный вкус. Пока вкуса нет, добавка
        не считается выбранной и денег не стоит.

        Добавка без вкусов (сливки, альтернативное молоко) выбирается сама по
        себе и оплачивается сразу.
        """
        chosen_flavor_ids = {flavor.id for flavor in self.flavors.all()}

        complete = []
        for addon in self.addons.all():
            addon_flavor_ids = {flavor.id for flavor in addon.flavors.all()}
            if addon_flavor_ids and not (addon_flavor_ids & chosen_flavor_ids):
                continue
            complete.append(addon)
        return complete

    @property
    def is_available(self):
        """Позицию ещё можно продать: товар в наличии и у размера есть цена.

        Размер без цены означает «этого объёма нет», а не «стоит ноль». Такая
        позиция может появиться уже после добавления — если администратор
        стёр цену размера, пока корзина лежала у клиента.
        """
        return bool(self.product and self.product.availability and self.size_price() is not None)

    @property
    def item_total_price(self):
        from decimal import Decimal
        product_price = self.size_price()

        if product_price is None:
            # Раньше здесь стояло `or Decimal('0.00')`: у товара без цены
            # выбранного размера позиция считалась бесплатной. Ноль — худший
            # из возможных ответов, поэтому берём минимальную заведённую цену
            # товара и жалуемся в лог; сама позиция помечена is_available=False.
            fallback = [
                price for price in (
                    self.product.price_s, self.product.price_m, self.product.price_l
                ) if price is not None
            ]
            product_price = min(fallback) if fallback else Decimal('0.00')
            logger.warning(
                "У товара {} нет цены размера {} (позиция корзины {}). "
                "Считаем по {}.",
                self.product_id, self.size, self.pk, product_price
            )
        
        # Деньги лежат на добавке и берутся с неё ровно один раз. Раньше к
        # сумме добавок прибавлялась ещё и цена вкуса — той же самой добавки,
        # то есть «Сироп» с выбранным вкусом стоил вдвое дороже, а два вкуса
        # одной добавки — втрое. Вкус денег не добавляет: он говорит, какой
        # именно сироп налить.
        addons_price = sum(
            (addon.price for addon in self.effective_addons() if addon.price),
            Decimal('0.00'),
        )

        return (product_price + addons_price) * self.amount


def get_active_cart(user):
    """
    Активная корзина пользователя, создаётся при необходимости (M7).

    Единственное место, где это решается. Раньше каждый вызывающий делал
    `.get(user=user, is_active=True)` или `get_or_create(...)`, и оба варианта
    падали `MultipleObjectsReturned` (то есть 500), если у пользователя
    почему-либо оказались две активные корзины — а уникальности на уровне БД
    здесь нет, и корзина создаётся ещё и сигналом на регистрацию.

    Ноль корзин, одна или несколько — во всех случаях возвращается одна, самая
    свежая, и никогда не бросается исключение.
    """
    cart = ShoppingCart.objects.filter(user=user, is_active=True).order_by("-id").first()
    if cart is None:
        cart = ShoppingCart.objects.create(user=user, is_active=True)
    return cart
