# Написана вручную: в окружении разработчика Django не установлен, поэтому
# makemigrations не запускался. Перед выкладкой прогнать
# `python manage.py makemigrations --check --dry-run`.
#
# Данные: у существующих записей SeasonMenu season проставляется по тексту
# раздела («Зима …» → winter, «Весна …» → spring), остальные остаются winter.

import colorfield.fields
from django.db import migrations, models
import django.db.models.deletion


SEASON_BY_PREFIX = (
    ("Зима", "winter"),
    ("Весна", "spring"),
    ("Лето", "summer"),
    ("Осень", "autumn"),
)


def fill_season_from_title(apps, schema_editor):
    SeasonMenu = apps.get_model('menu_coffee_product', 'SeasonMenu')
    for prefix, season in SEASON_BY_PREFIX:
        SeasonMenu.objects.filter(
            seasonal_section__startswith=prefix
        ).update(season=season)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('coffee_shop', '0001_initial'),
        ('menu_coffee_product', '0002_alter_product_product_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='category',
            name='color',
            field=colorfield.fields.ColorField(
                blank=True, default='', image_field=None, max_length=7,
                samples=None,
                help_text='Пусто — приложение возьмёт цвет из своего набора',
                verbose_name='Цвет плитки',
            ),
        ),
        migrations.AddField(
            model_name='category',
            name='icon',
            field=models.CharField(
                blank=True, default='', max_length=32,
                choices=[
                    ('palm_tree', 'Пальма'), ('beach_ball', 'Мяч'),
                    ('cappuccino', 'Капучино'), ('latte_art', 'Латте-арт'),
                    ('banana', 'Банан'), ('shaker', 'Шейкер'),
                    ('coconut', 'Кокос'), ('matcha', 'Матча'),
                    ('ice_cream', 'Мороженое'), ('tropical_leaf', 'Лист'),
                    ('lemon_slice', 'Лимон'), ('flamingo', 'Фламинго'),
                    ('sun', 'Солнце'), ('limonad', 'Лимонад'),
                    ('smoothie', 'Смузи'), ('energy_drink', 'Энергетик'),
                ],
                help_text='Пусто — приложение возьмёт иконку из своего набора',
                verbose_name='Иконка плитки',
            ),
        ),
        migrations.AddField(
            model_name='seasonmenu',
            name='season',
            field=models.CharField(
                default='winter', max_length=10,
                choices=[
                    ('winter', 'Зима'), ('spring', 'Весна'),
                    ('summer', 'Лето'), ('autumn', 'Осень'),
                ],
                verbose_name='Время года',
            ),
        ),
        migrations.AddField(
            model_name='seasonmenu',
            name='is_active',
            field=models.BooleanField(
                default=True,
                help_text='Каждая кофейня держит наборы на все четыре сезона и '
                          'включает нужный. Раньше для этого перезапускали seed_menu.',
                verbose_name='Показывать в приложении',
            ),
        ),
        migrations.AddField(
            model_name='seasonmenu',
            name='color',
            field=colorfield.fields.ColorField(
                blank=True, default='', image_field=None, max_length=7,
                samples=None,
                help_text='Пусто — приложение возьмёт цвет из своего набора',
                verbose_name='Цвет плитки',
            ),
        ),
        migrations.AddField(
            model_name='seasonmenu',
            name='icon',
            field=models.CharField(
                blank=True, default='', max_length=32,
                choices=[
                    ('palm_tree', 'Пальма'), ('beach_ball', 'Мяч'),
                    ('cappuccino', 'Капучино'), ('latte_art', 'Латте-арт'),
                    ('banana', 'Банан'), ('shaker', 'Шейкер'),
                    ('coconut', 'Кокос'), ('matcha', 'Матча'),
                    ('ice_cream', 'Мороженое'), ('tropical_leaf', 'Лист'),
                    ('lemon_slice', 'Лимон'), ('flamingo', 'Фламинго'),
                    ('sun', 'Солнце'), ('limonad', 'Лимонад'),
                    ('smoothie', 'Смузи'), ('energy_drink', 'Энергетик'),
                ],
                help_text='Пусто — приложение возьмёт иконку из своего набора',
                verbose_name='Иконка плитки',
            ),
        ),
        migrations.AlterField(
            model_name='seasonmenu',
            name='coffee_shop',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='season_menus',
                to='coffee_shop.coffeeshop',
                verbose_name='Кофейня',
            ),
        ),
        migrations.AlterModelOptions(
            name='seasonmenu',
            options={
                'ordering': ('coffee_shop_id', 'season', 'id'),
                'verbose_name': 'Сезонное меню',
                'verbose_name_plural': 'Сезонное меню',
            },
        ),
        migrations.RunPython(fill_season_from_title, noop),
        migrations.AddConstraint(
            model_name='seasonmenu',
            constraint=models.UniqueConstraint(
                fields=('coffee_shop', 'season', 'seasonal_section'),
                name='unique_season_section_per_shop',
            ),
        ),
    ]
