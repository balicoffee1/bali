# Happy Island Admin Panel

Web Admin Panel на React 18, TypeScript, Vite и Tailwind CSS. Рабочий API ожидается по префиксу `/api/admin/` и проксируется на Django `http://127.0.0.1:8000`.

## Запуск

```bash
npm install
npm run dev
```

Для изолированной демонстрации без Django mock-режим включается только явно:

```bash
VITE_USE_MOCK_API=true npm run dev
```

Демо-учётная запись: `+79172340001`, пароль `demo`.

## Проверки

```bash
npm run build
```

После установки backend-зависимостей примените новые миграции и выполните системную проверку:

```bash
cd ../Island-Bali
python manage.py migrate
python manage.py check
```

Переменные окружения backend, добавленные для Admin Panel:

- `CORS_ALLOWED_ORIGINS` — список разрешённых origins, по умолчанию локальные адреса Vite;
- `ACCESS_TOKEN_LIFETIME_HOURS` — срок access JWT, по умолчанию 1 час;
- `ADMIN_LOGIN_THROTTLE_RATE` — лимит попыток входа, по умолчанию `10/min`;
- `SMS_LOGIN`, `SMS_PASSWORD`, `ONESIGNAL_APP_ID`, `ONESIGNAL_API_KEY` — секреты интеграций, которые не должны храниться в коде.
