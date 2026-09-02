# Happy Island — M0 + M1: Order Security, Payment State Machine, Atomic Transitions

Итоговый отчёт по реализации M0 (P0 security fixes) и M1 (канонические state machine заказа/оплаты, атомарные переходы, payment deadline/grace, конкурентность). WebSocket **не реализовывался** — вне скоупа этой фазы, как и было указано.

Все файлы уже записаны в `/Users/egor/Projects/bali/Island-Bali` (часть — через прямые правки в вашем локальном шелле, часть — через staging из отдельной песочницы; список — раздел A). Ссылка на исходный аудит: `docs/order-status-websocket-audit.md`.

**Важно сразу**: реальный прогон тестов и миграций в этой сессии не выполнялся — ни у меня, ни в вашем окружении на Mac нет рабочего Django (нет сети до PyPI ни в облачной песочнице, ни в шелле на компьютере; Docker CLI на компьютере не найден). Подробности и точные команды для запуска — в разделах G и J.

---

## A. Изменённые/новые файлы

### Через облачную песочницу → записаны в ваш репозиторий (`device_commit_files`)

| Файл | Тип изменения |
|---|---|
| `island_bali/settings.py` | `DEFAULT_PERMISSION_CLASSES` → `IsAuthenticated`; добавлен `LOGGING` для `orders.state/signals/tasks`, `acquiring.providers/views` |
| `island_bali/urls.py` | явный `AllowAny` на token refresh/verify; удалён `PaymentChangeStatus` |
| `orders/models.py` | +`version`, `payment_deadline_at`, `payment_started_at`, `provider_paid_at`; удалены `confirm_order/cancel_order/complete_order/process_payment`, `PaymentMethod`; +`PaymentWebhookEvent`, `PaymentReconciliation` |
| `orders/state_machine.py` | **новый**. Канонические таблицы переходов Order/Payment, timing-константы |
| `orders/services.py` | **новый**. `OrderStateService` — единственная точка мутации |
| `orders/tasks.py` | переписан: `evaluate_payment_deadline_task` / `finalize_payment_window_task` |
| `orders/signals.py` | переписан: тестовый заказ через сервис; `payment_deadline_at` + Celery-таймауты через `transaction.on_commit` |
| `orders/views.py` | переписан: IDOR-фиксы, всё через `OrderStateService` |
| `orders/serializers.py` | `OrderStatusUpdateSerializer` → валидатор без `.save()`; `StaffOrderUpdateSerializer` лишён доступа к status-полям |
| `orders/tests.py` | **новый**. См. раздел G |
| `orders/migrations/0004_order_state_machine_m1.py` | **новый**. См. раздел H |
| `acquiring/views.py` | переписан: `PaymentChangeStatus` удалён; `create_invoice`/`lifepay_callback`/`LifePayCallbackView`/`check_lifepay_status` — IDOR-фиксы + перепроверка webhook через API LifePay |
| `acquiring/providers.py` | **новый**. Единая нормализация статуса LifePay |
| `staff/views.py` | IDOR-фиксы (`is_staff_for_order`) на всех order-мутирующих action; всё через `OrderStateService` |
| `staff/utils.py` | удалены прямые мутации `status_orders/payment_status`; добавлен `is_staff_for_order` |
| `admin_api/views.py` | `AdminOrdersViewSet.update_status` → `OrderStateService.admin_override` |
| `admin_api/serializers.py` | `AdminOrderSerializer.status_orders/payment_status` → `read_only_fields` |
| `franchise/views.py` | явный `AllowAny` на публичные формы (иначе сломались бы после флипа) |

### Прямыми правками в вашем шелле на Mac (уже применены, никуда коммитить не нужно)

| Файл | Изменение |
|---|---|
| `subtotal_api/views.py` | `GetDiscountForUser`: `AllowAny` → `IsAuthenticated` (анонимный lookup чужой скидки по phone_number) |
| `menu_coffee_product/views.py` | явный `AllowAny` на `CategoryViewSet/ProductViewSet/ProductListInCategory/AddonList/AdditiveFlavorsList` (публичное меню); `SeasonMenuViewSet` **не** тронут — остался `IsAuthenticated` по умолчанию |
| `seo/views.py` | `ColorModelViewSet/MarkdownModelViewSet`: `AllowAny` → `IsAuthenticatedOrReadOnly` (был полностью открытый CRUD) |

