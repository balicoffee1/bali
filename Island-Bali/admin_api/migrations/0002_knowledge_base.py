from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('admin_api', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='KnowledgeCategory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('slug', models.SlugField(max_length=100, unique=True, verbose_name='Идентификатор (slug)')),
                ('name', models.CharField(max_length=150, verbose_name='Название отдела/категории')),
                ('icon_name', models.CharField(blank=True, default='BookOpen', max_length=50, verbose_name='Иконка')),
                ('order', models.PositiveIntegerField(default=0, verbose_name='Порядок сортировки')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Создано')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Обновлено')),
            ],
            options={
                'verbose_name': 'Категория базы знаний',
                'verbose_name_plural': 'Категории базы знаний',
                'ordering': ['order', 'id'],
            },
        ),
        migrations.CreateModel(
            name='KnowledgeArticle',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255, verbose_name='Заголовок статьи')),
                ('slug', models.SlugField(max_length=150, unique=True, verbose_name='URL-слаг статьи')),
                ('target_role', models.CharField(choices=[('all', 'Для всех ролей'), ('barista', 'Бариста'), ('manager', 'Управляющий'), ('owner', 'Только Owner (Владелец)'), ('admin', 'Администратор')], default='all', max_length=20, verbose_name='Целевая роль')),
                ('why_needed', models.TextField(blank=True, default='', verbose_name='Зачем это нужно?')),
                ('what_is_it', models.TextField(blank=True, default='', verbose_name='Что это такое?')),
                ('steps', models.JSONField(blank=True, default=list, verbose_name='Шаги инструкции (список)')),
                ('troubleshooting', models.JSONField(blank=True, default=list, verbose_name='Частые ошибки (список)')),
                ('mockup_type', models.CharField(choices=[('none', 'Без мокапа'), ('mobile-order', 'Экран мобильного заказа'), ('order-card', 'Карточка заказа Live Desk'), ('telegram-bot', 'Сообщение в Telegram-боте'), ('push-preview', 'Экран Push-уведомления'), ('shift-card', 'Карточка смены'), ('acquiring-card', 'Терминал эквайринга')], default='none', max_length=30, verbose_name='Тип мокапа')),
                ('quick_action', models.JSONField(blank=True, default=dict, verbose_name='Быстрое действие (переход)')),
                ('tags', models.JSONField(blank=True, default=list, verbose_name='Теги')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Дата обновления')),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='articles', to='admin_api.knowledgecategory', verbose_name='Категория / Отдел')),
            ],
            options={
                'verbose_name': 'Статья базы знаний',
                'verbose_name_plural': 'Статьи базы знаний',
                'ordering': ['category__order', 'id'],
            },
        ),
    ]
