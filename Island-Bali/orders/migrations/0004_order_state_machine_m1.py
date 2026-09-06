"""
M1: поля состояния заказа (version, payment_deadline_at, payment_started_at,
provider_paid_at) + модели PaymentWebhookEvent (идемпотентность webhook'ов)
и PaymentReconciliation (поздние платежи / реконсиляция).

Не destructive: только добавление новых nullable/с default полей и новых
таблиц — существующие данные не теряются и не требуют backfill (see
docs/order-status-websocket-audit.md и финальный отчёт M0/M1, раздел I).
"""
from django.conf import settings
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('orders', '0003_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='orders',
            name='version',
            field=models.PositiveIntegerField(
                default=0,
                help_text='Инкрементируется на каждый успешный переход status_orders/payment_status. НЕ увеличивается на чисто presentation-изменения (диалоги, staff-комментарии).',
                verbose_name='Версия бизнес-состояния заказа',
            ),
        ),
        migrations.AddField(
            model_name='orders',
            name='payment_deadline_at',
            field=models.DateTimeField(
                blank=True, null=True,
                help_text='Момент создания заказа + 90 секунд. Устанавливается один раз и не пересчитывается.',
                verbose_name='Дедлайн оплаты',
            ),
        ),
        migrations.AddField(
            model_name='orders',
            name='payment_started_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Начало текущей попытки оплаты'),
        ),
        migrations.AddField(
            model_name='orders',
            name='provider_paid_at',
            field=models.DateTimeField(
                blank=True, null=True,
                help_text='Timestamp от платёжного провайдера, а не время получения webhook нашим backend.',
                verbose_name='Момент подтверждения оплаты провайдером',
            ),
        ),
        migrations.CreateModel(
            name='PaymentWebhookEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('provider', models.CharField(max_length=32, verbose_name='Провайдер')),
                ('provider_event_id', models.CharField(max_length=191, verbose_name='Идентификатор события провайдера')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Обработано')),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payment_webhook_events', to='orders.orders', verbose_name='Заказ')),
            ],
            options={
                'verbose_name': 'Обработанное платёжное событие',
                'verbose_name_plural': 'Обработанные платёжные события',
                'unique_together': {('provider', 'provider_event_id')},
            },
        ),
        migrations.CreateModel(
            name='PaymentReconciliation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(
                    choices=[
                        ('LATE_PAYMENT', 'Поздний платёж после отмены заказа'),
                        ('RESOLVED_REFUNDED', 'Оформлен возврат'),
                        ('RESOLVED_ACKNOWLEDGED', 'Подтверждено вручную без возврата'),
                    ],
                    default='LATE_PAYMENT', max_length=32, verbose_name='Статус реконсиляции',
                )),
                ('provider', models.CharField(max_length=32, verbose_name='Провайдер')),
                ('provider_transaction_id', models.CharField(blank=True, default='', max_length=191, verbose_name='ID транзакции провайдера')),
                ('amount', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='Сумма')),
                ('order_status_at_detection', models.CharField(max_length=30, verbose_name='Статус заказа на момент обнаружения')),
                ('detected_at', models.DateTimeField(auto_now_add=True, verbose_name='Обнаружено')),
                ('resolved_at', models.DateTimeField(blank=True, null=True, verbose_name='Разрешено')),
                ('note', models.TextField(blank=True, default='', verbose_name='Примечание')),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payment_reconciliations', to='orders.orders', verbose_name='Заказ')),
                ('resolved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='Кто разрешил')),
            ],
            options={
                'verbose_name': 'Поздний платёж / реконсиляция',
                'verbose_name_plural': 'Поздние платежи / реконсиляция',
                'ordering': ['-detected_at'],
            },
        ),
    ]
