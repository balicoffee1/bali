# Generated manually on 2026-09-06.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0007_remove_orders_isordercancelled_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="orders",
            name="subtotal_price",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                max_digits=10,
                verbose_name="Стоимость до скидки",
            ),
        ),
        migrations.AddField(
            model_name="orders",
            name="discount_percent",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                max_digits=5,
                verbose_name="Процент скидки",
            ),
        ),
        migrations.AddField(
            model_name="orders",
            name="discount_amount",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                max_digits=10,
                verbose_name="Сумма скидки",
            ),
        ),
    ]
