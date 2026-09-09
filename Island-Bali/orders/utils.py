"""Модуль намеренно пуст.

Здесь лежал набор функций, который не импортировался ни из одного места:
``get_menu_item``, ``get_or_create_user_cart``, ``add_or_update_cart_item``,
``get_city_and_coffee_shop``, ``process_cart_item`` и
``check_temperature_requirements``. Часть из них была уже нерабочей —
``add_or_update_cart_item`` обращался к ``cart_item.quantity``, которого у
``CartItem`` нет.

Опаснее всего был ``check_temperature_requirements``: он выглядел как
действующая проверка температуры напитка, но не вызывался никогда, и из-за
него казалось, что правила («коктейли только холодные», «для кофе
температура обязательна») где-то работают.

Актуальные проверки — ``resolve_temperature`` и ``resolve_size`` в
``cart/views.py``. Правило «каким бывает напиток» задаётся полем
``Product.temperature_type`` в админке, а не списком product_type в коде.

Историю удалённого кода можно поднять из git.
"""
