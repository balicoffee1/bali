from django.db import models

from cart.models import ShoppingCart
from coffee_shop.models import City, CoffeeShop
from staff.models import Staff
from users.models import CustomUser


class Orders(models.Model):
    WAITING = "Waiting"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"
    CANCELED = "Canceled"
    
    NEW = "New"
    PENDING = "Pending"
    PAID = "Paid"
    FAILED = "Failed"
    # WAITING_BARIST = 
    StatusOrders = [
        (NEW, "Новый"),
        (WAITING, "Ожидание"),
        (IN_PROGRESS, "Выполняется"),
        (COMPLETED, "Выполнен"),
        (CANCELED, "Отменен"),
    ]
    
    PaymentStatus = [
        (NEW, "Новый"),
        (PENDING, "Ожидание оплаты"),
        (PAID, "Оплачено"),
        (FAILED, "Неудача"),
    ]
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE,
                             related_name="user_orders",
                             verbose_name="Пользователь")
    city_choose = models.ForeignKey(City, related_name='city_choose',
                                    on_delete=models.CASCADE,
                                    verbose_name='Город в котором '
                                                 'заказывают кофе')
    coffee_shop = models.ForeignKey(CoffeeShop,
                                    related_name='coffee_shop_to_orders',
                                    verbose_name='Кофейня на улице',
                                    on_delete=models.CASCADE)
    cart = models.ForeignKey(ShoppingCart, on_delete=models.CASCADE,
                                verbose_name="Корзина пользователя")
    client_comments = models.TextField(blank=True, null=True,
                                       verbose_name='Комментарий клиента')
    staff_comments = models.TextField(blank=True, null=True,
                                      verbose_name='Комментарий сотрудника')
    time_is_finish = models.DateTimeField(blank=True, null=True,
                                          verbose_name='Время '
                                                       'до получения заказа')

    staff = models.ForeignKey(Staff, related_name='staff',
                              verbose_name="Исполнитель заказа",
                              on_delete=models.CASCADE,
                              null=True,
                              blank=True
    )
    status_orders = models.CharField(choices=StatusOrders, max_length=30,
                                     verbose_name="Статус заказа", default=NEW)
    payment_status = models.CharField(choices=PaymentStatus, max_length=30,
                                      verbose_name="Статус оплаты", default=NEW)
    receipt_photo = models.ImageField(upload_to='order_receipts/',
                                      blank=True, null=True,
                                      verbose_name='Фото чека заказа')
    created_at = models.DateTimeField(verbose_name='Дата создания', blank=True, null=True,)
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления', blank=True, null=True,)
    issued = models.BooleanField(default=False, verbose_name='Оформлен', null=True)
    full_price = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name='Полная стоимость заказа', default=0
    )
    updated_time = models.DateTimeField(
        verbose_name='Время обновления заказа', blank=True, null=True,
    )
    cancellation_reason = models.TextField(
        blank=True, null=True, verbose_name='Причина отмены заказа'
    )
    client_confirmed = models.BooleanField(
        default=False, verbose_name='Клиент подтвердил заказ'
    )
    
    is_appreciated = models.BooleanField(
        default=False, verbose_name='Клиент оценил заказ'
    )
    is_updated = models.BooleanField(
        default=False, verbose_name='Клиент оценил заказ'
    )
    isThankYouDialogOpen = models.BooleanField(
        default=False, verbose_name= 'Диалог благодарности открыт'
    )
    isOrderCancelled = models.BooleanField(
        default=False, verbose_name='Заказ отменен'
    )
    isTimeChangedDialog = models.BooleanField(
        default=False, verbose_name='Диалог изменения времени открыт'
    )
    is_used_discount = models.BooleanField(
        default=False, verbose_name='Скидка применена'
    )
    checkLoaded = models.BooleanField(default=False, verbose_name='Чек загружен', null=True)
    is_testing = models.BooleanField(
        default=False, verbose_name='Заказ тестовый'
    )

    # --- M1: доменное состояние ---
    # Эти поля меняются только внутри orders.services.OrderStateService (атомарно,
    # с select_for_update и проверкой допустимого перехода). Прямое присваивание
    # status_orders/payment_status/version/этих timestamp-полей где-либо ещё —
    # регрессия, закрытая аудитом (docs/order-status-websocket-audit.md).
    version = models.PositiveIntegerField(
        default=0,
        verbose_name='Версия бизнес-состояния заказа',
        help_text=(
            'Инкрементируется на каждый успешный переход status_orders/payment_status. '
            'НЕ увеличивается на чисто presentation-изменения (диалоги, staff-комментарии).'
        ),
    )
    payment_deadline_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Дедлайн оплаты',
        help_text='Момент создания заказа + 90 секунд. Устанавливается один раз и не пересчитывается.',
    )
    payment_started_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Начало текущей попытки оплаты',
    )
    provider_paid_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Момент подтверждения оплаты провайдером',
        help_text='Timestamp от платёжного провайдера, а не время получения webhook нашим backend.',
    )

    def __str__(self):
        return f'Заказ в {self.coffee_shop} от пользователя {self.user}'

    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'

    # confirm_order/cancel_order/complete_order/process_payment были удалены в M1:
    # они меняли status_orders/payment_status без проверки текущего состояния и без
    # блокировки строки (аудит P0-2..P0-5, P1-9..P1-11). См. orders.services.OrderStateService.


