from django.db import models


class City(models.Model):
    name = models.CharField(max_length=100, verbose_name="Название города")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Город"
        verbose_name_plural = "Города"


class CrmSystem(models.Model):
    CRM_SYSTEM = (
        ("QuickRestoApi", "QuickRestoApi"),
        ("SubTotal", "SubTotal"),
    )
    name = models.CharField(max_length=100, choices=CRM_SYSTEM,
                            verbose_name="CRM-Система")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "CRM Система"
        verbose_name_plural = "CRM Система"


class Acquiring(models.Model):
    ACQUIRING = (
        ("RussianStandart", "Русский Стандарт"),
        ("AlfaBank", "Альфа Банк"),
        ("Tinkoff Bank", "Тиньков Банк"),
    )
    for_coffeeshop = models.CharField(verbose_name="Название кофейни",
                                      max_length=120)
    name = models.CharField(max_length=100, choices=ACQUIRING)
    login = models.CharField(max_length=100, verbose_name="Логин")
    password = models.CharField(max_length=100, editable=True)

    def __str__(self):
        return f'{self.name} {self.for_coffeeshop}'

    class Meta:
        verbose_name = "Эквайринг"
        verbose_name_plural = "Эквайринги"


class CoffeeShop(models.Model):
    city = models.ForeignKey(City, on_delete=models.CASCADE,
                             verbose_name="Город")
    street = models.CharField(max_length=120, verbose_name="Улица")
    building_number = models.CharField(max_length=15,
                                       verbose_name="Номер строения")
    email = models.EmailField(
        verbose_name="Почта для получения плохих отзывов", blank=False,
        null=False,
        help_text="Пожалуйста введите вашу почту чтобы вы "
                  "могли контролировать отзывы)")
    

    telegram_username = models.CharField(max_length=20,
                                         verbose_name="Username в Telegram. "
                                                      "Пример <@col1ecti0n>",
                                         help_text="Введите ваш username "
                                                   "из Telegram")
    
    telegram_id = models.CharField(
        max_length=100,
        verbose_name="Username в Telegram. "
        "Пример <@col1ecti0n>",
        help_text="Введите ваш username "
        "из Telegram",
        null=True,
        blank=True              
    )
    

    crm_system = models.ForeignKey(CrmSystem, max_length=20,
                                      verbose_name="CRM-Система",
                                      on_delete=models.CASCADE)
    acquiring = models.ForeignKey(Acquiring, verbose_name="Эквайринг",
                                     on_delete=models.CASCADE)
    time_open = models.TimeField(verbose_name="Время открытия заведения",
                                 default='10:00')
    time_close = models.TimeField(verbose_name="Время закрытия заведения",
                                  default='23:00')
    password = models.CharField(max_length=20, default='')
    lat = models.DecimalField(
        max_digits=100,
        decimal_places=10,
        verbose_name=("Долгота"),
        default=0
    )
    lon = models.DecimalField(
        max_digits=10,
        decimal_places=10,
        verbose_name=("Широта"),
        default=0
    )

    def __str__(self):
        return f"{self.street}, {self.city.name}"

    class Meta:
        verbose_name = "Кофейня"
        verbose_name_plural = "Кофейни"