Также перемещён (не удалён — не было прав на `rm`) стрёмный технический файл `.staging_src.tar.gz` → `_to_delete/.staging_src.tar.gz` в корне репозитория; можете удалить эту папку сами.

**Не тронуто намеренно** (не в скоупе M0/M1, вне мобильного контракта или уже безопасно благодаря флипу default-permission): `bonus_system/views.py::get_discount_card_from_user` и `users/qr_code_view.py::GenerateQRCodeView` уже не имели явного `permission_classes` — стали `IsAuthenticated` автоматически, без правок; `music_api`, `quickresto`, `reviews`, `ref_system` — не меняли (см. §I).

---

## B. Финальные state machine (таблицы)

### Order status

| Target ↓ / Current → | New | Waiting | In Progress | Completed | Canceled |
|---|---|---|---|---|---|
| **Waiting** | ✅ | — | — | — | — |
| **In Progress** | — | ✅ | — | — | — |
| **Completed** | — | — | ✅ | — | — |
| **Canceled** | ✅ | ✅ | ✅ | — | — |

`Completed`/`Canceled` — терминальные: из них **нет** ни одного разрешённого перехода (включая admin-путь без явного `admin_override`).

### Payment status

| Target ↓ / Current → | New | Pending | Paid | Failed |
|---|---|---|---|---|
| **Pending** | ✅ | — | — | — |
| **Paid** | ✅ | ✅ | — | — |
| **Failed** | ✅ | ✅ | — | — |

`Paid`/`Failed` — терминальные. `Paid` разрешён и из `New` — провайдер может подтвердить оплату быстрее, чем backend записал `payment_started`.

Обе машины **независимы**: `payment_succeeded()` — единственное место, которое трогает оба поля одновременно (переводит `status_orders: New/Waiting → In Progress` **только** вместе с `payment_status → Paid`, и только если заказ не терминален).

---

## C. Payment timing policy — подтверждение

```
payment_window   = 90 сек   (Orders.state_machine.PAYMENT_WINDOW_SECONDS)
grace period     = 30 сек   (GRACE_PERIOD_SECONDS)
финальный дедлайн = 120 сек (FINAL_DEADLINE_SECONDS)
```

- `payment_deadline_at` вычисляется **один раз** в `orders/signals.py::initialize_payment_window` при создании заказа (`now() + 90s`) и никогда не пересчитывается.
- `evaluate_payment_deadline_task` — Celery `countdown=90`; `finalize_payment_window_task` — `countdown=120`. Обе — тонкие обёртки над `OrderStateService`, не содержат бизнес-логики сами.
- Судит по **provider-заявленному** времени оплаты (`provider_paid_at` из ответа LifePay), а не по времени получения webhook — см. `acquiring/providers.py::ProviderPaymentStatus.provider_paid_at`.
- `payment_started()` сам отклоняет новую попытку оплаты после `payment_deadline_at` (`payment_window_closed`) — это backend-authority, а не только UI-таймер.
- Граничные случаи (Case A: оплата не начата / Case C: PENDING на 90s, ждём grace / провайдер подтверждает ровно на границе / поздний платёж после отмены) реализованы в `OrderStateService.evaluate_payment_deadline`/`finalize_payment_window` — покрыты тестами a–i в `orders/tests.py`.

---

## D. Инвентаризация точек мутации статуса заказа

