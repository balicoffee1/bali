# Технический аудит: статус заказа Happy Island / Island Bali и переход на WebSocket

Дата: 2026-09-01
Область: мобильное приложение (`/Users/egor/Projects/happy_island/happy_island`, Flutter) + backend (`/Users/egor/Projects/bali/Island-Bali`, Django/DRF)

Обозначения путей в этом документе:
- `mobile:<path>` — от `/Users/egor/Projects/happy_island/happy_island/lib/src/`
- `backend:<path>` — от `/Users/egor/Projects/bali/Island-Bali/`

Документ расширен относительно исходного запроса до **13 разделов**: отдельным разделом 3 вынесен полный аудит способов изменения `status_orders`, который в задании был описан как приоритетный ("правильно ли сервер меняет статус" важнее, чем "как клиент об этом узнаёт").

---

## TL;DR

1. Сейчас нет WebSocket вообще. Клиент — customer-приложение — узнаёт о статусе через **HTTP-поллинг раз в 5 секунд** (`mobile:feature/cart/widget/order_notification_scope.dart:81`). Staff-приложение (тот же кодбейз, экран бариста) поллит **раз в 30 секунд четырьмя параллельными запросами** (`mobile:feature/staff/widget/staff_screen.dart:1198`).
2. Push-уведомления (FCM) в проекте есть, но **не участвуют в обновлении статуса**: пуш просто показывает текст, полученный по сети; код, который должен отправлять FCM-токен на сервер, нигде не вызывается (мёртвый код) — см. раздел 3 и П7.
3. На сервере **нет единой state machine заказа**. Обнаружено минимум 12 независимых HTTP-эндпоинтов и 2 фоновых механизма (Celery-задача, Django-сигнал), которые пишут `status_orders`/`payment_status` напрямую, каждый со своими (иногда нулевыми) проверками. Ни разу не используется `select_for_update()` или `transaction.atomic()` — конкурентная запись ничем не защищена.
4. Найдены серьёзные уязвимости уровня P0: публичный (без аутентификации) метод, мгновенно помечающий чужой заказ оплаченным и завершённым (`backend:acquiring/views.py:181-193`); IDOR на два эндпоинта работы с чужими заказами без какой-либо авторизации (`backend:orders/views.py:283-303`); глобальный `DEFAULT_PERMISSION_CLASSES = AllowAny` (`backend:island_bali/settings.py:193-195`), из-за чего любой view без явного `permission_classes` публичен.
5. Поэтому: **до перехода на WebSocket необходимо сначала навести порядок в мутации состояния заказа** (единый `OrderStateService`, транзакции, авторизация). WebSocket, добавленный поверх текущего бэкенда "как есть", будет просто быстрее и надёжнее доставлять клиенту уже испорченные/непредсказуемые данные.
6. Технически проект готов к Channels + Redis (Redis уже в docker-compose, DRF + SimpleJWT, единственный `web`-процесс — сложностей с горизонтальным масштабированием пока нет, но их стоит закладывать).

---

## 1. Текущая архитектура

### 1.1 Мобильная сторона — customer flow

```
main.dart (root)
 └─ MultiRepositoryProvider  (main.dart:126-217)  — Dio + все Repository (singleton на всё приложение)
     └─ MultiBlocProvider     (main.dart:219-296)  — OrderViewBLoC создаётся один раз здесь (main.dart:293-296)
         └─ StaffScope
             └─ MaterialApp.router
                 └─ ShellWidget (core/widget/shell_widget.dart)
                     └─ OrderNotificationScope (shell_widget.dart:68, оборачивает Scaffold с боттом-баром)
                         └─ BlocListener<OrderViewBLoC, OrderViewState>  (order_notification_scope.dart:113)
```

Ключевые классы:

- **`OrderViewBLoC`** (`mobile:feature/cart/bloc/order_view/order_view_bloc.dart`) — единственный bloc, отвечающий за состояние "мои заказы". Единственное событие — `OrderViewEvent.fetch` (`order_view_event.dart`). Обработчик (`order_view_bloc.dart:27-31`) вызывает `CartRepository.viewOrders()` и мапит результат в `MatchingState<List<OrderView>>` (idle/processing/successful/error, `core/util/matching_state.dart`).
- **`CartRepository` / `CartRepositoryImpl`** (`mobile:feature/cart/data/repository/cart_repository.dart`) — Dio-клиент. `viewOrders()` → `GET /api/orders/orders/` (строка 90-94), `cancelOrder()` → `PATCH /api/orders/orders/{id}/cancel/`, `confirmOrder()` → `POST /api/orders/orders/{id}/client_confirmation/`.
- **`OrderView`** (`mobile:feature/cart/model/order_view.dart`) — модель заказа на клиенте, включает как доменные поля (`statusOrders`, `paymentStatus`, `updatedTime`, `clientConfirmed`), так и UI-флаги, которые физически хранятся в БД заказа на сервере: `isThankYouDialogOpen`, `isOrderCancelled`, `isTimeChangedDialog` (см. п. 3, это осознанная, но архитектурно спорная модель — сервер хранит состояние диалогов клиента).
- **`OrderStatus`** enum (`mobile:core/model/order_status.dart`) — 5 значений: `newStatus/waiting/inProgress/completed/canceled`. `orderStatusFromString` (строки 44-64) на любой нераспознанной строке **по умолчанию возвращает `canceled`** (строка 62) — опасный fallback: если сервер когда-нибудь добавит новый статус или отдаст опечатку, клиент интерпретирует активный заказ как отменённый.
- **`OrderNotificationScope`** (`mobile:feature/cart/widget/order_notification_scope.dart`) — точка входа из задания. `StatefulWidget` с `RouteAware, WidgetsBindingObserver`:
  - `initState()` (69-90): если `isAuth`, сразу дёргает `fetch`, затем **`Timer.periodic(Duration(seconds: 5), ...)`** (строка 81) — на каждый тик снова `fetch`.
  - `didChangeAppLifecycleState` (188-190): на `resumed` — `_onResumeCheck()` (196) — ещё один внеплановый `fetch` + если заказ ждёт оплаты, редирект в корзину и опрос LifePay (`_checkLifePayStatus`, строка 204).
  - `_orderViewBLoCListener` (127-179) — читает **последний** заказ пользователя (`state.data!.last`, строка 130) и на основе комбинации `statusOrders`/`paymentStatus`/`updatedTime`/`clientConfirmed`/UI-флагов решает, какой из 4 модальных диалогов показать (или не показывать: используется `_isDialogOpen`-гейт, строка 250 в `_openDialog`).
  - `dispose()` (98-106) — корректно отменяет таймер и снимает observer. Течи здесь нет.
  - Отдельный ad-hoc поллинг оплаты: `_checkLifePayStatus` (204-230) дергает `SBPRepository.getPaymentStatus` — не по таймеру, а по требованию (при открытии диалога ожидания и при `resume`).

- Виджет **не создаёт** HTTP-клиент и не парсит транспорт сам — вся сетевая логика инкапсулирована в `CartRepository`/`SBPRepository`, это плюс текущей архитектуры. Но виджет **напрямую содержит бизнес-логику статусов** (все `if (orderStatus.isX && paymentStatus.isY)` в `_orderViewBLoCListener`) — это то, что при переходе на WebSocket нужно вынести.

### 1.2 Мобильная сторона — staff (бариста) flow

Тот же Flutter-проект содержит экран персонала: `mobile:feature/staff/widget/staff_screen.dart`. Отдельный набор блоков — `OrderBloc` (`feature/staff/bloc/order/order_bloc.dart`) и три инстанса `OrderByStatusBloc` (`feature/staff/bloc/order_by_status/order_by_status_bloc.dart`) для колонок Waiting / In Progress / Completed. `_StaffScreenState.initState()` (`staff_screen.dart:1142`) создаёт эти блоки вручную (не через `BlocProvider`) и запускает **`Timer.periodic(Duration(seconds: 30), ...)`** (`staff_screen.dart:1198`), который на каждый тик шлёт **4 отдельных HTTP-запроса**: `LoadedOrder` + 3× `OrderByStatusLoadEvent`. Репозиторий — `mobile:feature/staff/data/repository/order_repository.dart` (`GET /api/staff/orders/`, `POST /api/staff/orders_by_status/`) и `mobile:feature/staff/data/repository/staff_repository.dart` (`acceptOrder`→`POST /api/staff/`, `completeOrder`→`POST /api/staff/complete_order/`, `cancelOrder`→`DELETE /api/staff/`, `updateOrder`→`PATCH /api/staff/`).

Это фактически **второй, полностью независимый механизм доставки статуса**, который тоже нужно перевести на WebSocket, если цель — устранить поллинг в принципе; в задании фокус был на customer-flow, но staff-flow генерирует основную часть нагрузки поллинга (4 запроса / 30 сек на каждого открытого бариста-экрана).

### 1.3 Push-уведомления (FCM)

- `mobile:main.dart` инициализирует Firebase и `FirebaseMessaging` напрямую в `main()` (строки 66-104): запрашивает разрешения, получает токен в локальную переменную, вешает `onMessage`/`onMessageOpenedApp` листенеры, которые **только делают `debugPrint`** — никак не обновляют `OrderViewBLoC` и не парсят `message.data`.
- Есть отдельный класс `NotificationRepositoryImpl` (`mobile:feature/notification/data/notification_repository.dart`) с методами `init()`, `setDio()`, `sendFcmTokenToServer()` (→ `POST /api/fcm-token`). Он зарегистрирован в DI (`main.dart:127-129`), но:
  - `init()` закомментирован в `main.dart:107-108`;
  - `setDio()` нигде не вызывается (проверено грепом по всему `lib/`);
  - соответственно `sendFcmTokenToServer()` **никогда не выполняется** ни при старте, ни при обновлении токена.
  - Единственное реальное использование класса — `staff_screen.dart:1148/1157-1165` вызывает `showNotification()` (чисто локальный баннер) как напоминалку "прими заказ" каждые 30 сек, если есть неподтверждённый новый заказ.
