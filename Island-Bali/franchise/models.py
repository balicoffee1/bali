from django.db import models
from phonenumber_field.modelfields import PhoneNumberField


class FranchiseRequest(models.Model):
    name = models.CharField(max_length=40, verbose_name="Ваше Имя")
    number_phone = PhoneNumberField(
        null=False, blank=False, verbose_name="Номер Телефона"
    )
    text = models.TextField(verbose_name="Ваши Пожелания")

    class Meta:
        verbose_name = "Заявка на франшизу"
        verbose_name_plural = "Заявка на франшизу"


class FranchiseInfo(models.Model):
    text = models.TextField(verbose_name="Информация")

    class Meta:
        verbose_name = "Информация"
        verbose_name_plural = "Информация"