| # | Метод / endpoint | Актёр | До | После |
|---|---|---|---|---|
| 1 | `OrderViewSet.perform_create` | клиент | создаёт заказ (default `New`) | не менялось — не мутация статуса |
| 2 | `OrderViewSet.confirm_orders` (`/confirm/`) | staff (не используется мобильным) | `Orders.get(pk)` без auth, вызывал удалённый `confirm_order()` | `is_staff_for_order` + `OrderStateService.accept` |
| 3 | `OrderViewSet.cancel_orders` (`/cancel/`) | клиент (**используется мобильным**) | `Orders.get(pk)` без owner-фильтра — IDOR P0 | ownership-check + `OrderStateService.cancel` |
| 4 | `OrderViewSet.complete_order` (`/complete/`) | не используется мобильным | вызывал удалённый `complete_order()` | `OrderStateService.complete` (owner-scoped, как было) |
| 5 | `OrderViewSet.pay_order` (`/pay/`) | не используется мобильным | вызывал удалённые `process_payment`/`PaymentMethod` — ImportError | `OrderStateService.payment_started` |
| 6 | `OrderViewSet.client_confirmation` | клиент (**используется мобильным**) | прямой `order.client_confirmed=True; save()` | `OrderStateService.client_confirmed` |
| 7 | `OrderViewSet.staff_update` (`/staff-update/`) | staff, не используется мобильным | `StaffOrderUpdateSerializer` писал **любое** поле, включая status_orders/payment_status/version — P0 | serializer лишён этих полей + staff-scoping |
| 8 | `OrderStatusUpdateView` (`/orders/<id>/status/`) | клиент, не используется мобильным | raw `status_orders` через ModelSerializer.save() | только `Canceled` разрешён, через сервис |
| 9 | `PaymentView` (`/orders/<id>/pay/`) | не используется мобильным | вызывал удалённые методы | `OrderStateService.payment_started` |
| 10 | `staff/views.py::PendingOrdersAcceptView.post` (`/api/staff/`) | staff (**используется мобильным**) | `update_order_status()` безусловно форсировал Waiting поверх ЛЮБОГО статуса, без auth — P0 | `is_staff_for_order` + `OrderStateService.accept` |
| 11 | `PendingOrdersAcceptView.delete` (`/api/staff/`) | staff (**используется мобильным**) | `cancel_order_with_comment()` форсировал Canceled поверх Completed — P0 | scoping + `OrderStateService.cancel` |
| 12 | `CompleteOrdersView.post` (`/api/staff/complete_order/`) | staff (**используется мобильным**) | проверял "In Progress", но без auth и без atomic | scoping + `OrderStateService.complete` |
| 13 | `acquiring/views.py::create_invoice` | клиент (**используется мобильным**) | IDOR (любой order_id), `order.status='pending'` — несуществующее поле, тихо ничего не сохраняло | ownership + `OrderStateService.payment_started` |
| 14 | `acquiring/views.py::lifepay_callback` + `LifePayCallbackView` (webhooks) | внешний провайдер | доверял `status` из тела запроса напрямую | перепроверка через `get_lifepay_transaction_status` (API LifePay), затем `OrderStateService` |
| 15 | `acquiring/views.py::check_lifepay_status` | клиент (**используется мобильным**) | доверял телу ответа LifePay напрямую, `verify=False` (TLS отключён) | перепроверка + сервис, `verify=True` |
| 16 | `acquiring/views.py::SBPPaymentCreateView` | не используется мобильным | безусловно PAID+Completed, без auth, без return — P0, крашился | ownership + `OrderStateService.payment_started` |
| 17 | `acquiring/views.py::PaymentChangeStatus` | — | **полностью анонимный** force-PAID любого заказа — P0 | **endpoint удалён** (код + URL) |
| 18 | `admin_api/views.py::AdminOrdersViewSet.update_status` | admin | прямой `order.save()`, без atomic/version, но с audit-логом | `OrderStateService.admin_override` (atomic + audit внутри сервиса) |
| 19 | `admin_api/views.py::AdminOrdersViewSet` (обычный PATCH/PUT) | admin | `AdminOrderSerializer` делал status_orders/payment_status обычными writable-полями — обходил №18 целиком | `read_only_fields` — обход больше невозможен |
| 20 | `orders/signals.py::set_waiting_status_for_testing_order` | система (`is_testing`) | форсировал Waiting на **каждый** save(), невалидным `payment_status="Waiting"` | один раз при создании, через `OrderStateService.accept` |
| 21 | Celery: `cancel_unpaid_order_task` (старый) | система | один недетерминированный таск на 90с | `evaluate_payment_deadline_task`(90s) + `finalize_payment_window_task`(120s), оба через сервис |

**Итог**: 21 обнаруженная точка мутации; после M1 — 0 точек мимо `OrderStateService`.

---

## E. P0/P1 из исходного аудита — статус

