# Написана вручную: в окружении разработчика Django не установлен, поэтому
# makemigrations не запускался. Перед выкладкой прогнать
# `python manage.py makemigrations --check --dry-run`.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0005_phoneverification'),
    ]

    operations = [
        migrations.AddField(
            model_name='phoneverification',
            name='client_id',
            field=models.CharField(
                blank=True, db_index=True, default='', max_length=32,
                help_text='Наш идентификатор сообщения, по нему сверяется статус.',
                verbose_name='clientId у провайдера',
            ),
        ),
        migrations.AddField(
            model_name='phoneverification',
            name='smsc_id',
            field=models.CharField(
                blank=True, db_index=True, default='', max_length=64,
                verbose_name='smscId у провайдера',
            ),
        ),
        migrations.AddField(
            model_name='phoneverification',
            name='delivery_status',
            field=models.CharField(
                blank=True, default='', max_length=32,
                help_text='queued, smsc submit, delivered, smsc reject, delivery error',
                verbose_name='Статус доставки',
            ),
        ),
        migrations.AddField(
            model_name='phoneverification',
            name='status_checked_at',
            field=models.DateTimeField(
                blank=True, null=True, verbose_name='Статус проверен',
            ),
        ),
    ]
