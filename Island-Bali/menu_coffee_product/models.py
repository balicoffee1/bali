from colorfield.fields import ColorField
from django.db import models

from coffee_shop.models import CoffeeShop


class Season(models.TextChoices):
    """Времена года для сезонного меню.

    Раньше сезона как понятия не было вовсе: раздел отличался только текстом
    в ``seasonal_section`` («Зима», «Весна»), а какие разделы показывать —
    решалось тем, какие записи вообще заведены в базе.
    """

    WINTER = "winter", "Зима"
    SPRING = "spring", "Весна"
    SUMMER = "summer", "Лето"
    AUTUMN = "autumn", "Осень"


# Оформление плиток меню раньше жило в дартовом файле: одиннадцать градиентов
# и три иконки раздавались по кругу через `index % длина списка`. Двенадцатая
# категория получала оформление первой, а поменять цвет без пересборки
# приложения было нельзя. Иконки остаются набором на клиенте — сервер хранит
# ключ, а не картинку.
MENU_ICON_CHOICES = (
    ("palm_tree", "Пальма"),
    ("beach_ball", "Мяч"),
    ("cappuccino", "Капучино"),
    ("latte_art", "Латте-арт"),
    ("banana", "Банан"),
    ("shaker", "Шейкер"),
    ("coconut", "Кокос"),
    ("matcha", "Матча"),
    ("ice_cream", "Мороженое"),
    ("tropical_leaf", "Лист"),
    ("lemon_slice", "Лимон"),
    ("flamingo", "Фламинго"),
    ("sun", "Солнце"),
    ("limonad", "Лимонад"),
    ("smoothie", "Смузи"),
    ("energy_drink", "Энергетик"),
)


class AdditiveFlavors(models.Model):
    """Вкусы добавок"""
    coffee_shop = models.ForeignKey(
        CoffeeShop, on_delete=models.CASCADE,
        verbose_name="Кофейня",
        related_name="additiveflavors_coffe_shop",
        null=True
    )
    name = models.CharField(max_length=255, verbose_name="Название вкуса")
    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Вкус добавки'
        verbose_name_plural = 'Вкусы добавок'


