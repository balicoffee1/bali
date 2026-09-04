import hashlib
from datetime import timedelta

from cryptography.fernet import Fernet
from django.conf import settings
from django.contrib.auth.models import (AbstractBaseUser, BaseUserManager,
                                        PermissionsMixin)
from django.utils import timezone

from django.db import models
from phonenumber_field.modelfields import PhoneNumberField
from fcm_django.models import FCMDevice


class CustomUserManager(BaseUserManager):
    def create_user(self, login, password=None, **extra_fields):
        if not login:
            raise ValueError("The Login field must be set")

        extra_fields.setdefault("is_active", True)
        user = self.model(login=login, **extra_fields)
        if password is not None:
            user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, login, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(login, password, **extra_fields)


class CustomUser(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = (
        ("owner", "Владелец"),
        ("admin", "Администратор"),
        ("moderator", "Модератор"),
        ("support", "Служба поддержки"),
        ("employee", "Сотрудник"),
        ("user", "Пользователь"),
    )
    login = models.CharField(max_length=100, unique=True, verbose_name="Логин")
    first_name = models.CharField(max_length=30, verbose_name="Имя")
    last_name = models.CharField(max_length=50, verbose_name="Фамилия", blank=True, null=True, default='')
    code = models.IntegerField(blank=True, null=True)
    photo = models.ImageField(
        null=True, blank=True, upload_to="media/", verbose_name="Аватарка"
    )
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True,
                                    verbose_name="Статус активности")
    phone_number = PhoneNumberField(verbose_name="Телефон", max_length=23)
    email = models.CharField(
        max_length=100, blank=True, null=True, verbose_name="Почта"
    )
    fcm_token = models.CharField(max_length=500, null=True, blank=True)
    role = models.CharField(default="user", choices=ROLE_CHOICES,
                            max_length=12, verbose_name="Роль пользователя")
    chosen_card = models.OneToOneField(
        "UserCard",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="Выбранная банковская карта",
    )


    objects = CustomUserManager()

    USERNAME_FIELD = "login"
    REQUIRED_FIELDS = []
    
    class Meta:
        managed = True
        db_table = "users"
        verbose_name_plural = "Пользователи"
        verbose_name = "Пользователь"

    @property
    def is_admin(self):
        return self.role == "admin"

    @property
    def is_moderator(self):
        return self.role == "moderator"

    @property
    def is_support(self):
        return self.role == "support"

    @property
    def is_user(self):
        return self.role == "user"

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    def has_device(self):
        return FCMDevice.objects.filter(user=self).exists()



class EncryptionKey(models.Model):
    key = models.BinaryField()


class UserCard(models.Model):
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="cards",
        verbose_name="Пользователь",
    )
    card_number = models.CharField(
        max_length=100, null=True, verbose_name="Зашифрованный номер карты"
    )
    expiration_date = models.CharField(verbose_name="Дата истечения", default='', max_length=10)

    @staticmethod
    def create_new_card(user, card_number, expiration_date):
        new_card = UserCard(user=user, expiration_date=expiration_date, card_number=card_number)
        new_card.save()
        return new_card
    
    def get_card_number(self):
        if self.card_number:
            return self.card_number
        return None
    
    def __str__(self):
        return f"Карта пользователя {self.user.login} с номером {self.card_number}"
    
    class Meta:
        verbose_name = ("Карта пользователя")
        verbose_name_plural = ("Карты пользователей")



class PhoneVerification(models.Model):
    """
    Одноразовый код подтверждения номера телефона.

    Код хранится только в виде хеша, живёт ограниченное время и выдерживает
    ограниченное число попыток ввода. Привязан к номеру, а не к пользователю,
    чтобы работать и для ещё не зарегистрированных номеров.
    """

    MAX_ATTEMPTS = 5

    phone = models.CharField(
        max_length=20, db_index=True, verbose_name="Телефон"
    )
    code_hash = models.CharField(max_length=128, verbose_name="Хеш кода")
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name="Создан"
    )
    expires_at = models.DateTimeField(verbose_name="Истекает")
    attempts = models.PositiveSmallIntegerField(
        default=0, verbose_name="Попыток ввода"
    )
    is_used = models.BooleanField(
        default=False, verbose_name="Использован"
    )

    class Meta:
        db_table = "users_phone_verification"
        ordering = ("-created_at",)
        verbose_name = "Код подтверждения телефона"
        verbose_name_plural = "Коды подтверждения телефона"

    def __str__(self):
        return f"Код для {self.phone} (использован: {self.is_used})"

    @staticmethod
    def hash_code(code: str) -> str:
        return hashlib.sha256(
            f"{settings.SECRET_KEY}:{code}".encode("utf-8")
        ).hexdigest()

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    @property
    def is_spent(self) -> bool:
        return self.is_used or self.is_expired or self.attempts >= self.MAX_ATTEMPTS

    @classmethod
    def issue(cls, phone: str, code: str) -> "PhoneVerification":
        """Гасит прежние коды номера и создаёт новый."""
        cls.objects.filter(phone=phone, is_used=False).update(is_used=True)
        return cls.objects.create(
            phone=phone,
            code_hash=cls.hash_code(code),
            expires_at=timezone.now() + timedelta(
                seconds=settings.SMS_CODE_TTL
            ),
        )

    @classmethod
    def latest_for(cls, phone: str):
        return cls.objects.filter(phone=phone).order_by("-created_at").first()

    @classmethod
    def verify(cls, phone: str, code: str) -> tuple:
        """
        Проверяет код. Возвращает (успех, текст ошибки).
        Успешная проверка гасит код, неуспешная — увеличивает счётчик попыток.
        """
        verification = cls.latest_for(phone)
        if verification is None:
            return False, "Код не запрашивался. Запросите новый код."
        if verification.is_used:
            return False, "Код уже использован. Запросите новый код."
        if verification.is_expired:
            return False, "Срок действия кода истёк. Запросите новый код."
        if verification.attempts >= cls.MAX_ATTEMPTS:
            return False, "Превышено число попыток. Запросите новый код."

        if verification.code_hash != cls.hash_code(str(code)):
            verification.attempts += 1
            verification.save(update_fields=["attempts"])
            return False, "Неверный код."

        verification.is_used = True
        verification.save(update_fields=["is_used"])
        return True, ""