- Итог: серверный push (`backend:notifications/main.py`, см. 3.4) почти наверняка никогда не долетает до реальных пользователей, т.к. `user.has_device()` не станет `True` без токена на сервере. Пуши сейчас — это фактически мёртвый канал, не источник истины и даже не рабочий "будильник" для polling.

### 1.4 Backend — стек

- Django 4.2.6 + DRF 3.14, аутентификация — `rest_framework_simplejwt` (`backend:island_bali/settings.py:190-192`), WSGI (`gunicorn island_bali.wsgi:application`, `backend:docker-compose.yaml`), без флага `-w` → 1 sync-воркер.
- Celery 5.3.6 + django-celery-beat, брокер — Redis (сервис `redis` в `docker-compose.yaml`, порт наружу `6380:6379`). Два отдельных контейнера: `celery` (worker) и `celery-beat` (планировщик).
- **`channels`/`daphne`/`uvicorn`/`websockets` в `requirements.txt` нет.** ASGI-приложение (`island_bali/asgi.py`) есть, но это стандартный, ничем не расширенный файл `django-admin startproject`, реального ASGI-стека (Channels) в проекте нет — WebSocket поддержки на сервере сейчас нет вообще.
- `nginx/default.conf` проксирует `^/(api|admin|swagger|redoc)/` на `web:8000`, всё остальное отдаёт статику admin-панели. Правила для `/ws/` нет.
- Приложения, относящиеся к заказу: `orders`, `staff`, `acquiring` (эквайринг/LifePay/SBP), `admin_api` (React admin-панель), `notifications` (FCM через `fcm-django`/`firebase-admin`), `cart`.

---

## 2. Текущий жизненный цикл заказа (как задумано)

```
Клиент собирает корзину (cart app)
        ↓
POST /api/orders/orders/  →  OrderViewSet.perform_create (orders/views.py)
        статус по умолчанию = "New" (orders/models.py: default=NEW)
        ↓
Django-сигнал schedule_order_timeout (orders/signals.py) ставит
Celery-задачу cancel_unpaid_order_task с задержкой 90 сек
        ↓
Бариста жмёт "Принять" в staff-приложении
POST /api/staff/  →  PendingOrdersAcceptView.post → update_order_status()
        статус = "Waiting", payment_status = "Pending"  (safety-проверок нет)
        ↓
Клиент оплачивает (LifePay/SBP) — статус меняет ОДИН из ~5 разных
        обработчиков платежа (см. раздел 3) → "In Progress" + payment "Paid"
        ↓
Бариста жмёт "Готово"
POST /api/staff/complete_order/ → change_order_status_to_completed()
        проверяет, что текущий статус == "In Progress", иначе 400
        статус = "Completed"
        ↓
Клиент открывает "Спасибо за заказ" → оценивает заказ (review)
```

Если оплата не проходит за 90 секунд — `cancel_unpaid_order_task` переводит заказ в `Canceled`. Отмена также возможна вручную (клиентом, бариста, админом) на нескольких независимых путях — см. раздел 3.

**Важный практический разрыв, найденный в ходе аудита:** ни в одном коде, доступном из mobile-приложения (customer или staff), нет перехода в `"In Progress"`, КРОМЕ как через оплату (LifePay/SBP callback или ручной опрос). Единственная не-платёжная точка, которая явно умеет ставить `"In Progress"` — это админ-панель (`AdminOrdersViewSet.update_status`, `backend:admin_api/views.py:359`). Это означает, что реальный жизненный цикл — не "бариста ведёт заказ по стадиям", а "оплата — единственный переключатель между Waiting и In Progress"; поле `"In Progress"` фактически = "оплачено и готовится", а не отдельная стадия, управляемая персоналом.

---

## 3. Аудит изменения состояния заказа (`Order state mutation`)

Раздел отвечает на прямой вопрос: **правильно ли сервер вообще меняет `order.status`, независимо от способа доставки этого изменения клиенту.**

### 3.1 Таблица всех найденных точек входа

| # | Метод / endpoint | Файл:строка | Текущий статус (проверяется?) | Куда переводит | Авторизация | Блокировка/атомарность | Публикация события |
|---|---|---|---|---|---|---|---|
| 1 | `POST /api/orders/orders/` (создание) | `orders/views.py` (`OrderViewSet.perform_create`) | — (create) | `New` (default модели) | `IsAuthenticated`, cart = `request.user` | нет | нет |
| 2 | `PATCH /orders/{id}/confirm/` | `orders/views.py:139` (`confirm_orders`) | **не проверяется** | `Completed` (через `Orders.confirm_order`, `models.py:118`) | только `IsAuthenticated`; `Orders.objects.get(pk=pk)` **не отфильтрован по пользователю** — IDOR | нет | нет |
| 3 | `PATCH /orders/{id}/cancel/` | `orders/views.py:146` (`cancel_orders`) | **не проверяется** | `Canceled` (`models.py:126`) | `IsAuthenticated`, unscoped `Orders.objects.get(pk=pk)` — IDOR | нет | нет |
| 4 | `PATCH /orders/{id}/complete/` | `orders/views.py:164` (`complete_order` action) | не проверяется | `Completed` — **баг**: модельный `complete_order(self, reason)` требует аргумент, а вызывается без него (`models.py:133` vs `views.py:166`) → `TypeError`/500 | scoped через `self.get_object()` (фильтр `user=request.user`) — то есть по факту доступен только владельцу заказа, не персоналу | нет | нет |
| 5 | `POST /orders/{id}/pay/` | `orders/views.py:171` (`pay_order`) | нет | `payment_status = Paid` (`PaymentMethod.process()` в `models.py:150-159` **всегда** возвращает `"success"`) | scoped к владельцу — не IDOR, но клиент **сам** переводит себя в "оплачено" без реальной оплаты | нет | нет |
| 6 | `POST /orders/{id}/client_confirmation/` | `orders/views.py:181` | статус не трогает, только `client_confirmed=True` | — | корректно: `order.user != request.user` → 403 | нет | нет |
| 7 | `PATCH /orders/{id}/staff-update/` | `orders/views.py:192` (`staff_update`) | нет | любое поле, включая `status_orders` (`StaffOrderUpdateSerializer` — `exclude=['user','created_at','cart']`, т.е. `status_orders` **разрешён**) | scoped через `self.get_object()` (владелец!) — для реального персонала endpoint фактически недоступен (сотрудник ≠ `order.user`), но при совпадении аккаунтов — полный контроль над заказом | нет | нет |
| 8 | `PATCH /orders/{id}/status/` | `orders/views.py` (`OrderStatusUpdateView`), `OrderStatusUpdateSerializer` (`serializers.py`) | нет | **любое** значение `status_orders`, принятое напрямую от клиента, без бизнес-валидации | scoped к `user=request.user` — сам клиент может поставить себе любой статус | нет | нет |
| 9 | `PATCH /orders/update-thank-you-dialog/{id}/` | `orders/views.py:283` (`UpdateThankYouDialogView`) | нет | `isThankYouDialogOpen` | **нет `permission_classes`** → глобальный `DEFAULT_PERMISSION_CLASSES=AllowAny` (`settings.py:193-195`) — эндпоинт публичный; `get_object_or_404(Orders, id=order_id)` (строка 286) без фильтра по пользователю — IDOR без авторизации вообще | нет | нет |
| 10 | `PATCH /orders/update-order-cancelled/{id}/` | `orders/views.py:295` (`UpdateOrderCancelledView`) | нет | `isOrderCancelled` | то же — публично, IDOR (строка 298) | нет | нет |
| 11 | `POST /api/staff/` (accept) | `staff/views.py` → `update_order_status` (`staff/utils.py:48`), fetch — `get_order_if_new` (`utils.py:37`, **не проверяет "новизну" несмотря на название**) | **не проверяется вообще** | безусловно `Waiting` + `payment=Pending` | `IsAuthenticated` (без роли "staff") | нет | push |
| 12 | `PATCH /api/staff/` (update) | `staff/views.py` → `PatchOrderSerializer.update_order` | статус не трогает (время/комментарии/UI-флаги) | — | `IsAuthenticated` | нет | push |
| 13 | `DELETE /api/staff/` (cancel) | `staff/views.py` → `cancel_order_with_comment` (`staff/utils.py:77`) | **не проверяется** | безусловно `Canceled`, из любого текущего статуса, включая `Completed` | `IsAuthenticated` | нет | push |
| 14 | `POST /api/staff/complete_order/` | `staff/views.py` → `change_order_status_to_completed` (`staff/utils.py:94`) | проверяет `== "In Progress"` (`utils.py:105`) — единственная реальная проверка среди staff-методов | `Completed` | `IsAuthenticated` | нет (check-then-save без блокировки) | push |
| 15 | `POST create-invoice/` | `acquiring/views.py` (`create_invoice`) | нет | пишет `order.status = 'pending'` — **несуществующее поле модели** (правильное имя `status_orders`), т.е. по факту **no-op** | `@api_view` без явного `permission_classes` → `AllowAny` по умолчанию | нет | нет |
| 16 | `POST /api/lifepay/callback/` | `acquiring/views.py:260` (`lifepay_callback`) | нет | `status==10` → `Paid`+`In Progress`; `status in [20,30]`/`15` → пишет `order.status = ...` (несуществующее поле — **no-op**, реальная отмена/пендинг не срабатывает) | `@csrf_exempt @permission_classes([AllowAny])` — ожидаемо для вебхука, но **нет проверки подписи/секрета от LifePay** | нет | нет |
| 17 | `POST` (class) | `acquiring/views.py:309` (`LifePayCallbackView`) | нет | дублирует №16 в виде класса, `status==10` → `Paid`+`In Progress` | `permission_classes = [AllowAny]` (строка 315), без проверки подписи | нет | нет |
| 18 | `POST` | `acquiring/views.py:335` (`PaymentChangeStatus`) | нет | по одному `order_id` из тела запроса **безусловно** ставит `Paid`+`In Progress` | `permission_classes = [AllowAny]` (строка 343), **никакой** привязки к реальному инвойсу/провайдеру | нет | нет |
| 19 | `GET /api/payment/lifepay/status/{id}/` | `acquiring/views.py:360` (`check_lifepay_status`) | нет | по факту опроса LifePay: `Paid`+`In Progress` / `Canceled`+`Failed` / `Pending` | `IsAuthenticated`, scoped `user=request.user` — единственный платёжный путь без IDOR | нет | нет (но вызывается мобильным клиентом как обычный **GET**, при этом имеет side-effect записи в БД) |
| 20 | `POST` (создание SBP-инвойса) | `acquiring/views.py:181` (`SBPPaymentCreateView`) | нет | **немедленно** `status_orders=Completed`, `payment_status=Paid` — при простом создании счёта, до какого-либо подтверждения оплаты | **нет `permission_classes`** → `AllowAny` по умолчанию | нет | нет |
| 21 | `PATCH /admin/orders/{id}/update_status/` | `admin_api/views.py:359` (`AdminOrdersViewSet.update_status`) | проверяет только, что значение — валидный enum (строки 367-369), не проверяет допустимость перехода из текущего статуса | любое допустимое значение enum; для `Canceled` требует `cancellation_reason` | `IsAdminOrReadOnly`, есть `log_admin_activity` (аудит) | нет | push |
| 22 | Celery-задача `cancel_unpaid_order_task` | `orders/tasks.py` | `payment_status != Paid and status not in [Completed, Canceled]` — есть проверка, но без блокировки | `Canceled` | системный (не HTTP) | нет (read-then-write без `select_for_update`) | нет |
| 23 | Django-сигнал `set_waiting_status_for_testing_order` | `orders/signals.py` | `is_testing == True` | форсирует `Waiting`+`payment=Waiting` **на каждый `save()`** тестового заказа | системный | нет | нет |

