"""
JWT-аутентификация ASGI/WebSocket handshake (M2).

Переиспользует rest_framework_simplejwt — тот же access token, что и REST API,
никакой отдельной auth-системы. Токен передаётся в заголовке
``Authorization: Bearer <token>`` того же handshake-запроса (Flutter mobile
client — dart:io WebSocket поддерживает произвольные заголовки; в отличие от
query-параметра это не попадает ни в access log nginx, ни в application log).

AccessToken(raw_token) уже проверяет подпись и exp при конструировании —
отдельно вызывать validate() не нужно. Anonymous/невалидный/просроченный токен
=> scope["user"] = AnonymousUser(), сам consumer обязан отклонить соединение.
"""
from __future__ import annotations

import logging

from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken

logger = logging.getLogger("island_bali.ws_auth")


def _extract_bearer_token(headers: dict) -> str | None:
    raw = headers.get(b"authorization")
    if not raw:
        return None
    raw = raw.decode("utf-8", errors="ignore")
    if not raw.lower().startswith("bearer "):
        return None
    token = raw[7:].strip()
    return token or None


@database_sync_to_async
def _resolve_user(raw_token: str):
    from django.conf import settings
    from users.models import CustomUser

    try:
        validated = AccessToken(raw_token)
    except TokenError:
        return AnonymousUser(), None

    user_id_claim = settings.SIMPLE_JWT["USER_ID_CLAIM"]
    try:
        user = CustomUser.objects.get(pk=validated[user_id_claim], is_active=True)
    except CustomUser.DoesNotExist:
        return AnonymousUser(), None
    return user, validated["exp"]


class JWTAuthMiddleware:
    """ASGI middleware — резолвит scope["user"]/scope["token_exp"] по Bearer JWT."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        headers = dict(scope.get("headers") or [])
        token = _extract_bearer_token(headers)

        user = AnonymousUser()
        token_exp = None
        if token:
            user, token_exp = await _resolve_user(token)

        scope["user"] = user
        scope["token_exp"] = token_exp
        return await self.app(scope, receive, send)


def JWTAuthMiddlewareStack(app):
    return JWTAuthMiddleware(app)
