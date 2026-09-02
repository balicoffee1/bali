from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0003_alter_customuser_is_active'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customuser',
            name='role',
            field=models.CharField(
                choices=[
                    ('owner', 'Владелец'),
                    ('admin', 'Администратор'),
                    ('moderator', 'Модератор'),
                    ('support', 'Служба поддержки'),
                    ('employee', 'Сотрудник'),
                    ('user', 'Пользователь'),
                ],
                default='user',
                max_length=12,
                verbose_name='Роль пользователя',
            ),
        ),
    ]
