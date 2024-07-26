from django.db import models

from coffee_shop.models import CoffeeShop


class Addon(models.Model):
    name = models.CharField(max_length=255, verbose_name="Название добавки")
    description = models.TextField(blank=True, null=True,
                                   verbose_name='Описание добавки')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Добавка'
        verbose_name_plural = 'Добавки'


class Category(models.Model):
    """Разделы меню"""
    coffee_shop = models.ForeignKey(CoffeeShop,
                                    on_delete=models.CASCADE,
                                    related_name='categories',
                                    verbose_name='Кофейня')
    name = models.CharField(max_length=255, verbose_name='Название категории')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'


class Product(models.Model):
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
    category = models.ForeignKey(Category, on_delete=models.SET('undefined'),
                                 related_name='products',
                                 verbose_name='Категория')
    product = models.CharField(
        max_length=100,
        unique=True,
        verbose_name='Продукт',
        help_text='Понятное название продукта'
    )
    price = models.DecimalField(decimal_places=2,
                                max_digits=10,
                                verbose_name='Цена',
                                )

    availability = models.BooleanField(default=True, verbose_name='Наличие')

    product_type = models.CharField(max_length=50,
                                    choices=PRODUCT_TYPE_CHOICES,
                                    verbose_name="Тип продукта")

    product_photo = models.ImageField(verbose_name='Фото продукта',
                                      upload_to='images/', blank=True,
                                      null=True)
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

    def __str__(self):
        return f"Название продукта {self.product}"

    class Meta:
        verbose_name = 'Продукт'
        verbose_name_plural = 'Продукты'
        indexes = (models.Index('product', name='product'),)
        unique_together = ('coffee_shop', 'product')


class SeasonMenu(models.Model):
    coffee_shop = models.ForeignKey(CoffeeShop, on_delete=models.CASCADE,
                                    verbose_name="Кофейня")
    seasonal_section = models.CharField(max_length=255,
                                        verbose_name="Раздел сезонного меню")
    products = models.ManyToManyField(Product,
                                      verbose_name="Продукты")

    def __str__(self):
        return f"{self.seasonal_section} в {self.coffee_shop.city}"

    class Meta:
        verbose_name = "Сезонное меню"
        verbose_name_plural = "Сезонное меню"
