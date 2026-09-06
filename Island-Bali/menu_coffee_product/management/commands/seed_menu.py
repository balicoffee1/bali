"""Наполнение каталога кофейни меню Happy Island.

Идемпотентна: повторный запуск обновляет цены и состав, не плодя дубли.
Печатное меню и разбор колонок — в menu_coffee_product/data/menu_happy_island.py.

    python manage.py seed_menu --city Казань --street "Баумана" --building 10
    python manage.py seed_menu --season spring        # переключить сезон
    python manage.py seed_menu --dry-run              # только показать план
"""
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from coffee_shop.models import Acquiring, CoffeeShop, CrmSystem, City
from menu_coffee_product.data.menu_happy_island import (
    ADDON_FLAVORS,
    ADDONS,
    MAIN_MENU,
    SEASON_MENU,
)
from menu_coffee_product.models import (
    AdditiveFlavors,
    Addon,
    Category,
    Product,
    SeasonMenu,
)

SEASON_TITLES = {"winter": "Зима", "spring": "Весна"}


class Command(BaseCommand):
    help = "Завести кофейню и наполнить её меню Happy Island."

    def add_arguments(self, parser):
        parser.add_argument("--city", default="Казань")
        parser.add_argument("--street", help="Улица кофейни (обязательна при создании)")
        parser.add_argument("--building", default="", help="Номер строения")
        parser.add_argument(
            "--season",
            choices=sorted(SEASON_MENU) + ["none"],
            default="winter",
            help="Какой сезонный набор сделать доступным. Позиции другого сезона "
                 "остаются в базе, но с availability=False.",
        )
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opts):
        self.dry = opts["dry_run"]
        season = opts["season"]

        with transaction.atomic():
            shop = self._shop(opts)
            main = self._load_sections(shop, MAIN_MENU, "main_menu")
            seasonal = {}
            for name, sections in SEASON_MENU.items():
                seasonal[name] = self._load_sections(
                    shop, sections, "season_menu", prefix=SEASON_TITLES[name]
                )
            self._apply_season(shop, seasonal, season)
            self._addons(shop)

            if self.dry:
                self.stdout.write(self.style.WARNING("\n--dry-run: изменения откачены"))
                transaction.set_rollback(True)

        total_main = sum(len(items) for _, items in MAIN_MENU)
        total_season = sum(len(i) for s in SEASON_MENU.values() for _, i in s)
        self.stdout.write(
            self.style.SUCCESS(
                f"\nГотово. Основное меню: {total_main} позиций, "
                f"сезонное: {total_season}. Активен сезон: {season}."
            )
        )

    # ------------------------------------------------------------------ shop

    def _shop(self, opts):
        city, _ = City.objects.get_or_create(name=opts["city"])
        shop = CoffeeShop.objects.filter(city=city).first()

        if shop is None:
            if not opts["street"]:
                raise CommandError(
                    "Кофейни в этом городе ещё нет — укажите --street "
                    '(например: --street "Баумана" --building 10)'
                )
            shop = CoffeeShop(
                city=city,
                street=opts["street"],
                building_number=opts["building"],
                # Сетевые дефолты: единственные записи, если они заведены.
                crm_system=CrmSystem.objects.order_by("id").first(),
                acquiring=Acquiring.objects.order_by("id").first(),
            )
            shop.save()
            self.stdout.write(self.style.SUCCESS(f"Создана кофейня: {city.name}, {shop.street}"))
        else:
            self.stdout.write(f"Кофейня уже есть: {city.name}, {shop.street}")
        return shop

    # ------------------------------------------------------------------ menu

    def _load_sections(self, shop, sections, which_menu, prefix=None):
        """Возвращает {раздел: [Product, ...]}."""
        loaded = {}
        for section, items in sections:
            title = f"{prefix} · {section}" if prefix else section
            category, created = Category.objects.update_or_create(
                coffee_shop=shop,
                name=title,
                defaults={"which_menu": which_menu},
            )
            self.stdout.write(
                ("  + " if created else "  · ") + f"{title} ({len(items)})"
            )
            products = []
            for name, price_s, price_l, kind, temp in items:
                product, _ = Product.objects.update_or_create(
                    coffee_shop=shop,
                    product=name,
                    defaults={
                        "category": category,
                        "price_s": Decimal(price_s) if price_s else None,
                        "price_m": None,      # среднего размера в меню нет
                        "price_l": Decimal(price_l) if price_l else None,
                        "price": Decimal(price_l or price_s),
                        "product_type": kind,
                        "temperature_type": temp,
                        "can_be_hot_and_cold": False,
                        "which_menu": which_menu,
                        "availability": True,
                    },
                )
                products.append(product)
            loaded[title] = products
        return loaded

    def _apply_season(self, shop, seasonal, active):
        """Активный сезон доступен, остальные — скрыты, но остаются в базе."""
        for name, sections in seasonal.items():
            on = name == active
            ids = [p.id for products in sections.values() for p in products]
            Product.objects.filter(id__in=ids).update(availability=on)

            for title, products in sections.items():
                menu, _ = SeasonMenu.objects.get_or_create(
                    coffee_shop=shop, seasonal_section=title
                )
                menu.products.set(products)

            mark = self.style.SUCCESS("активен") if on else self.style.WARNING("скрыт")
            self.stdout.write(f"  сезон {SEASON_TITLES[name]}: {mark} ({len(ids)} позиций)")

    # ---------------------------------------------------------------- addons

    def _addons(self, shop):
        self.stdout.write("Добавки:")
        for name, price in ADDONS:
            addon, _ = Addon.objects.update_or_create(
                coffee_shop=shop,
                name=name,
                defaults={"price": Decimal(price)},
            )
            flavors = []
            for flavor_name in ADDON_FLAVORS.get(name, []):
                flavor, _ = AdditiveFlavors.objects.get_or_create(
                    coffee_shop=shop, name=flavor_name
                )
                flavors.append(flavor)
            addon.flavors.set(flavors)
            suffix = f" · вкусы: {len(flavors)}" if flavors else ""
            self.stdout.write(f"  · {name} — {price} ₽{suffix}")
