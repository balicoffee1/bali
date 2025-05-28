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
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания', blank=True, null=True,)
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


    def __str__(self):
        return f'Заказ в {self.coffee_shop} от пользователя {self.user}'

    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'
        
    
    def confirm_order(self, staff):
        """Подтверждает заказ и устанавливает его статус"""
        self.status_orders = self.COMPLETED
        self.payment_status = self.PENDING
        self.staff = staff  
        self.save()  

    def cancel_order(self, reason):
        """Отменяет заказ и записывает причину отмены"""
        self.status_orders = self.CANCELED  
        self.cancellation_reason = reason  
        self.save()
    
    def complete_order(self, reason):
        self.status_orders = self.COMPLETED
        self.save()
        
    
    def process_payment(self, payment_method):
        """Process payment for the order."""

        result = payment_method.process(self)  

        if result == "success":
            self.payment_status = self.PAID  
        else:
            self.payment_status = self.FAILED  

        self.save() 


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


class PaymentMethod:
    """Пример обработчика оплаты"""
    def __init__(self, method_type):
        self.method_type = method_type  # Например, 'СБП' или 'Эквайринг'

    def process(self, order):
        """Процесс обработки оплаты"""
        if self.method_type == "СБП":
            return "success"
        elif self.method_type == "Эквайринг":
            return "success"
        return "failed"


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