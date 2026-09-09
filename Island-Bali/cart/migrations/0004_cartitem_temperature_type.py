# Написана вручную: в окружении разработчика Django не установлен, поэтому
# makemigrations не запускался. Перед выкладкой прогнать
# `python manage.py makemigrations --check --dry-run` — расхождений быть не должно.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cart', '0003_remove_cartitem_unique_cart_product'),
    ]

    operations = [
        migrations.AddField(
            model_name='cartitem',
            name='temperature_type',
            field=models.CharField(
                blank=True,
                choices=[('Hot', 'Горячий'), ('Cold', 'Холодный')],
                help_text='Выбор клиента для этой позиции. У товара в каталоге есть '
                          'своё поле temperature_type — оно говорит, какой выбор '
                          'вообще возможен, а не что выбрали.',
                max_length=4,
                null=True,
                verbose_name='Температура напитка',
            ),
        ),
    ]