| ID (см. `docs/order-status-websocket-audit.md`) | Проблема | Статус |
|---|---|---|
| P0: IDOR `confirm_orders`/`cancel_orders` | любой пользователь меняет чужой заказ | ✅ исправлено (см. D.2, D.3) |
| P0: `PaymentChangeStatus` анонимный force-PAID | ✅ endpoint удалён |
| P0: `staff_update`/`StaffOrderUpdateSerializer` | raw доступ ко всем полям | ✅ исправлено |
| P0: `/api/staff/` accept/cancel без auth и без state-check | ✅ исправлено |
| P0: `SBPPaymentCreateView` без auth, не возвращал Response | ✅ исправлено |
| P1: `complete_order()`/`process_payment()` — вызовы несуществующих/сломанных методов | ✅ методы удалены, заменены сервисом |
| P1: `order.status` vs `status_orders` typo (create_invoice, lifepay_callback) | ✅ убрано вместе с переписыванием этих функций |
| P1: LifePay webhook без проверки подлинности | ✅ заменено на перепроверку через API провайдера (нет задокументированной подписи — не изобретена своя схема) |
| P1: `verify=False` (отключённый TLS) в запросах к LifePay | ✅ убрано (`create_invoice`, `check_lifepay_status`) |
| P1: `DEFAULT_PERMISSION_CLASSES=AllowAny` глобально | ✅ флип на `IsAuthenticated` + точечные `AllowAny` там, где нужно |
| P1: `UploadReceiptPhotoView` — `AllowAny` на весь класс | ✅ `IsAuthenticated` + staff-scoping |
| P1: `AdminOrderSerializer` — обход `update_status` через обычный PATCH | ✅ `read_only_fields` |
| P1: `seo` — полностью открытый CRUD (обнаружено при этой ревизии, не было в исходном аудите) | ✅ `IsAuthenticatedOrReadOnly` |
| P1: `subtotal_api::GetDiscountForUser` — анонимный lookup по телефону | ✅ `IsAuthenticated` (полная IDOR-защита по конкретному номеру — вне скоупа, см. §I) |
| P1: `users/views.py::get_discount_for_user` — то же (найдено в этой ревизии) | ⚠️ теперь требует auth (флип default), но любой авторизованный видит скидку по любому телефону — не сужал специально (см. §I) |

---

## F. Механизм конкурентности

`transaction.atomic()` + `Orders.objects.select_for_update().get(pk=order_id)` в каждом методе `OrderStateService`:

1. Блокирующий SELECT берёт row-lock — конкурирующий вызов **ждёт**, а не читает устаревшую строку.
2. Состояние проверяется **после** получения лока (`order.status_orders`/`payment_status`), не до входа в транзакцию.
3. `version` инкрементируется только при реальном изменении полей (не на no-op повторных вызовах, не на presentation-полях).
4. Вложенные вызовы (`evaluate_payment_deadline` → `cancel`/`payment_succeeded`) используют Django savepoints (nested `atomic()`) — тот же connection, повторный lock на ту же строку в той же транзакции безопасен (не self-deadlock).
5. `transaction.on_commit()` — структурированный лог и (в `signals.py`) диспетч Celery-тасков откладываются до реального коммита, чтобы откат транзакции не оставил "повисший" таск на несуществующее изменение.

Это не оптимистическая блокировка через `version` (хотя поле есть и накапливает историю изменений для аудита/будущего ETag) — реальная защита от гонок — пессимистическая, через `select_for_update()`.

Тесты `OrderConcurrencyTests` (2 потока, `TransactionTestCase`, `threading.Barrier`) — см. §G.

---

## G. Тесты

Файл: `orders/tests.py`. Покрывает все запрошенные категории:

