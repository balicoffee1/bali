import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "island_bali.settings")

app = Celery("island_bali")
app.conf.broker_connection_retry_on_startup = True
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    'update-chart-data-daily': {
        'task': 'music_api.tasks.update_chart_data',
        'schedule': crontab(minute='*/15'),
    },
    # Код живёт пять минут, поэтому статус доставки имеет смысл спрашивать
    # часто: провайдер отдаёт его не мгновенно.
    'check-sms-delivery': {
        'task': 'users.tasks.check_sms_delivery',
        'schedule': crontab(minute='*/10'),
    },
    # Раньше баланс проверяли вручную «раз в месяц» по записи в реестре
    # доступов. Пустой счёт останавливает вход в приложение целиком.
    'notify-low-sms-balance': {
        'task': 'users.tasks.notify_low_sms_balance',
        'schedule': crontab(hour=9, minute=0),
    },
}


@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')