from django.db import models
from phonenumber_field.modelfields import PhoneNumberField


class FranchiseRequest(models.Model):
    STATUS_CHOICES = (
        ('new', 'Новая'),
        ('in_progress', 'В работе'),
        ('completed', 'Договор заключен'),
        ('rejected', 'Отклонена'),
    )

    name = models.CharField(max_length=40, verbose_name="Ваше Имя")
    number_phone = PhoneNumberField(
        null=False, blank=False, verbose_name="Номер Телефона"
    )
    text = models.TextField(verbose_name="Ваши Пожелания")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='new',
        verbose_name='Статус обработки',
    )
    manager_comment = models.TextField(blank=True, default='', verbose_name='Комментарий менеджера')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата заявки')

    class Meta:
        verbose_name = "Заявка на франшизу"
        verbose_name_plural = "Заявка на франшизу"
        ordering = ['-created_at']


class FranchiseInfo(models.Model):
    text = models.TextField(verbose_name="Информация")

    class Meta:
        verbose_name = "Информация"
        verbose_name_plural = "Информация"