- **State machine**: разрешённые переходы + 4 явно запрещённых (`Completed→Waiting`, `Canceled→In Progress`, `Completed→Canceled`, `In Progress→New`), идемпотентность `accept`/`cancel`, `version` не растёт на no-op.
- **Payment deadline/grace**: 9 граничных сценариев (a–i) с точными секундными смещениями — never-started/90s, PENDING-at-90s, PAID-exactly-at-90s, PENDING-at-120s→cancel, PAID-exactly-at-120s, late-payment-after-cancel→reconciliation-not-resurrect, PAID-beats-late-autocancel, payment_started-rejected-after-deadline.
- **Идемпотентность webhook**: повторная доставка одного `event_key` не меняет состояние дважды.
- **Конкурентность**: `TransactionTestCase` + реальные потоки — `payment_succeeded` vs `system cancel` (PAID не должен быть отменён), двойной `accept()` даёт ровно один `version++`.
- **Авторизация**: чужой заказ нельзя отменить (403), анонимный запрос — 401/403, staff другой кофейни — не проходит `is_staff_for_order`, `/api/staff/` отклоняет не-staff, `admin_override` требует `reason`.
- **Платёжная безопасность**: `PaymentChangeStatus` — 404 (endpoint удалён), forged webhook-статус в теле игнорируется в пользу перепроверенного через API, чужой заказ через `check_lifepay_status` — 404, `StaffOrderUpdateSerializer` не содержит status-полей.

### ⚠️ Тесты НЕ были запущены

В этой сессии не было доступного окружения для реального запуска:

- Облачная песочница: `pip install django==4.2.6 ...` → `403 Forbidden` от PyPI (сеть заблокирована для этого аккаунта/сессии).
- Ваш Mac: тот же результат через `pip install --user` (проверено явно в этой сессии) — прокси возвращает `403 Forbidden`; `docker`/`docker-compose` не найдены в PATH; `venv/` в репозитории — посторонний/битый (нет Django).

Файл проверен: `python3 -m py_compile` на всех изменённых `.py` — синтаксически корректны. Логика тестов вычитана вручную построчно против реализации `OrderStateService`, но **не исполнялась**.

**Команды для запуска у вас** (через ваш реальный docker-compose):

```bash
cd /Users/egor/Projects/bali/Island-Bali
docker compose run --rm web python manage.py makemigrations --check --dry-run   # ожидается: no changes (миграция уже написана вручную)
docker compose run --rm web python manage.py migrate
docker compose run --rm web python manage.py test orders -v 2
docker compose run --rm web python manage.py test   # весь существующий набор — обязательно, чтобы поймать регрессии/unrelated failures
```

