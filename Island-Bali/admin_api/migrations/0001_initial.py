from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('users', '0004_add_admin_roles'),
    ]

    operations = [
        migrations.CreateModel(
            name='AdminActivityLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(choices=[('CREATE', 'Создание'), ('UPDATE', 'Изменение'), ('DELETE', 'Удаление'), ('STATUS_CHANGE', 'Смена статуса'), ('LOGIN', 'Вход в систему')], default='UPDATE', max_length=20, verbose_name='Действие')),
                ('entity_name', models.CharField(max_length=100, verbose_name='Сущность')),
                ('entity_id', models.CharField(blank=True, default='', max_length=50, verbose_name='ID сущности')),
                ('summary', models.CharField(blank=True, default='', max_length=255, verbose_name='Краткое описание действия')),
                ('changes', models.JSONField(blank=True, default=dict, verbose_name='Детали изменений (diff)')),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True, verbose_name='IP адрес')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Время действия')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='admin_activity_logs', to=settings.AUTH_USER_MODEL, verbose_name='Администратор')),
            ],
            options={
                'verbose_name': 'Журнал действия администратора',
                'verbose_name_plural': 'Журнал действий администраторов',
                'ordering': ['-created_at'],
            },
        ),
    ]
