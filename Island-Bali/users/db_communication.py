import base64

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.files.base import ContentFile
from loguru import logger
from rest_framework_simplejwt.tokens import RefreshToken

from users import utils

from .models import CustomUser


def add_user(values: dict) -> tuple:
    """
    Добавление нового пользователя в базу данных.

    Параметры:
    - values (dict): Данные пользователя (имя пользователя, логин, пароль
    и т.д.).

    Возвращает:
    - token (str): Сгенерированный токен для нового пользователя.
    - user (Users): Вновь созданный экземпляр пользователя.
    """
    login = values["login"]
    first_name = values["first_name"]
    last_name = values["last_name"]
    photo = values.get("photo")
    email = values.get("email")
    phone = None
    if utils.is_phone_number(login):
        phone = login
        if CustomUser.objects.filter(phone_number__exact=phone).exists():
            raise Exception("UNIQUE constraint failed: user.phone_number")

    user = CustomUser.objects.create_user(
        login=login,
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone_number=phone,
        fcm_token=values["fcm_token"],
    )
    logger.debug(f'Created new user with fcm token {values["fcm_token"]}')

    if photo:
        change_photo(user, photo)

    # token_obj, created = Token.objects.get_or_create(user=user)
    # token = token_obj.key
    #
    # return token, user
    refresh = RefreshToken.for_user(user)
    token = {"access": str(refresh.access_token), "refresh": str(refresh)}
    return token, user


def get_user(**kwargs) -> CustomUser:
    login = kwargs.get("login")
    phone_number = None
    if login:
        phone_number = login if utils.is_phone_number(login) else None
    if phone_number:
        user = CustomUser.objects.filter(
            phone_number__exact=phone_number).first()
    else:
        user = CustomUser.objects.filter(**kwargs).first()
    if user:
        if not user.is_active:
            raise Exception(
                "Your account has been blocked. Please, contact support")
    return user


def reset_password1(values):
    login = values["login"]
    # if utils.is_email(login):
    #     user = get_user(login=login)
    #     if not user:
    #         raise ObjectDoesNotExist
    #     code = utils.send_mail_reset(login)
    #
    #     user.code = code
    #     user.save()
    #     return {
    #         "login": login
    #     }

    if utils.is_phone_number(login):
        user = get_user(login=login)
        if not user:
            raise ObjectDoesNotExist
        code = utils.send_phone_reset(login)
        user.code = code
        user.save()
        return {"login": login}
    else:
        raise ValidationError("Invalid login format")


def check_code(values):
    login = values["login"]
    code = values["code"]
    if utils.is_email(login):
        user = get_user(login=login)
    elif utils.is_phone_number(login):
        user = get_user(login=login)
    else:
        raise ValidationError("Invalid login format")
    if not user:
        raise ObjectDoesNotExist

    if not user.code:
        raise Exception("No need a code")
    if user.code == code:
        user.code = 0
        user.save()
        refresh = RefreshToken.for_user(user)
        token = {"access": str(refresh.access_token),
                 "refresh": str(refresh)}
        return {"is_correct": True, "token": token}
    else:
        return {"is_correct": False}


def reset_password2(user, password):
    try:
        user.set_password(password)
        user.save()
    except Exception as ex:
        return ex


def change_photo(user, photo: str):
    if photo:
        format, imgstr = photo.split(";base64,")
        ext = format.split("/")[-1]
        data = ContentFile(base64.b64decode(imgstr),
                           name=f"{user.nickname}_ava.{ext}")
        user.photo = data
    else:
        user.photo = None
    user.save()
