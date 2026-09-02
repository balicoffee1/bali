from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('franchise', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='franchiserequest',
            name='status',
            field=models.CharField(
                choices=[
                    ('new', 'Новая'),
                    ('in_progress', 'В работе'),
                    ('completed', 'Договор заключен'),
                    ('rejected', 'Отклонена'),
                ],
                default='new',
                max_length=20,
                verbose_name='Статус обработки',
            ),
        ),
        migrations.AddField(
            model_name='franchiserequest',
            name='manager_comment',
            field=models.TextField(blank=True, default='', verbose_name='Комментарий менеджера'),
        ),
        migrations.AddField(
            model_name='franchiserequest',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now, verbose_name='Дата заявки'),
            preserve_default=False,
        ),
        migrations.AlterModelOptions(
            name='franchiserequest',
            options={
                'ordering': ['-created_at'],
                'verbose_name': 'Заявка на франшизу',
                'verbose_name_plural': 'Заявка на франшизу',
            },
        ),
    ]
