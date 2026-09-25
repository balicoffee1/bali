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


class KnowledgeCategory(models.Model):
    slug = models.SlugField(max_length=100, unique=True, verbose_name="Идентификатор (slug)")
    name = models.CharField(max_length=150, verbose_name="Название отдела/категории")
    icon_name = models.CharField(max_length=50, default="BookOpen", blank=True, verbose_name="Иконка")
    order = models.PositiveIntegerField(default=0, verbose_name="Порядок сортировки")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")

    class Meta:
        verbose_name = "Категория базы знаний"
        verbose_name_plural = "Категории базы знаний"
        ordering = ["order", "id"]

    def __str__(self):
        return self.name


class KnowledgeArticle(models.Model):
    ROLE_CHOICES = (
        ('all', 'Для всех ролей'),
        ('barista', 'Бариста'),
        ('manager', 'Управляющий'),
        ('owner', 'Только Owner (Владелец)'),
        ('admin', 'Администратор'),
    )

    MOCKUP_CHOICES = (
        ('none', 'Без мокапа'),
        ('mobile-order', 'Экран мобильного заказа'),
        ('order-card', 'Карточка заказа Live Desk'),
        ('telegram-bot', 'Сообщение в Telegram-боте'),
        ('push-preview', 'Экран Push-уведомления'),
        ('shift-card', 'Карточка смены'),
        ('acquiring-card', 'Терминал эквайринга'),
    )

    category = models.ForeignKey(
        KnowledgeCategory,
        on_delete=models.CASCADE,
        related_name="articles",
        verbose_name="Категория / Отдел",
    )
    title = models.CharField(max_length=255, verbose_name="Заголовок статьи")
    slug = models.SlugField(max_length=150, unique=True, verbose_name="URL-слаг статьи")
    target_role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='all',
        verbose_name="Целевая роль",
    )
    why_needed = models.TextField(blank=True, default="", verbose_name="Зачем это нужно?")
    what_is_it = models.TextField(blank=True, default="", verbose_name="Что это такое?")
    steps = models.JSONField(default=list, blank=True, verbose_name="Шаги инструкции (список)")
    troubleshooting = models.JSONField(default=list, blank=True, verbose_name="Частые ошибки (список)")
    mockup_type = models.CharField(
        max_length=30,
        choices=MOCKUP_CHOICES,
        default='none',
        verbose_name="Тип мокапа",
    )
    quick_action = models.JSONField(default=dict, blank=True, verbose_name="Быстрое действие (переход)")
    tags = models.JSONField(default=list, blank=True, verbose_name="Теги")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    class Meta:
        verbose_name = "Статья базы знаний"
        verbose_name_plural = "Статьи базы знаний"
        ordering = ["category__order", "id"]

    def __str__(self):
        return f"{self.category.name} - {self.title}"