Если что-то из `orders/tests.py` упадёт — это, скорее всего, несовпадение с реальной схемой БД (например, точные default'ы/related_name где-то отличаются от того, что я видел при чтении файлов) или отличие версии тестовой БД (Postgres locking semantics для `select_for_update()` в конкурентных тестах требуют реального Postgres, не SQLite — уточните `DATABASES` в тестовом `settings`, если используется SQLite fallback).

---

## H. Миграции

`orders/migrations/0004_order_state_machine_m1.py`, зависит от `orders.0003_initial` — единственная существующая head-миграция приложения `orders` на момент написания.

**Операции**: `AddField` (`version`, `payment_deadline_at`, `payment_started_at`, `provider_paid_at` — все nullable/с default, backward-compatible), `CreateModel` (`PaymentWebhookEvent`, `PaymentReconciliation` — новые таблицы).

**Не destructive**: ни одна колонка не удаляется и не переименовывается, backfill не требуется (все новые поля — `null=True`/`default=0`). Безопасна для применения на непустой БД без downtime.

**Не проверено `makemigrations --check`** (Django недоступен, см. §G) — есть небольшой риск, что при реальном запуске Django обнаружит расхождение и предложит доп. auto-migration (например, если я упустил какой-то `Meta`-нюанс). Команда для проверки — в §G.

---

## I. Оставшиеся риски / не в скоупе

1. **Тесты и миграция не исполнялись** (см. §G, §H) — главный открытый риск, из-за которого не могу дать "READY" без вашего подтверждения.
2. `CheckoutView`/`CheckoutSerializer` (`checkout/`) — обнаружен предсуществующий баг (`send_orders_for_confirmation_to_barista()` вызывается без обязательных `staff`/`time_is_finish`) — endpoint не используется мобильным приложением, не чинил (не входит в скоуп, избежал unrelated redesign).
3. `SBPPaymentCreateView`/`pay_order`/`PaymentView` — не используются мобильным, реальной интеграции с провайдером СБП в проекте никогда не было; я не стал её изобретать, только закрыл IDOR и убрал крэш.
4. `RussianStandardPaymentView`/`AlphaBank*`/`Tinkoff*`/`RSB*` (acquiring) — IDOR по `coffee_shop_id` остаётся (любой авторизованный может дёрнуть банковские креды любой кофейни), но провайдеры не используются мобильным приложением и не были явно названы в ТЗ — только закрыты флипом `AllowAny→IsAuthenticated`.
5. `quickresto/views.py` (CRM-интеграция, персональные данные клиентов) — были полностью `AllowAny` по умолчанию (без явного объявления), теперь `IsAuthenticated` благодаря флипу; staff/admin-scoping не добавлял — не назывался в исходном аудите, требует отдельного прохода.
6. `subtotal_api::GetDiscountForUser` и `users/views.py::get_discount_for_user` — анонимный доступ закрыт (`IsAuthenticated`), но любой авторизованный пользователь всё ещё может запросить скидку по **чужому** номеру телефона — уточните у продукта, предполагался ли это staff-only lookup на кассе, чтобы понять, нужна ли дальнейшая IDOR-защита.
7. LifePay webhook verification — у провайдера нет задокументированной подписи в доступной мне документации/схеме `CoffeeShop` (только `lifepay_api_key`/`lifepay_login`). Реализована перепроверка через собственный status-API провайдера как источник доверия. Если у LifePay всё же есть HMAC-подпись (проверьте их актуальную документацию/личный кабинет) — это было бы надёжнее и дешевле по нагрузке, чем лишний HTTP-запрос на каждый webhook.
8. `music_api` — оставлен как есть (публичный плеер, не относится к заказам/PII, было решение исходного аудита).
9. Смены (`ShiftToggleView`) — IDOR по `user_id` в теле запроса (можно переключить смену другого сотрудника) не закрывался — не относится к state machine заказа, вне главного инварианта ТЗ.

---

## J. Финальный вердикт

**M0/M1 NOT READY**

Причина — не в качестве или полноте реализации (все 5 сценариев "главного acceptance invariant" ниже провably закрыты в коде и покрыты тестами), а в том, что ни миграция, ни тесты не были фактически исполнены в этой сессии — окружение без сети до PyPI и без Docker не позволило это сделать ни в облачной песочнице, ни в вашем локальном шелле. Заявлять "READY" без единого реального прогона было бы нарушением прямого требования ТЗ "не скрывать failing tests" — в данном случае скрывать пришлось бы не сам fail, а факт отсутствия проверки вообще, что хуже.

Пять сценариев acceptance invariant — статус по коду (не по прогону):

1. Late-completing request не откатывает `Completed → Waiting` — `is_order_transition_allowed` не даёт (терминальный статус), тест `test_forbidden_completed_to_waiting`.
2. Поздний webhook не воскрешает `Canceled → In Progress` — `payment_succeeded()` на терминальном заказе не трогает `status_orders`, заводит `PaymentReconciliation`, тест `test_g_late_payment_after_cancel_creates_reconciliation_not_resurrect`.
3. Celery-таймаут не отменяет уже `Paid` заказ — явная проверка `payment_status == Orders.PAID` в начале `cancel()` для `actor_type="system"`, тест `test_system_cancel_never_cancels_paid_order`.
4. Пользователь A не мутирует заказ пользователя B через переданный `order_id` — ownership-проверки в `cancel_orders`/`client_confirmation`/`create_invoice`/`check_lifepay_status`, staff-scoping в `staff/views.py`, тесты `OrderAuthorizationRegressionTests`.
5. Анонимный запрос не достигает `Paid`/`Completed` — `DEFAULT_PERMISSION_CLASSES=IsAuthenticated` + удалённый `PaymentChangeStatus`, тест `test_payment_change_status_endpoint_removed` и `test_anonymous_cannot_cancel_order`.

**Что нужно, чтобы дойти до READY**: прогнать команды из §G у себя (Docker-окружение с реальным Postgres/Redis), поправить то, что не сойдётся с реальной схемой (правки, скорее всего, точечные — либо в тестовых фикстурах, либо в самой миграции), и подтвердить `python manage.py test` зелёным по всему проекту (не только `orders`), чтобы поймать regressions вне state machine.