### 3.2 Ключевой вывод

**Единой state machine нет.** 23 независимых места пишут `status_orders`/`payment_status`, из них:
- ни одно **не использует** `select_for_update()` или `transaction.atomic()`;
- только 2 из ~16 HTTP-точек (`change_order_status_to_completed`, частично `AdminOrdersViewSet.update_status`) хоть как-то проверяют текущий статус перед записью;
- ни одна не проверяет "разрешён ли переход X→Y" по общей матрице — каждая точка кодирует правило (если вообще кодирует) самостоятельно;
- как минимум 3 точки (`SBPPaymentCreateView`, `PaymentChangeStatus`, `lifepay_callback`/`LifePayCallbackView`) позволяют **посторонним/неаутентифицированным** запросом перевести чужой заказ в "оплачен" без реальной оплаты.

### 3.3 Разбор конкурентных сценариев из задания

1. **Клиент отменяет заказ одновременно с подтверждением оператором.** Возможно и не защищено: `cancel_orders` (клиент, но фактически вызывается кем угодно из-за IDOR) и `PendingOrdersAcceptView.post` (бариста) оба делают `Orders.objects.get(...)` → мутация полей в памяти → `save()`. Django `save()` на `CharField` — это безусловный `UPDATE ... SET status_orders=X WHERE id=Y` (без `WHERE status_orders=<ожидаемое>`) — **классический lost update**: чей `save()` выполнится последним, тот и победит, независимо от бизнес-смысла.
2. **READY одновременно с CANCELLED.** Тот же механизм: `change_order_status_to_completed` читает статус, потом (после сетевой паузы) пишет `Completed`; если между чтением и записью другой запрос поставил `Canceled`, `change_order_status_to_completed` всё равно перезапишет его на `Completed`, потому что проверка (`utils.py:105`) выполняется **до** записи, а не атомарно с ней.
3. **Два сотрудника меняют один заказ.** Ничем не отличается от (1)-(2) — ни один путь не блокирует строку.
4. **Повторный HTTP-запрос после таймаута** (клиент ретраит "Принять оплату"/"Готово"): ни один из write-эндпоинтов не идемпотентен и не хранит `request_id`/`idempotency_key` — повторный запрос просто повторно выполнит ту же безусловную запись (для `Completed` это не опасно, т.к. переход конечный, но повторный push будет отправлен снова).
5. **Worker повторно обрабатывает задачу.** `cancel_unpaid_order_task` не имеет Celery `acks_late`/уникальности — если брокер редоставит задачу (что Celery делает при падении воркера), задача просто перепроверит условие и, если заказ всё ещё "не оплачен", отменит его повторно — не критично само по себе, но при этом всё ещё без `select_for_update`, поэтому уязвимо к гонке с одновременной оплатой ровно в 90-ю секунду.
6. **Webhook приходит несколько раз** (LifePay это делает — таков смысл вебхука с ретраями на стороне провайдера). `lifepay_callback`/`LifePayCallbackView` не хранят "этот `transaction_number` уже обработан" — при повторной доставке они просто ещё раз запишут `Paid`+`In Progress` (безопасно для конечного состояния), НО так же повторно ничего не сделают для `status in [20,30]` из-за бага с несуществующим полем `order.status` (см. таблицу №16-17) — то есть отказ платежа тихо теряется при каждой доставке.
7. **Старый запрос завершается позже нового.** Явно возможно между `check_lifepay_status` (клиентский поллинг) и настоящим webhook — оба пишут в одну и ту же строку без версии/условия, побеждает тот, кто физически ответит последним.
8. **Два backend-инстанса одновременно меняют заказ.** Сейчас деплой — один `web`-контейнер (см. `docker-compose.yaml`, без `-w` у gunicorn, без `replicas`), поэтому проблема пока не проявляется физически, но код к этому не готов: при масштабировании (что обычно и происходит вместе с добавлением realtime-фич) первая же конкурентная запись обнажит все race conditions из пп. 1-7 на нескольких процессах одновременно.

### 3.4 Восстановленная (де-факто) state machine

```
                    ┌────────── PaymentChangeStatus/SBPPaymentCreateView (баг, обходит всё) ─────────┐
                    │                                                                                  ▼
   New ──accept(staff, безусловно)──► Waiting ──payment ok (webhook/poll)──► In Progress ──complete(staff, guarded)──► Completed
    │                    │                          │                             │                        ▲
    │                    │                          │                             │                        │
    └────────────────────┴──────────────────────────┴─────────────────────────────┴── cancel (staff/admin/customer-IDOR/auto-90s, всегда безусловно) ──► Canceled
```

Все стрелки "cancel" не проверяют исходное состояние (можно отменить уже `Completed`), стрелка "accept" не проверяет исходное состояние (можно вернуть `Completed`/`Canceled` обратно в `Waiting`), а `client_confirmation`/`staff-update`/`status/`-эндпоинты потенциально позволяют клиенту вставить произвольный переход в обход всей схемы.

### 3.5 Целевая канонiческая state machine (предложение)

```
NEW ──► WAITING ──► IN_PROGRESS ──► COMPLETED
  │         │             │
  └─────────┴─────────────┴──────► CANCELED   (терминальное состояние, только из NEW/WAITING/IN_PROGRESS)
```

Правила:
- `COMPLETED` и `CANCELED` — терминальные, из них переходов нет ни при каких обстоятельствах (кроме ручной admin-коррекции, которая должна логироваться отдельно и не переиспользовать обычный API).
- Каждый переход валиден только из явно перечисленного набора исходных статусов (таблица "текущий → допустимые следующие"), а не "любой → любой, если значение валидно как enum" (текущее поведение `OrderStatusUpdateSerializer`, `AdminOrdersViewSet.update_status`).
- Единственное место, которое умеет менять `status_orders`, — доменный сервис (`OrderStateService`, см. раздел 5), который выполняет переход **атомарно и условно** (`UPDATE orders SET status=%s, version=version+1 WHERE id=%s AND status=%s`, либо `select_for_update()` внутри `transaction.atomic()`), и **только после успешного перехода** публикует событие. Все 23 найденные точки входа должны быть переписаны на вызов этого сервиса вместо прямого присваивания полей модели.

### 3.6 `Order state mutation` vs `Order state notification`

Явно разделяем ответственность:

- **Mutation (кто имеет право менять статус и как)** — исключительно backend-сервис уровня домена, с транзакцией и проверкой допустимого перехода. WebSocket к этому не имеет отношения.
- **Notification (кто и как узнаёт об уже свершившемся, зафиксированном изменении)** — WebSocket/push/поллинг. Их задача — донести уже принятое и закоммиченное решение, а не принимать его. Ниже (разделы 5-9) речь идёт только об этой части, при условии, что раздел 3 будет закрыт отдельно (см. раздел 11, где это выделено в M0).

