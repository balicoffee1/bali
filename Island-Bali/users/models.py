from cryptography.fernet import Fernet
from django.contrib.auth.models import (AbstractBaseUser, BaseUserManager,
                                        PermissionsMixin)
from django.utils.crypto import get_random_string

from django.db import models
from phonenumber_field.modelfields import PhoneNumberField


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
    is_active = models.BooleanField(default=False,
                                    verbose_name="Статус активности")
    phone_number = PhoneNumberField(verbose_name="Телефон", max_length=23)
    email = models.CharField(
        max_length=100, blank=True, null=True, verbose_name="Почта"
    )
    fcm_token = models.CharField(max_length=500, null=True, blank=True)
    role = models.CharField(default="user", choices=ROLE_CHOICES,
                            max_length=12)
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
    
    def create_activation_code(self):
        code = get_random_string(length=4, allowed_chars='1234567890')
        self.fcm_token = code
        self.save()

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
    def is_user(self):
        return self.role == "user"

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


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
    expiration_date = models.DateField(verbose_name="Дата истечения")

    @staticmethod
    def create_new_card(user, card_number, expiration_date):
        new_card = UserCard(user=user, expiration_date=expiration_date, card_number=card_number)
        new_card.save()
        return new_card
    
    def get_card_number(self):
        if self.card_number:
            return self.card_number
        return None


