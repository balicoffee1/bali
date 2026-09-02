"""
ASGI config for island_bali project (M2).

http-часть остаётся get_asgi_application() ради ProtocolTypeRouter/тестов/локального
runserver, но в production nginx на неё ничего не проксирует — HTTP API обслуживается
gunicorn/WSGI (island_bali.wsgi), как и раньше. Реально по этому процессу (daphne)
в production идёт только /ws/* (см. nginx/default.conf, docker-compose*.yml, сервис "ws").

Origin клиента (browser Origin header) сознательно не валидируется на этом уровне:
основной клиент — мобильное Flutter-приложение, которое не отправляет Origin вовсе,
а реальная граница авторизации — JWT + серверные group membership (island_bali.ws_auth,
orders.consumers), а не Origin заголовок.
"""

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE",
                      "island_bali.settings")

from django.core.asgi import get_asgi_application

# Должен быть создан до импорта чего-либо, трогающего модели (стандартное требование
# Channels docs) — иначе AppRegistryNotReady.
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter

from island_bali.ws_auth import JWTAuthMiddlewareStack
from orders.routing import websocket_urlpatterns

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": JWTAuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
    }
)
