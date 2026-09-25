from django.db import migrations, models
import django.db.models.deletion


def populate_existing_telegram_recipients(apps, schema_editor):
    CoffeeShop = apps.get_model('coffee_shop', 'CoffeeShop')
    CoffeeShopTelegramRecipient = apps.get_model('coffee_shop', 'CoffeeShopTelegramRecipient')

    for shop in CoffeeShop.objects.exclude(telegram_id__isnull=True).exclude(telegram_id=''):
        CoffeeShopTelegramRecipient.objects.get_or_create(
            coffee_shop=shop,
            telegram_id=shop.telegram_id,
            defaults={
                'telegram_username': shop.telegram_username or '',
                'first_name': '',
                'is_active': True,
            }
        )


class Migration(migrations.Migration):

    dependencies = [
        ('coffee_shop', '0002_alter_coffeeshop_acquiring_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='CoffeeShopTelegramRecipient',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('telegram_id', models.CharField(max_length=100, verbose_name='ID в Telegram')),
                ('telegram_username', models.CharField(blank=True, default='', max_length=100, verbose_name='Username в Telegram')),
                ('first_name', models.CharField(blank=True, default='', max_length=100, verbose_name='Имя')),
                ('is_active', models.BooleanField(default=True, verbose_name='Активен')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата привязки')),
                ('coffee_shop', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='telegram_recipients', to='coffee_shop.coffeeshop', verbose_name='Кофейня')),
            ],
            options={
                'verbose_name': 'Получатель Telegram-уведомлений',
                'verbose_name_plural': 'Получатели Telegram-уведомлений',
                'unique_together': {('coffee_shop', 'telegram_id')},
            },
        ),
        migrations.RunPython(populate_existing_telegram_recipients, reverse_code=migrations.RunPython.noop),
    ]
