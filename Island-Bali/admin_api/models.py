from django.db import models
from users.models import CustomUser


class AdminActivityLog(models.Model):
    ACTION_CHOICES = (
        ('CREATE', 'Создание'),
        ('UPDATE', 'Изменение'),
        ('DELETE', 'Удаление'),
        ('STATUS_CHANGE', 'Смена статуса'),
        ('LOGIN', 'Вход в систему'),
    )

    user = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admin_activity_logs",
        verbose_name="Администратор",
    )
    action = models.CharField(
        max_length=20,
        choices=ACTION_CHOICES,
        default='UPDATE',
        verbose_name="Действие",
    )
    entity_name = models.CharField(
        max_length=100,
        verbose_name="Сущность",
    )
    entity_id = models.CharField(
        max_length=50,
        verbose_name="ID сущности",
        blank=True,
        default="",
    )
    summary = models.CharField(
        max_length=255,
        verbose_name="Краткое описание действия",
        blank=True,
        default="",
    )
    changes = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Детали изменений (diff)",
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="IP адрес",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Время действия",
    )

    class Meta:
        verbose_name = "Журнал действия администратора"
        verbose_name_plural = "Журнал действий администраторов"
        ordering = ["-created_at"]

    def __str__(self):
        actor = self.user.login if self.user else "Система"
        return f"[{self.created_at:%Y-%m-%d %H:%M}] {actor} - {self.action} {self.entity_name} #{self.entity_id}"
