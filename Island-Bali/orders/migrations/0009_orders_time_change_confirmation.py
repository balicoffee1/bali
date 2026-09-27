# Generated manually on 2026-09-27.

from django.db import migrations, models


def backfill_pending_time_changes(apps, schema_editor):
    Orders = apps.get_model("orders", "Orders")
    # Не оставляем уже показанные, но ещё не подтверждённые предложения в
    # неразрешимом состоянии после выката нового контракта.
    Orders.objects.filter(
        updated_time__isnull=False,
        client_confirmed=False,
        status_orders__in=("New", "Waiting"),
    ).update(time_change_revision=1, pending_time_change_revision=1)


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0008_orders_server_pricing"),
    ]

    operations = [
        migrations.AddField(
            model_name="orders",
            name="time_change_revision",
            field=models.PositiveIntegerField(default=0, verbose_name="Версия изменения времени"),
        ),
        migrations.AddField(
            model_name="orders",
            name="pending_time_change_revision",
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name="Ожидающая подтверждения версия времени"),
        ),
        migrations.AddField(
            model_name="orders",
            name="time_change_confirmation_deadline_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Дедлайн подтверждения изменения времени"),
        ),
        migrations.RunPython(backfill_pending_time_changes, migrations.RunPython.noop),
    ]