---

## 4. Проблемы (Problems)

Далее — отдельные находки с severity. P0 — критично (безопасность/потеря денег/данных), P1 — серьёзный баг архитектуры/надёжности, P2 — заметная проблема качества, P3 — незначительно/косметика.

### P0

1. **Публичный "бесплатный" complete+pay заказа.** `backend:acquiring/views.py:181-193` (`SBPPaymentCreateView.post`). Нет `permission_classes` → действует глобальный `AllowAny` (`backend:island_bali/settings.py:193-195`). Сценарий: любой (даже неаутентифицированный) запрос `POST` на этот endpoint с любым `order_id` мгновенно ставит `status_orders=Completed`, `payment_status=Paid`, без проверки факта оплаты. Последствие: прямая потеря денег/товара.
2. **Публичные payment-webhook'и без проверки подписи и без привязки к аутентичному провайдеру.** `backend:acquiring/views.py:335-357` (`PaymentChangeStatus`) — принимает голый `order_id` и безусловно помечает оплаченным; `backend:acquiring/views.py:260-291` и `:309-333` (`lifepay_callback`, `LifePayCallbackView`) — `AllowAny`, нет HMAC/подписи от LifePay, есть привязка к `transaction_number`, но её может знать кто угодно, кто перехватил один legit callback. Последствие: подделка оплаты.
3. **IDOR без аутентификации на изменение состояния диалогов заказа.** `backend:orders/views.py:283-303` (`UpdateThankYouDialogView`, `UpdateOrderCancelledView`) — нет `permission_classes`, `get_object_or_404(Orders, id=order_id)` без фильтра по владельцу. Любой может пометить чужой заказ "отменённым" на уровне UI-флага или сбить `isThankYouDialogOpen` любого заказа.
4. **IDOR на подтверждение/отмену заказа персоналом.** `backend:orders/views.py:139-152` (`confirm_orders`, `cancel_orders`) — `Orders.objects.get(pk=pk)` без фильтра, доступно любому `IsAuthenticated`-пользователю (не только персоналу) — можно подтвердить (→ `Completed`!) или отменить чужой заказ.
5. **Клиент может выставить себе любой статус напрямую.** `backend:orders/views.py` (`OrderStatusUpdateView`) + `OrderStatusUpdateSerializer` (`serializers.py`, `fields=['status_orders']`) — нет проверки допустимости перехода, только владение заказом. Пользователь может сам "завершить" свой заказ без похода на кассу.
6. **Глобальный `DEFAULT_PERMISSION_CLASSES = AllowAny`.** `backend:island_bali/settings.py:193-195`. Системная проблема: любой новый/старый view без явного `permission_classes` по умолчанию публичен. Это ровно то, что привело к находкам 1 и 3. Необходимо сменить дефолт на `IsAuthenticated` и точечно разрешать `AllowAny` только там, где это осознанно нужно (реальные webhook'и — но и там нужна подпись).
7. **Отсутствие блокировок/атомарности при любой мутации статуса.** Ни одного `select_for_update()`/`transaction.atomic()` во всём backend (грепом по всему проекту). Race conditions из раздела 3.3 (пп. 1-8) актуальны уже сейчас, при единственном backend-процессе — просто из-за параллельных HTTP-запросов и Celery-задачи.

### P1

8. **Нет единой state machine — 23 независимых мутатора статуса** (полный список — раздел 3.1). Разные правила, разные проверки (или их отсутствие), разные наборы "разрешённых" переходов в разных модулях (`orders`, `staff`, `acquiring`, `admin_api`). Любая будущая доработка рискует продублировать ещё одно правило вместо переиспользования существующего.
9. **Runtime-баг: `PATCH /orders/{id}/complete/` всегда падает.** `backend:orders/models.py:133` — `complete_order(self, reason)` требует позиционный аргумент; `backend:orders/views.py:166` — вызывается как `order.complete_order()` без аргументов → `TypeError` на каждый вызов.
10. **`accept` в staff-приложении не проверяет исходный статус и может откатить заказ назад по жизненному циклу.** `backend:staff/utils.py:37-54` (`get_order_if_new` не проверяет "новизну" несмотря на комментарий; `update_order_status` безусловно ставит `Waiting`). Бариста может случайно (двойной тап, гонка с автоотменой) вернуть уже `Completed`/`Canceled` заказ в `Waiting`.
11. **`cancel` (staff) не проверяет исходный статус.** `backend:staff/utils.py:77-82` — можно отменить уже `Completed` заказ.
12. **Тихая потеря отказа оплаты.** `backend:acquiring/views.py:250,283,285` — код пишет `order.status = 'pending'/'cancelled'` — поля `status` у модели `Orders` не существует (есть только `status_orders`), Django молча создаёт "фантомный" атрибут экземпляра и не сохраняет его. В результате реальный отказ/просрочка платежа (`status in [20,30]` от LifePay) **не отменяет** заказ на сервере — заказ повисает в `Waiting`, пока его не снимет 90-секундная Celery-задача (если она ещё не сработала) или persist остаётся неверным неограниченно долго, если платёж пришёл позже 90 секунд.
13. **`bloc_concurrency.concurrent()` без гарантии порядка ответов.** `mobile:feature/cart/bloc/order_view/order_view_bloc.dart:30` и аналогично `mobile:feature/staff/bloc/order/order_bloc.dart` — при "конкурентном" transformer'е несколько `fetch`-запросов (обычный 5-секундный тик + `onResume` + `onDialogClosed` могут пересечься) выполняются параллельно, и `emit` происходит в порядке завершения сетевого запроса, а не порядка отправки. Более старый (медленный) ответ, завершившийся позже нового, перезапишет свежее состояние устаревшим — classic out-of-order emit.
14. **На сетевой ошибке `data` теряется.** `backend:` н/д — это мобильный код: `mobile:feature/cart/bloc/order_view/order_view_bloc.dart:44` — `emit(OrderViewState.error(message: error.toString()))` не передаёт предыдущий `data`, значит `MatchingState.data` становится `null`. `OrderViewStateX.lastOrder`/`hasData` (`order_view_bloc.dart`, extension) после этого возвращают "нет заказа", хотя последний известный заказ был. `_onResumeCheck` (`order_notification_scope.dart:196-203`) использует `_orderViewBLoC.state.lastOrder` — после одного неудачного тика поллинга (например, кратковременная потеря сети) резюм-логика "клиент ещё не оплатил — редиректнуть в корзину" перестаёт срабатывать до следующего успешного `fetch`.
15. **Утечки Timer/Bloc/StreamSubscription на экране персонала.** `mobile:feature/staff/widget/staff_screen.dart` — `_StaffScreenState` содержит `orderTimer` (`Timer.periodic`, строка 1198), `_acceptanceTimer` (строка 894), три вручную созданных `OrderByStatusBloc` (строки 1154-1193, с `..stream.listen(...)` на первом из них) — метод `dispose()` в файле **отсутствует** (проверено грепом `void dispose` по файлу — 0 совпадений). При уходе с экрана бариста ни таймеры, ни блоки, ни подписка не освобождаются: течёт память, таймеры продолжают дёргать сеть даже после того как `State` уже не в дереве виджетов (что само по себе может кидать `setState() called after dispose()`), 30-секундный опрос продолжает копиться при каждом повторном заходе на экран.
16. **FCM-канал фактически неработоспособен.** `mobile:feature/notification/data/notification_repository.dart` — `sendFcmTokenToServer` (единственное место, отправляющее токен на `/api/fcm-token`) не вызывается нигде в приложении (`init()` закомментирован в `main.dart:107-108`, `setDio()` без вызовов). Backend, скорее всего, никогда не получает реальные токены → `user.has_device()` (используется в `backend:notifications/main.py`) в проде почти всегда `False` → push, отправленные из `staff/views.py`, `admin_api/views.py`, `orders/views.py`, тихо не долетают.
17. **Дублирующиеся, частично противоречащие друг другу create-order и payment-flow пути.** Создание заказа — либо `OrderViewSet.perform_create` (используется мобильным клиентом), либо `CheckoutView`/`CheckoutSerializer.create` (`backend:orders/serializers.py`, вызывает `cart.send_orders_for_confirmation_to_barista`) — два разных пути с разными побочными эффектами (второй сразу переводит в "Pending"). Аналогично оплата дублируется как минимум в 5 разных вьюхах (см. раздел 3.1, №15-20).

### P2

18. **`OrderStatus.orderStatusFromString` по умолчанию мапит неизвестную строку в `canceled`.** `mobile:core/model/order_status.dart:61-62`. Любая опечатка/новый статус на сервере молча превращает активный заказ в "отменён" на клиенте — вводит пользователя в заблуждение.
19. **`PatchOrderSerializer.update_order` пишет `new_comments` в поле `cancellation_reason`, а не в `staff_comments`.** `backend:staff/serializers.py` — похоже на copy-paste баг, комментарий персонала записывается как "причина отмены" даже когда заказ не отменяется.
20. **`AdminOrdersViewSet.update_status` не проверяет допустимость перехода, только что значение — валидный enum.** `backend:admin_api/views.py:359-369`. Лучше остальных (есть аудит-лог, есть обязательность `cancellation_reason`), но всё ещё позволяет, например, `Completed → Waiting`.
21. **UI-флаги диалогов (`isThankYouDialogOpen`, `isOrderCancelled`, `isTimeChangedDialog`) хранятся как поля доменной модели `Orders` на сервере** (`backend:orders/models.py`, camelCase-поля посреди snake_case модели). Это смешение UI-состояния мобильного клиента и бизнес-модели заказа — усложняет и мутацию (лишние поля, которые могут менять посторонние вьюхи), и будущую событийную модель (непонятно, является ли изменение такого флага "событием заказа" для WebSocket).
22. **Поллинг создаёт постоянную сетевую нагрузку independent от активности.** Пока `isAuth == true` и `OrderNotificationScope` смонтирован, `GET /api/orders/orders/` летит каждые 5 секунд **даже если у пользователя нет активных заказов** (`state.data!.isEmpty` — обрабатывается уже после ответа, а не до запроса). На экране персонала аналогично — 4 запроса/30 сек, включая опрос "Completed"-заказов, которые уже не изменятся.

### P3

23. **`orderStatusToString`/`paymentStatusToString` содержат неконсистентные строки-заглушки** (`mobile:core/model/payment_status.dart` — `paid`/`newS` оба переведены как `'NEW'`) — не влияет на функциональность статуса заказа, но затрудняет отладку по логам.
24. **Множество `print()`/`debugPrint()` вместо структурированного логирования** и в мобильном, и в backend-коде (например `acquiring/views.py` — `print(data)`, `print(result)` с потенциальным попаданием телефона/email клиента в консоль/логи контейнера) — соседствует с вопросом PII в логах (раздел 10).

---

## 5. Целевая архитектура WebSocket

Схема из задания (`Backend transaction → Order event → WebSocket → Mobile client → Repository/state → UI`) в целом подходит проекту, с двумя поправками под то, что реально есть в коде:

1. Перед "Order event" обязательно нужен шаг **"Validate transition + atomic write"** — раздел 3 показал, что без него подключать WebSocket бессмысленно и даже вредно (события будут доставлять быстрее, но не корректнее).
2. У проекта уже два независимых потребителя статуса (customer `OrderNotificationScope`/`OrderViewBLoC` и staff `staff_screen.dart`/`OrderBloc`/`OrderByStatusBloc`) — целевой транспортный слой должен обслуживать оба, а не быть завязан на `order_notification_scope.dart` персонально.

```
HTTP (customer/staff) / Admin / Celery worker / Payment webhook
                              ↓
                     OrderStateService.transition(order_id, event, actor)
                              ↓
                 validate: текущий статус ∈ allowed_from[event]
                              ↓
        transaction.atomic():  select_for_update() → conditional UPDATE
                              ↓
                    COMMIT (только тут заказ реально изменился)
                              ↓
                    on_commit(): публикация OrderStatusChanged
                       ↙                              ↘
      Channels layer (Redis pub/sub)              прочие side-effects
      group "user.{user_id}" (+ "staff.{shop_id}")   (push-уведомление, аудит-лог)
                       ↓
         ASGI WS consumer держит соединение,
         рассылает событие всем подпискам группы
                       ↓
        Mobile: OrderSocketService (см. раздел 7)
                       ↓
        OrderRepository/OrderViewBLoC (тот же bloc, новый event "socketUpdate")
                       ↓
        OrderNotificationScope слушает BlocListener как сейчас — без изменений в способе получения данных
```

### 5.1 Backend

- Framework: поверх существующего DRF/WSGI-стека добавляется **Django Channels** (пакет отсутствует, нужно установить `channels`, `channels-redis`, ASGI-сервер `daphne` или `uvicorn[standard]`). Redis для channel layer уже есть в инфраструктуре (`docker-compose.yaml`, сервис `redis`) — можно переиспользовать тот же инстанс с отдельной DB/namespace, либо поднять второй Redis для изоляции от Celery broker (рекомендуется для прод, чтобы всплеск WS-трафика не влиял на очередь задач).
- WS и HTTP API продолжают жить в одном Django-проекте, но HTTP остаётся на gunicorn/WSGI (как сейчас), а WS-эндпоинт обслуживается отдельным ASGI-процессом (`daphne island_bali.asgi:application`) в отдельном контейнере, за тем же nginx с новым `location /ws/ { proxy_http_version 1.1; proxy_set_header Upgrade ...; proxy_set_header Connection "upgrade"; proxy_pass http://ws:8001; }`. Смешивать WSGI и ASGI в одном процессе не нужно и рискованно при текущем размере проекта.

### 5.2 Mobile

- Новый independent-от-UI сервис `OrderSocketService` (или `OrderRealtimeClient`) — единственный, кто открывает `WebSocketChannel`, разбирает транспортные кадры и решает про reconnect/heartbeat.
- Он публикует уже готовые доменные события (`OrderStatusChanged`) в существующий `OrderViewBLoC` через новое событие (например `OrderViewEvent.applyRealtimeUpdate(OrderView)` или `OrderViewEvent.invalidate()`, вызывающее уже существующий `fetch`) — то есть WebSocket **не подменяет** `OrderViewBLoC`, а становится ещё одним источником, который триггерит тот же путь обновления state, что и сейчас поллинг. `order_notification_scope.dart` не меняется в части `_orderViewBLoCListener` — вся текущая диалоговая логика продолжает работать, т.к. она реагирует на `OrderViewState`, а не на способ его получения.
- `OrderNotificationScope` теряет: `Timer.periodic` (81), прямой `_orderViewBLoC.add(fetch)` по таймеру. Сохраняет: `didChangeAppLifecycleState` (188, но теперь вызывает reconciliation, а не просто fetch), `_orderViewBLoCListener` целиком, `_checkLifePayStatus` (это про оплату, не про статус заказа per se — остаётся отдельным до отдельного review).

### 5.3 Event contract

Без выдумывания новых полей поверх того, что уже отдаёт `OrderSerializers`/`OrderView` (`mobile:feature/cart/model/order_view.dart`, `backend:orders/serializers.py`):

```json
{
  "type": "order.status_changed",
  "order_id": 1234,
  "status_orders": "In Progress",
  "payment_status": "Paid",
  "updated_at": "2026-09-01T10:15:00Z",
  "client_confirmed": false,
  "cancellation_reason": null
}
```

- **Одно событие `order.status_changed`, не набор специализированных `order.cancelled`/`order.completed`.** Обоснование: у модели и так один enum `status_orders` с 5 значениями, клиент (`_orderViewBLoCListener`) уже устроен как единый switch по комбинации `statusOrders`/`paymentStatus`/`updatedTime` — дробление на типы событий заставило бы дублировать эту логику на два места (тип события + поле статуса) без выигрыша. Специализированный тип имеет смысл только для событий, у которых схема payload'а принципиально другая (например `order.receipt_uploaded` с фото) — таких среди статусов заказа нет.
- **`version`/`event_id` в духе примера из задания — не вводим**, т.к. в модели `Orders` нет `version`-поля (см. P0/P1 в разделе 4 — его в принципе нет и для конкурентного контроля тоже нужно). Вместо изобретения нового поля предлагается **добавить его один раз и переиспользовать и для оптимистичной блокировки, и как версию события**: миграция добавляет `Orders.version = IntegerField(default=0)`, `OrderStateService` инкрементирует его при каждом успешном переходе внутри той же атомарной операции (`UPDATE ... SET version = version + 1 WHERE id=%s AND version=%s`). Тогда `version` в WS-событии — это ровно то же число, что и защита от гонок в БД, а не отдельная сущность.
- `updated_at` уже есть (`auto_now=True`) и меняется при любом `save()`, не только смене статуса — для WS-события это ок как "когда событие возникло", но для reconciliation (раздел 8-9) нужнее `version`.
- Для staff-канала имеет смысл более широкий payload (весь `PendingOrdersAcceptSerializer`-набор полей), т.к. staff-экран показывает списки по колонкам, а не один заказ — см. `docs. подписка user vs shop` ниже.

---

## 6. Backend changes

**Существующие файлы для изменения:**
- `backend:orders/views.py` — заменить прямые мутации (`confirm_orders`, `cancel_orders`, `complete_order`, `pay_order`, `staff_update`, `OrderStatusUpdateView`) на вызовы `OrderStateService`; закрыть IDOR (добавить владельца/роль в scope выборки); удалить/защитить дублирующий `OrderStatusUpdateSerializer`.
- `backend:orders/models.py` — `confirm_order`/`cancel_order`/`complete_order`/`process_payment` либо удалить (перенести логику в сервис), либо превратить в тонкие обёртки над сервисом, чтобы не было двух источников бизнес-правил.
- `backend:orders/tasks.py`, `orders/signals.py` — переписать на вызов `OrderStateService.transition(...)` вместо прямого `order.status_orders = ...; order.save()`.
- `backend:staff/utils.py`, `staff/views.py` — та же замена (`update_order_status`, `cancel_order_with_comment`, `change_order_status_to_completed`).
- `backend:acquiring/views.py` — все 5 путей оплаты (создание инвойса, 2 варианта callback, `PaymentChangeStatus`, `check_lifepay_status`) свести к одному месту с проверкой подписи/токена вебхука и единым вызовом сервиса; исправить баг с несуществующим полем `order.status`.
- `backend:admin_api/views.py` — `update_status` тоже переводится на сервис (сохраняя текущий аудит-лог `log_admin_activity`), плюс явная проверка допустимости перехода вместо "просто валидный enum".
- `backend:island_bali/settings.py` — сменить `DEFAULT_PERMISSION_CLASSES` на `IsAuthenticated`, добавить `INSTALLED_APPS += ["channels"]`, `ASGI_APPLICATION`, `CHANNEL_LAYERS` (redis backend).
- `backend:island_bali/asgi.py` — заменить на `ProtocolTypeRouter` с `URLRouter` для WS-маршрутов + JWT-middleware.
- `backend:nginx/default.conf` — добавить `location /ws/` с проксированием на ASGI-контейнер и заголовками для upgrade.
- `backend:docker-compose.yaml` / `docker-compose.prod.yml` — новый сервис (`daphne`/`ws`), команда `daphne -b 0.0.0.0 -p 8001 island_bali.asgi:application`.

**Новые модули:**
- `orders/services/order_state.py` — `OrderStateService` с методом `transition(order, event, actor, **kwargs)`, таблицей допустимых переходов (раздел 3.5), `transaction.atomic()` + `select_for_update()` (или conditional `UPDATE ... WHERE status=X AND version=Y`), генерацией `django.db.transaction.on_commit(lambda: publish_order_event(order))` — событие публикуется **строго после commit**, что автоматически исключает отправку недокоммиченного изменения.
- `orders/events.py` — `publish_order_event(order)`: сериализует `order` через уже существующий `OrderSerializers`/новый компактный `OrderEventSerializer`, кладёт в Channels layer в группы `f"user.{order.user_id}"` и, если нужно — `f"shop.{order.coffee_shop_id}"` (для staff-экрана).
- `orders/consumers.py` — `OrderConsumer(AsyncJsonWebsocketConsumer)`: на `connect()` аутентифицирует по JWT (см. раздел 8), подписывает соединение на группу(ы) в зависимости от роли (customer → своя `user.{id}`; staff → `shop.{coffee_shop_id}` его смены).
- `orders/routing.py` — WS urlpatterns (`/ws/orders/`).
- `island_bali/jwt_ws_middleware.py` — middleware, достающий `access`-токен из query-параметра или `Sec-WebSocket-Protocol` и кладущий `scope["user"]` (переиспользует `rest_framework_simplejwt` валидацию, которая уже используется для HTTP).
- Миграция `orders/migrations/000X_add_version.py` — добавление `Orders.version` (см. раздел 5.3).

**DB changes:** одно новое поле `Orders.version` (integer, default 0) — минимально необходимое для conditional update и версии события. Отдельная `event_id` не требуется, если бизнес не просит идемпотентность на уровне клиента сверх того, что даёт `version` (см. раздел 9).

**Redis/broker:** нужен — уже есть в инфраструктуре, переиспользуется `channels-redis` как channel layer. Отдельная Redis Pub/Sub-обвязка вручную не нужна — `channels-redis` уже реализует нужный паттерн (группы = каналы) поверх Redis.

---

## 7. Mobile changes

**Существующие файлы:**
- `mobile:feature/cart/widget/order_notification_scope.dart` — удалить `Timer _timer`/`Timer.periodic` (81-84) и прямые `_orderViewBLoC.add(fetch)` по таймеру; `didChangeAppLifecycleState` (188) вместо повторного fetch вызывает reconciliation через repository (см. ниже); весь `_orderViewBLoCListener` (127-179) и модальные виджеты (`ThanksOrder`, `_OrderFeedbackWidget`, `_OrderWaitingConfirmationWidget`, `_TimeChangedConfirmWidget`, `_OrderCanceledWidget`) остаются без изменений — они уже реагируют только на `OrderViewState`, а не на транспорт.
- `mobile:feature/cart/bloc/order_view/order_view_bloc.dart` — добавить новый **источник** событий: `OrderRepository`/`CartRepository` эмитит realtime-обновления через `Stream`, на который bloc подписывается (`on<OrderViewEvent>`/`emit.forEach` или явная подписка в конструкторе, закрываемая в `close()`). Оставить `bloc_concurrency.concurrent()` только если реально нужна параллельность нескольких независимых fetch — для одного заказа лучше `restartable()`/`sequential()`, чтобы не было гонки из P1-13.
- `mobile:feature/cart/data/repository/cart_repository.dart` — добавить `Stream<OrderView> watchActiveOrder()` (или аналог), реализация внутри дергает WS-сервис + делает первичный REST `viewOrders()` для reconciliation (раздел 9).
- `mobile:feature/staff/widget/staff_screen.dart` — тот же паттерн: убрать `Timer.periodic` (1198) и добавить `void dispose()` (сейчас отсутствует — это уже нужно исправить независимо от WebSocket, см. P1-15) с отменой `_acceptanceTimer`, закрытием трёх `OrderByStatusBloc` и отпиской stream listener.
- `mobile:main.dart` — регистрация нового `OrderSocketService` в DI (`RepositoryProvider`, создаётся один раз, `lazy: false`, т.к. должен начинать слушать сразу после логина).

**Новые классы:**
- `OrderSocketService` (например `feature/cart/data/socket/order_socket_service.dart`) — единственный владелец `WebSocketChannel`. Отвечает за: connect/disconnect, JWT в URL/заголовке, heartbeat (ping/pong или application-level `{"type":"ping"}`), exponential backoff reconnect, разбор входящих кадров в типизированные события (`OrderStatusChangedEvent`), экспонирует `Stream<OrderStatusChangedEvent>` наружу. **Не знает про Bloc, про UI, про диалоги.**
- `OrderRealtimeRepository` (или расширение `CartRepositoryImpl`) — связывает `OrderSocketService` и REST: на событие сокета не доверяет payload'у "как есть", а либо мержит по `version`/`updated_at`, либо просто триггерит `viewOrders()` (перечитать факт из REST) — простая и надёжная стратегия на первом этапе (см. раздел 9).
- `ConnectivityAwareReconnector` (можно на базе пакета `connectivity_plus`, которого сейчас нет в зависимостях, либо через `WidgetsBindingObserver` + retry-таймер) — слушает смену сети и форсирует reconnect, а не просто ждёт следующий backoff-тик.

**State-management changes:** `OrderViewBLoC` получает новый `OrderViewEvent` (например `.realtimeSync()`), который выполняет тот же путь, что и текущий `fetch` (переиспользуем `_fetch`), чтобы не дублировать бизнес-логику интерпретации ответа сервера.

**`order_notification_scope.dart` — что остаётся/удаляется/переносится/заменяется:**

| Было | Действие |
|---|---|
| `Timer _timer` + `Timer.periodic(5s)` (81) | **Удалить.** Полностью заменяется подпиской на `OrderSocketService` внутри repository/bloc уровня. |
| `initState()`: первичный `fetch` при `isAuth` (78) | **Остаётся**, дополняется stream-подпиской (открывается в repository, не в виджете). |
| `didChangeAppLifecycleState`/`_onResumeCheck` (188-203) | **Переносится** назначение (не сам callback): вместо "просто fetch" — вызов reconciliation-метода repository (REST-снимок + гарантированный reconnect WS), логика редиректа в корзину при pending-оплате остаётся в виджете, т.к. это UI-навигация. |
| `_orderViewBLoCListener` и все диалоги (127-260, 640-960) | **Остаётся без изменений** — это единственно верное место для бизнес-правил "какой диалог показать", т.к. виджет уже реагирует только на `OrderViewState`. |
| `_checkLifePayStatus` (204-230), ad-hoc поллинг оплаты | Вне скоупа этого аудита по существу (это оплата, не статус заказа), но технически может быть заменено на тот же WS-канал позже отдельным событием `payment.status_changed`. |
| Прямое создание/парсинг транспорта | Виджет и так этого не делает (уже хорошо) — фиксируется как требование не регрессировать при рефакторинге. |

**Reconnect/reconciliation lifecycle (мобильный):**

```
App start / login          → connect WS + GET /api/orders/orders/ (снимок истины)
App resumed (foreground)   → если WS уже соединён — ничего; если нет — reconnect + принудительный REST snapshot
WS onDone/onError          → exponential backoff (например 1s,2s,4s,8s,capped 30s) + jitter
Reconnected после разрыва  → ОБЯЗАТЕЛЬНО повторный REST snapshot до начала доверия новым WS-событиям
Token refreshed            → переоткрыть соединение с новым токеном (WS-соединение не умеет "обновить" auth на лету)
Logout / смена пользователя → explicit disconnect + сброс bloc state (иначе события старого пользователя могут прийти в стрим уже под новым)
Connectivity changed → offline → online → форс reconnect, не ждать текущий backoff-таймер
```

---

## 8. WebSocket protocol

- **Connection URL:** `wss://<host>/ws/orders/` (за nginx, см. раздел 6). Один канал на пользователя достаточно (не нужен отдельный "order-level subscribe/unsubscribe" — у клиента и так активен максимум 1 незавершённый заказ одновременно, судя по `state.data!.last` в `order_notification_scope.dart:130` и по `existing_order`-проверке в `CheckoutView.post`, которая не даёт создать второй неоплаченный заказ). Для staff — второй consumer/группа `shop.{coffee_shop_id}`, т.к. персоналу нужны все заказы точки, а не один.
- **Authentication:** тот же JWT (`SIMPLE_JWT`, `access` token), передаётся при коннекте (query param `?token=` или `Sec-WebSocket-Protocol`, т.к. браузерный/Dart `WebSocketChannel` не позволяет произвольные заголовки на handshake без доп. библиотек) — middleware на сервере валидирует его через тот же `rest_framework_simplejwt`, кладёт `scope["user"]`. Соединение с невалидным/просроченным токеном — закрывается с явным кодом (см. ниже) сразу после handshake.
- **Группа/канал = user-level, а не order-level.** Обоснование: у клиента всегда "мой последний активный заказ" (см. выше), подписка на "все свои заказы" естественно решает задачу без дополнительного protoco-уровня subscribe/unsubscribe. Order-level имело бы смысл, если бы один пользователь мог одновременно следить за несколькими активными заказами (сейчас бизнес-правило это исключает).
- **Событие:** см. раздел 5.3 (`order.status_changed`).
- **Error messages:** `{"type": "error", "code": "auth_failed" | "forbidden" | "internal", "message": "..."}` перед закрытием соединения; закрытие — стандартные WS close codes (4401 — auth failed, 4403 — forbidden/order не принадлежит пользователю, 1011 — internal error).
- **Heartbeat:** application-level `{"type":"ping"}` от клиента раз в 20-30 сек, сервер отвечает `{"type":"pong"}`; если 2 heartbeat подряд не отвечены — клиент считает соединение мёртвым и переподключается (одного TCP/WS keостанется недостаточно за NAT/мобильными сетями, где разрыв не всегда доходит как явный `onError`).
- **Reconnect:** exponential backoff с verhaltenjitter на клиенте (раздел 7); сервер не обязан ничего специального делать для reconnect, кроме как быть stateless относительно соединения (вся истина — в БД, WS только уведомляет).
- **Event ordering/versioning:** событие включает `version` (новое поле, раздел 5.3/6). Клиент **не обязан** доверять последовательности доставки по TCP — то есть даже если WS гарантирует порядок в рамках одного соединения, reconnect создаёт разрыв, при котором порядок неизвестен. Правило: применять событие, только если `event.version > localOrder.version`либо просто раз в reconnect делать полный REST-snapshot и дальше доверять последовательности до следующего reconnect.

---

## 9. Reliability model

- **Потеря сети:** WS обрывается → клиент это обнаруживает по heartbeat/onError → UI не "зависает" на старом статусе, т.к. `OrderViewBLoC`/`_orderViewBLoCListener` продолжают показывать последнее известное `OrderViewState` (как и сейчас) — ничего критично нового не требуется, кроме индикатора "нет соединения" (сейчас такого индикатора тоже нет — можно добавить как улучшение UX, не обязательно для корректности).
- **Reconnect:** после восстановления сети — **обязательный REST snapshot** до начала доверия WS-событиям (раздел 7) — это и есть ответ на сценарий из задания (`PREPARING → offline → READY → COMPLETED → reconnect`): реальный `status_orders` в БД к этому моменту уже `Completed`/`Canceled`, значит `GET /api/orders/orders/` немедленно вернёт актуальное значение и UI не "застрянет" на `PREPARING`, независимо от того, сколько промежуточных WS-событий было пропущено, потому что клиент не полагается на "проигрывание" пропущенных событий по порядку — он один раз спрашивает "какой статус сейчас" и дальше просто продолжает слушать WS.
- **Restart backend:** т.к. вся истина в PostgreSQL, а не в памяти WS-процесса, рестарт ASGI-контейнера просто разрывает все соединения (клиенты переподключаются по backoff) без потери данных о статусе.
- **Process kill приложения:** при cold start — `initState()`/DI поднимает repository → сразу REST snapshot + открытие WS, тот же путь, что и "reconnect" (раздел 7) — отдельной логики не нужно, cold start = частный случай reconnect с пустым локальным состоянием.
- **Несколько backend instances:** сейчас 1 инстанс (раздел 1.4) — но `channels-redis` изначально спроектирован под множество ASGI-процессов (публикация в группу — через Redis, любой процесс с активным соединением на эту группу её получит), так что добавление второго `web`/`ws`-контейнера в будущем не потребует архитектурных изменений на этом уровне — только не забыть перевести и HTTP-уровень (раздел 3, 4) на `select_for_update()`/conditional update до того, как это станет актуально.
- **Несколько устройств одного пользователя:** группа `user.{id}` естественно поддерживает множественные соединения от разных устройств — просто несколько consumer-инстансов в одной группе, каждое получает копию события. Ничего специально проектировать не нужно, кроме как не завязываться на "ровно одно соединение на пользователя" при реализации consumer'а.
- **Пропущенные события:** закрываются пунктом "reconnect ⇒ обязательный REST snapshot" — WebSocket в этой архитектуре осознанно **не** является единственным источником истины (что и просило задание), это чисто уведомительный (at-most-once, best-effort) канал поверх REST-как-истины.
- **Duplicate events:** безопасны, т.к. клиентское применение обновления идемпотентно (просто "переприсвоить" `OrderView` из payload'а или заново вызвать REST) — двойная доставка одного и того же `version` не меняет результат.
- **Out-of-order events:** отсекаются сравнением `version` на клиенте (раздел 8) — более старое событие, пришедшее позже, игнорируется.

---

## 10. Security

- **Authentication:** переиспользуется существующий `SIMPLE_JWT`/`rest_framework_simplejwt` (`backend:island_bali/settings.py:190-192, 201-209`) — тот же access-токен, что и для REST, валидируется тем же способом на WS handshake. Дополнительной инфраструктуры аутентификации заводить не нужно.
- **Authorization / "нельзя подписаться на чужой order_id":** т.к. предложенная модель — user-level группа (`user.{id}`), а не произвольная подписка на `order_id`, вопрос "может ли клиент запросить чужой order_id" в принципе не возникает на транспортном уровне — сервер сам решает, в какую группу положить соединение, исходя из `scope["user"]`, а не из того, что прислал клиент. Это прямо закрывает инвариант из задания ("пользователь получает события только тех заказов, к которым у него есть доступ") **при условии**, что `publish_order_event` (раздел 6) публикует событие только в группу владельца заказа (`order.user_id`), а для staff-группы (`shop.{coffee_shop_id}`) — только персоналу, у которого `Staff.place_of_work == order.coffee_shop` (это правило должно быть явно закодировано в `OrderConsumer.connect()`, а не предполагаться).
- **Токен по query-параметру** — стандартная практика для WS (т.к. кастомные заголовки на handshake не всегда доступны в клиентских WS-библиотеках), но означает, что токен может осесть в access-логах nginx/прокси — рекомендуется логировать WS-урлы с маскированием query-строки, либо использовать `Sec-WebSocket-Protocol` для передачи токена (не логируется nginx по умолчанию).
- **Token expiration/logout:** WS-соединение не "узнаёт" само по себе, что токен истёк на середине сессии (в отличие от HTTP, где каждый запрос ревалидируется). Нужно: (а) при логауте — явный disconnect с клиента; (б) на сервере — периодическая ревалидация уже открытых соединений (например, при каждом heartbeat-pong проверять `exp` токена, использованного при коннекте, и рвать соединение по истечении) — иначе соединение может пережить логический logout пользователя на срок до `ACCESS_TOKEN_LIFETIME` (сейчас 1 час, `settings.py:203`).
- **Leaked connections:** т.к. `channels-redis` хранит подписки в Redis, а не в памяти одного процесса, при падении ASGI worker'а соединения просто разрываются (клиенты видят `onDone`/`onError` и переподключаются) — специальной "уборки" не требуется сверх штатного поведения Channels.
- **PII в payload/логировании:** событие `order.status_changed` (раздел 5.3) не содержит телефон/email/имя — только `order_id`/статусы/даты, что хорошо. Отдельно стоит зафиксировать найденную в ходе аудита проблему (P3-24): `backend:acquiring/views.py` логирует через `print()` весь `data`-словарь, включающий `customer_phone`/`customer_email` (см. `create_invoice`) — это уже нарушение сейчас, независимо от WebSocket, стоит убрать/замаскировать при любом рефакторинге этого файла.
- **Систематическая уязвимость, напрямую влияющая на безопасность будущего WS:** глобальный `AllowAny`-дефолт (раздел 4, P0-6) означает, что если консьюмер/urls для WS случайно унаследуют этот же паттерн ("забыли явно указать permission") — WS-эндпоинт тоже окажется публичным. Это должно быть explicit-проверено в code review при реализации (`AuthMiddlewareStack` должен явно отклонять анонимные соединения, а не полагаться на дефолт).

---

## 11. Migration plan

- **M0 — Существующий flow (этот документ) + фикс P0-угроз без WebSocket.** Это не подготовка к WS, а самостоятельно необходимый и более приоритетный этап (сам аудит явно просил поставить его выше): закрыть 6 找到нных P0 (разделы 3-4) — убрать `AllowAny`-дефолт, добавить владельца/роль в фильтры IDOR-эндпоинтов, отключить/защитить `SBPPaymentCreateView` и `PaymentChangeStatus`, добавить проверку подписи в LifePay callback. Делается независимо от WS и не требует мобильного релиза.
- **M1 — Единый `OrderStateService` + `version`-поле + атомарные переходы.** Миграция БД (`version`), доменный сервис с таблицей допустимых переходов (раздел 3.5), перевод всех 23 точек мутации на вызов сервиса. Полностью серверная работа, не требует мобильного релиза, полностью покрывается тестами до деплоя.
- **M2 — Backend WebSocket foundation.** `channels`+`channels-redis` в зависимости, `ASGI_APPLICATION`, `CHANNEL_LAYERS`, JWT WS middleware, nginx `/ws/` роут, отдельный ASGI-контейнер в docker-compose. Ещё без реальных consumer'ов бизнес-логики — только "эхо"/health-check WS, чтобы обкатать инфраструктуру.
- **M3 — Order event publication.** `orders/events.py`/`publish_order_event`, вызов из `OrderStateService` через `transaction.on_commit`. Проверяется вручную/тестами, что события реально летят в Redis-группу — ещё без мобильного клиента.
- **M4 — Mobile WebSocket infrastructure.** `OrderSocketService` (раздел 7), подключение, heartbeat, backoff — за feature-флагом, не влияет на текущий поллинг (работают параллельно, WS только логируется/телеметрируется).
- **M5 — Integration with order state.** `OrderViewBLoC` получает новый источник событий, `CartRepository`/новый realtime-repository реализует reconciliation (REST snapshot при reconnect). Всё ещё за feature-флагом; поллинг остаётся как safety net.
- **M6 — Migration `order_notification_scope.dart`.** Убрать `Timer.periodic` (раздел 7, таблица) — теперь именно тогда, когда WS+reconciliation уже провалидированы в M4-M5 на части пользователей (canary/feature-флаг). `_orderViewBLoCListener` и диалоги не трогаются.
- **M7 — Reconciliation/reconnect hardening.** Нагрузочное и хаос-тестирование сценариев из раздела 9 (обрыв сети, kill процесса, рестарт backend, несколько устройств) — до полного отключения поллинга у всех пользователей.
- **M8 — Removal of old polling (customer).** Убрать fallback-поллинг для customer-flow полностью после подтверждённой стабильности WS в проде.
- **M9 — Staff-flow migration.** Тот же путь (M4-M8) для `staff_screen.dart`/`OrderBloc`/`OrderByStatusBloc` — отдельный этап, т.к. это независимый потребитель с другим паттерном подписки (`shop.{coffee_shop_id}`), и его 30-секундный поллинг создаёт основную часть текущей нагрузки.
- **M10 — Tests + production readiness.** Полное покрытие (раздел 12), нагрузочное тестирование WS (много соединений на группу), финальный review security-чеклиста (раздел 10) перед объявлением GA.

Нумерация расширена до M10 (в задании — до M8) из-за отдельного M1 (state machine) и отдельного M9 (staff-flow), которые в задании не были явно выделены, но обнаружились в ходе аудита как отдельные, не сводимые друг к другу этапы.

---

## 12. Tests

**Backend unit tests:**
- `OrderStateService.transition()` — для каждой пары (текущий статус, событие) из таблицы раздела 3.5: разрешённые переходы проходят, запрещённые — кидают исключение и не меняют БД.
- Конкурентный transition: два потока/треда одновременно вызывают `transition()` на одном `order_id` с разными событиями — ровно один должен победить, ровно один — получить явную ошибку "конфликт версии", ни разу — оба не должны "тихо" применить оба изменения (регрессионный тест на P0-7).
- Каждый из 23 существующих write-путей (раздел 3.1), после рефакторинга на сервис — тест, что нельзя выполнить запрещённый переход (например, `complete` из `Waiting`).

**Authorization tests:**
- IDOR-регрессия: `confirm_orders`/`cancel_orders`/`UpdateThankYouDialogView`/`UpdateOrderCancelledView` — запрос с токеном пользователя A на `order_id`, принадлежащий пользователю B, должен возвращать 403/404, не менять запись.
- Полностью неаутентифицированный запрос ко всем order-мутирующим эндпоинтам — 401.
- Payment webhook — запрос без валидной подписи отклоняется, не меняет заказ.
- WS: соединение с чужим/просроченным/невалидным токеном — закрывается до подписки на группу; клиент А не получает события заказов клиента Б (тест на реальном канале с двумя consumer'ами).
- Staff WS-группа: сотрудник кофейни X не получает события кофейни Y.

**WebSocket integration tests:**
- connect → событие статуса → доставка в течение SLA (например < 2с в тестовой среде).
- reconnect после обрыва → доставка snapshot + продолжение получения новых событий.
- heartbeat timeout → сервер закрывает "мёртвое" соединение.
- несколько соединений одного пользователя (2 устройства) — оба получают событие.

**Reconnect tests (mobile):**
- симуляция потери сети во время `PREPARING`, смены статуса "за кулисами" (прямой вызов API, минуя сокет), восстановления сети — итоговый UI-статус соответствует серверу, не завис на `PREPARING` (прямой тест сценария из задания).
- симуляция protracted offline (WS не может переподключиться много попыток) — backoff не долбит бэкенд бесконечно часто (проверка формулы бэкоффа).

**Event ordering tests:**
- искусственная доставка события со старым `version` после нового — клиент игнорирует старое.
- дублирующая доставка одного и того же `version` — не создаёт дублей в UI/не вызывает повторного показа диалога (регрессия на текущий `_isDialogOpen`-гейт, `order_notification_scope.dart:250`).

**Flutter unit tests:**
- `OrderViewBLoC` — новый источник событий (`realtimeSync`) корректно переиспользует существующий `_fetch` без дублирования логики маппинга ошибок.
- `MatchingState` — фикс потери `data` на ошибке (раздел 4, P1-14) — тест, что `error()`-состояние сохраняет предыдущий `data`.

**Widget tests:**
- `OrderNotificationScope` — при получении `OrderViewState` через мок-bloc (без реального WS/HTTP) корректно показывает нужный диалог для каждой комбинации статусов (уже неявно тестируемая сейчас логика, стоит формализовать до рефакторинга, чтобы иметь baseline).
- `staff_screen.dart` — после фикса dispose (P1-15) тест, что при `pumpWidget`→`removeWidget` не остаётся активных таймеров/подписок (можно проверить через `FakeAsync`/`flutter_test`'овский `tester.binding` pending timers assertion).

**Lifecycle tests:**
- app resumed из background с активным заказом → reconciliation REST-запрос выполняется ровно один раз (не дублируется с WS-инициированным).
- logout → WS отключается, повторный login другим пользователем не получает "хвост" событий предыдущей сессии.

**End-to-end сценарии:**
- Полный путь: создание заказа → accept → оплата (реальный/тестовый webhook) → complete → review, с проверкой, что на каждом шаге и customer-, и staff-приложение (если открыты одновременно) видят согласованное состояние без ручного обновления.
- Сценарий из задания дословно: `PREPARING → offline → READY → COMPLETED → reconnect` → финальный UI-статус `COMPLETED`, без промежуточного "зависания".
- Два сотрудника одновременно нажимают "Готово"/"Отмена" на одном заказе (M1) — ровно один переход применяется, второй получает явную ошибку в UI, а не тихий silent-fail.

---

## 13. Final verdict

**`GO WITH REQUIRED CHANGES`.**

Технически проект готов к WebSocket: DRF+SimpleJWT даёт готовую аутентификацию, Redis уже есть в инфраструктуре, деплой пока однопроцессный (упрощает первые этапы), а точка входа `order_notification_scope.dart` уже сегодня отделяет транспорт (bloc/repository) от UI-логики диалогов настолько, что миграция транспорта возможна почти без изменения самого файла (раздел 7, таблица).

**Но** переход нельзя начинать с WebSocket-инфраструктуры (разделы 5-9) — сначала обязателен раздел 3/раздел 4 (P0). Причина буквально в тексте задания: WebSocket способен только *быстрее и надёжнее донести* то, что сервер решил про статус заказа. Если решение сервера ненадёжно (23 несинхронизированных мутатора, нулевая защита от гонок, минимум 3 публично эксплуатируемых способа бесплатно "оплатить" чужой заказ), быстрая доставка этого решения — не улучшение, а ухудшение: пользователи будут *быстрее и увереннее* видеть неправильные статусы.

**Рекомендуемая архитектура:** DRF (как есть) + Django Channels (`channels`/`channels-redis`) поверх существующего Redis, ASGI-процесс отдельно от WSGI/gunicorn, единый `OrderStateService` как единственная точка мутации `status_orders`, user-level WS-группа (не order-level), reconciliation "REST snapshot при каждом reconnect" вместо попытки гарантировать доставку каждого отдельного события. Одно событие `order.status_changed`, не набор специализированных типов.

**Главные риски:**
1. Мутация статуса сейчас настолько небезопасна и непредсказуема (раздел 3-4), что любая realtime-надстройка над ней рискует создать у команды ложное ощущение, что "теперь всё быстро и надёжно", маскируя фундаментальную проблему.
2. Минимум 3 находки P0 — это не гипотетические уязвимости, а прямая финансовая экспозиция (бесплатное "завершение" заказов) уже сегодня, независимо от WebSocket-проекта — по-хорошему это incident, а не пункт бэклога.
3. Staff-flow (`staff_screen.dart`) создаёт основную часть текущей поллинг-нагрузки и содержит собственные утечки ресурсов (P1-15) — если WebSocket-миграция коснётся только customer-flow (как буквально было в задании), staff-flow останется главным источником нагрузки и главным источником гонок с customer-действиями (раздел 3.3, сценарии 1-3), потому что именно staff-эндпоинты чаще всего инициируют опасные переходы.

**Что обязательно сделать до начала реализации WebSocket (M0/M1, раздел 11):**
- Сменить `DEFAULT_PERMISSION_CLASSES` на `IsAuthenticated`, аудит всех view без явного `permission_classes`.
- Закрыть IDOR на `confirm_orders`/`cancel_orders`/`UpdateThankYouDialogView`/`UpdateOrderCancelledView`.
- Отключить или защитить (подпись/секрет + привязка к реальному провайдеру) `SBPPaymentCreateView`, `PaymentChangeStatus`, `lifepay_callback`/`LifePayCallbackView`.
- Ввести единый `OrderStateService` с явной таблицей переходов и атомарной/условной записью (`select_for_update()` или conditional `UPDATE`), перевести на него все найденные 23 точки мутации.
- Исправить runtime-баг `complete_order()` (отсутствующий аргумент) и баг с несуществующим полем `order.status` в `acquiring/views.py`.
