from typing import Any

from coffee_shop.models import Acquiring


def get_data_crm_system_for_connection(request, pk) -> tuple[Any, Any, Any]:
    """Получаем логин и пароль для авторизация в апи"""
    credentials = Acquiring.objects.filter(pk=pk)
    return credentials.name, credentials.login, credentials.password