class Addon(models.Model):
    coffee_shop = models.ForeignKey(
        CoffeeShop, on_delete=models.CASCADE,
        verbose_name="Кофейня",
        related_name="addon_coffe_shop",
        null=True
    )
    name = models.CharField(max_length=255, verbose_name="Название добавки")
    description = models.TextField(blank=True, null=True,
                                   verbose_name='Описание добавки')
    price = models.DecimalField(decimal_places=2,
                                max_digits=10,
                                verbose_name='Цена',
                                default=0,null=True, blank=True)
    flavors = models.ManyToManyField(
        AdditiveFlavors,
        verbose_name="Вкусы добавки",
        related_name="additive_flavors",
        blank=True
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Добавка'
        verbose_name_plural = 'Добавки'


class Category(models.Model):
    """Разделы меню"""
    WHICH_MENYU_CHOICES = (
        ('main_menu', 'Основное меню'),
        ('season_menu', 'Сезонное меню'),
        ("both", "Оба меню"),
    )
    coffee_shop = models.ForeignKey(CoffeeShop,
                                    on_delete=models.CASCADE,
                                    related_name='categories',
                                    verbose_name='Кофейня')
    name = models.CharField(max_length=255, verbose_name='Название категории')
    which_menu = models.CharField(
        max_length=20,
        choices=WHICH_MENYU_CHOICES,
        default='main_menu',
        verbose_name='В каком меню находится категория'
    )
    color = ColorField(
        max_length=7,
        blank=True,
        default='',
        verbose_name='Цвет плитки',
        help_text='Пусто — приложение возьмёт цвет из своего набора',
    )
    icon = models.CharField(
        max_length=32,
        choices=MENU_ICON_CHOICES,
        blank=True,
        default='',
        verbose_name='Иконка плитки',
        help_text='Пусто — приложение возьмёт иконку из своего набора',
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'


class Product(models.Model):
    WHICH_MENYU_CHOICES = (
        ('main_menu', 'Основное меню'),
        ('season_menu', 'Сезонное меню'),
        ("both", "Оба меню"),
    )
    PRODUCT_TYPE_CHOICES = (
        ('coffee', 'Кофе'),
        ('ice_cream', 'Мороженое'),
        ('matcha', 'Матча'),
        ('tea', 'Чай'),
        ('cocktail', 'Коктейль'),
        ('fresh_juice', 'Свежевыжатый сок'),

    )
    CAN_BE_HOT_AND_COLD_CHOICES = (
        (True, "Да"),
        (False, "Нет")
    )
    TEMPERATURE_TYPE_CHOICES = (
        ("Hot", "Горячий"),
        ("Cold", "Холодный"),
        ("All", "Все виды"),
    )

    coffee_shop = models.ForeignKey(CoffeeShop, verbose_name='Кофейня',
                                    on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.CASCADE,
                                 related_name='products',
                                 verbose_name='Категория')
    product = models.CharField(
        max_length=100,
        verbose_name='Продукт',
        help_text='Понятное название продукта'
    )
    price = models.DecimalField(decimal_places=2,
                                max_digits=10,
                                verbose_name='Цена',
                                null=True,
                                blank=True,
                                )

    availability = models.BooleanField(default=True, verbose_name='Наличие')

    product_type = models.CharField(max_length=50,
                                    choices=PRODUCT_TYPE_CHOICES,
                                    verbose_name="Тип продукта")
    addons = models.ManyToManyField(Addon, verbose_name='Добавки', blank=True)
    can_be_hot_and_cold = models.BooleanField(
        default=False,
        verbose_name="Доступен как в горячем, так и в холодном виде?",
        choices=CAN_BE_HOT_AND_COLD_CHOICES
    )
    temperature_type = models.CharField(
        max_length=4,
        choices=TEMPERATURE_TYPE_CHOICES,
        verbose_name="Тип температуры напитка",
        default="Hot"
    )
    price_s = models.DecimalField(
        decimal_places=2,
        max_digits=10,
        verbose_name='Цена размера S',
        null=True,
        blank=True
    )
    price_m = models.DecimalField(
        decimal_places=2,
        max_digits=10,
        verbose_name='Цена размера M',
        null=True,
        blank=True
    )
    price_l = models.DecimalField(
        decimal_places=2,
        max_digits=10,
        verbose_name='Цена размера L',
        null=True,
        blank=True
    )
    which_menu = models.CharField(
        max_length=20,
        choices=WHICH_MENYU_CHOICES,
        default='main_menu',
        verbose_name='В каком меню находится продукт'
    )

    def __str__(self):
        return f"Название продукта {self.product}"

    class Meta:
        verbose_name = 'Продукт'
        verbose_name_plural = 'Продукты'
        indexes = (models.Index('product', name='product'),)
        constraints = (
            # Раньше на названии стоял глобальный unique=True: «Латте» мог
            # существовать в сети ровно один раз и принадлежать ровно одной
            # точке. Из-за этого add_to_cart искал товар только по имени и
            # игнорировал кофейню из URL, а вторая кофейня сети потребовала бы
            # переименования всего меню. Уникальность нужна в пределах точки.
            models.UniqueConstraint(
                fields=('coffee_shop', 'product'),
                name='unique_product_per_coffee_shop',
            ),
        )


class SeasonMenu(models.Model):
    coffee_shop = models.ForeignKey(CoffeeShop, on_delete=models.CASCADE,
                                    verbose_name="Кофейня",
                                    related_name='season_menus')
    season = models.CharField(
        max_length=10,
        choices=Season.choices,
        default=Season.WINTER,
        verbose_name="Время года",
    )
    seasonal_section = models.CharField(max_length=255,
                                        verbose_name="Раздел сезонного меню")
    is_active = models.BooleanField(
        default=True,
        verbose_name="Показывать в приложении",
        help_text='Каждая кофейня держит наборы на все четыре сезона и '
                  'включает нужный. Раньше для этого перезапускали seed_menu.',
    )
    color = ColorField(
        max_length=7,
        blank=True,
        default='',
        verbose_name='Цвет плитки',
        help_text='Пусто — приложение возьмёт цвет из своего набора',
    )
    icon = models.CharField(
        max_length=32,
        choices=MENU_ICON_CHOICES,
        blank=True,
        default='',
        verbose_name='Иконка плитки',
        help_text='Пусто — приложение возьмёт иконку из своего набора',
    )
    products = models.ManyToManyField(Product,
                                      verbose_name="Продукты")

    def __str__(self):
        return (
            f"{self.get_season_display()}: {self.seasonal_section} "
            f"в {self.coffee_shop.city}"
        )

    class Meta:
        verbose_name = "Сезонное меню"
        verbose_name_plural = "Сезонное меню"
        ordering = ('coffee_shop_id', 'season', 'id')
        constraints = (
            # Раздел уникален внутри пары «кофейня + сезон»: повторный
            # get_or_create в seed_menu иначе плодит одинаковые разделы.
            models.UniqueConstraint(
                fields=('coffee_shop', 'season', 'seasonal_section'),
                name='unique_season_section_per_shop',
            ),
        )
