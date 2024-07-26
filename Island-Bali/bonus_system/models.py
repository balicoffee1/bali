from io import BytesIO

import qrcode
from django.core.files import File
from django.db import models

from coffee_shop.models import CoffeeShop
from users.models import CustomUser


class DiscountCard(models.Model):
    """
    Модель скидочной карты пользователя.
    """

    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="discount_card",
        verbose_name="Владелец карты",
    )
    is_active = models.BooleanField(default=False,
                                    verbose_name="Статус активации")
    qr_code = models.CharField(max_length=255, unique=True,
                               verbose_name="Код QR-карты")
    qr_code_image = models.ImageField(
        upload_to="qr_codes/",
        blank=True,
        null=True,
        verbose_name="Изображение QR-кода",
    )
    discount_rate = models.FloatField(default=5.0,
                                      verbose_name="Размер скидки (%)")
    coffee_shop = models.ForeignKey(
        CoffeeShop,
        on_delete=models.CASCADE,
        verbose_name="Кофейня, где действует скидка"
    )

    def save(self, *args, **kwargs):
        """
        При сохранении модели генерирует QR-код, если это новая запись.
        """
        if not self.pk:
            super().save(*args, **kwargs)
            self.qr_code = str(self.pk)
            buffer = BytesIO()
            img_qr = qrcode.make(self.qr_code)
            img_qr.save(buffer, format="PNG")
            self.qr_code_image.save(f"qr_code_{self.pk}.png",
                                    File(buffer),
                                    save=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Скидочная карта {self.user} (Кофейня: {self.coffee_shop})"

    class Meta:
        verbose_name = "Скидочная карта"
        verbose_name_plural = "Скидочные карты"