class Notification(models.Model):
    order = models.ForeignKey(
        Orders, on_delete=models.CASCADE, related_name='notifications', 
        verbose_name='Заказ'
    )
    user = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name='notifications',
        verbose_name='Пользователь'
    )
    message = models.TextField(verbose_name='Текст уведомления')
    is_read = models.BooleanField(default=False, verbose_name='Прочитано')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Время создания')

    def __str__(self):
        return f'Уведомление для {self.user}: {self.message[:50]}'

    class Meta:
        verbose_name = 'Уведомление'
        verbose_name_plural = 'Уведомления'


class PaymentWebhookEvent(models.Model):
    """
    Журнал уже обработанных провайдерских событий оплаты — идемпотентность webhook'ов (M1, п.21).

    Ключ идемпотентности — (provider, provider_event_id). provider_event_id формируется
    вызывающим кодом из того, что реально присылает провайдер (например, для LifePay —
    "<transaction_number>:<status_code>", т.к. номер транзакции у LifePay переиспользуется
    на разных стадиях одного платежа). Повторная попытка записать существующую пару —
    IntegrityError/get_or_create(created=False), которую сервис трактует как "уже обработано".
    """
    provider = models.CharField(max_length=32, verbose_name='Провайдер')
    provider_event_id = models.CharField(max_length=191, verbose_name='Идентификатор события провайдера')
    order = models.ForeignKey(
        Orders, on_delete=models.CASCADE, related_name='payment_webhook_events', verbose_name='Заказ'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Обработано')

    class Meta:
        verbose_name = 'Обработанное платёжное событие'
        verbose_name_plural = 'Обработанные платёжные события'
        unique_together = ('provider', 'provider_event_id')

    def __str__(self):
        return f'{self.provider}:{self.provider_event_id} -> order {self.order_id}'


class PaymentReconciliation(models.Model):
    """
    Поздний платёж / расхождение между заказом и провайдером (M1, п.11-12).

    Заводится, когда провайдер сообщает об успешной оплате уже окончательно
    CANCELED (или иначе терминального) заказа. Сам факт создания записи НЕ меняет
    status_orders — воскрешение отменённого заказа поздним webhook'ом запрещено.
    Дальнейшая обработка — ручная (admin) или будущий refund-flow.
    """
    LATE_PAYMENT = 'LATE_PAYMENT'
    RESOLVED_REFUNDED = 'RESOLVED_REFUNDED'
    RESOLVED_ACKNOWLEDGED = 'RESOLVED_ACKNOWLEDGED'
    RECONCILIATION_STATUS_CHOICES = [
        (LATE_PAYMENT, 'Поздний платёж после отмены заказа'),
        (RESOLVED_REFUNDED, 'Оформлен возврат'),
        (RESOLVED_ACKNOWLEDGED, 'Подтверждено вручную без возврата'),
    ]

    order = models.ForeignKey(
        Orders, on_delete=models.CASCADE, related_name='payment_reconciliations', verbose_name='Заказ'
    )
    status = models.CharField(
        max_length=32, choices=RECONCILIATION_STATUS_CHOICES, default=LATE_PAYMENT,
        verbose_name='Статус реконсиляции',
    )
    provider = models.CharField(max_length=32, verbose_name='Провайдер')
    provider_transaction_id = models.CharField(max_length=191, blank=True, default='', verbose_name='ID транзакции провайдера')
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='Сумма')
    order_status_at_detection = models.CharField(
        max_length=30, verbose_name='Статус заказа на момент обнаружения'
    )
    detected_at = models.DateTimeField(auto_now_add=True, verbose_name='Обнаружено')
    resolved_at = models.DateTimeField(null=True, blank=True, verbose_name='Разрешено')
    resolved_by = models.ForeignKey(
        CustomUser, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='+', verbose_name='Кто разрешил',
    )
    note = models.TextField(blank=True, default='', verbose_name='Примечание')

    class Meta:
        verbose_name = 'Поздний платёж / реконсиляция'
        verbose_name_plural = 'Поздние платежи / реконсиляция'
        ordering = ['-detected_at']

    def __str__(self):
        return f'{self.status} order={self.order_id} provider={self.provider}'


class CheckOrder(models.Model):
    order = models.ForeignKey(Orders, on_delete=models.CASCADE,
                              related_name='check_orders',
                              verbose_name='Заказ')
    check_photo = models.ImageField(upload_to='check_orders/',
                                    blank=True, null=True,
                                    verbose_name='Фото чека заказа')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания', blank=True, null=True,)
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления', blank=True, null=True,)
    def __str__(self):
        return f'Чек заказа {self.order.id}'
    class Meta:
        verbose_name = 'Чек заказа'
        verbose_name_plural = 'Чеки заказов'
