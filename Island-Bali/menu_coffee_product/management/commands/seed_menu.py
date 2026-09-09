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
    COFFEE_SHOPS,
    MAIN_MENU,
    SEASON_MENU,
)
from menu_coffee_product.models import (
    AdditiveFlavors,
    Addon,
    Category,
    Product,
    Season,
    SeasonMenu,
)

# Все четыре времени года; печатное меню пока описывает только зиму и весну,
# остальные наборы появятся в menu_happy_island.SEASON_MENU по мере готовности.
SEASON_TITLES = {season.value: season.label for season in Season}


class Command(BaseCommand):
    help = "Завести кофейню и наполнить её меню Happy Island."

    def add_arguments(self, parser):
        parser.add_argument(
            "--street",
            action="append",
            dest="streets",
            help="Улица точки. Можно повторять. Без этого флага наполняются все "
                 "точки сети из COFFEE_SHOPS.",
        )
        parser.add_argument("--city", default="Казань", help="Город для --street")
        parser.add_argument("--building", default="", help="Номер строения для --street")
        parser.add_argument(
            "--season",
            choices=sorted(SEASON_MENU) + ["all", "none"],
            default="all",
            help="Какие сезонные наборы включить. Доступны те сезоны, для "
                 "которых заведено печатное меню в SEASON_MENU, плюс all и "
                 "none. Остальные наборы остаются в базе с is_active=False.",
        )
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opts):
        self.dry = opts["dry_run"]
        season = opts["season"]

        if opts["streets"]:
            targets = [(opts["city"], st, opts["building"]) for st in opts["streets"]]
        else:
            targets = COFFEE_SHOPS

        with transaction.atomic():
            for city, street, building in targets:
                self.stdout.write(self.style.MIGRATE_HEADING(f"\n{city}, ул. {street}"))
                shop = self._shop(city, street, building)
                self._load_sections(shop, MAIN_MENU, "main_menu")
                seasonal = {
                    name: self._load_sections(
                        shop, sections, "season_menu", prefix=SEASON_TITLES[name]
                    )
                    for name, sections in SEASON_MENU.items()
                }
                self._apply_season(shop, seasonal, season)
                self._addons(shop)

            if self.dry:
                self.stdout.write(self.style.WARNING("\n--dry-run: изменения откачены"))
                transaction.set_rollback(True)

        per_shop = (
            sum(len(items) for _, items in MAIN_MENU)
            + sum(len(i) for s in SEASON_MENU.values() for _, i in s)
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"\nГотово. Точек: {len(targets)}, позиций на точку: {per_shop}, "
                f"всего: {per_shop * len(targets)}. Сезон: {season}."
            )
        )

    # ------------------------------------------------------------------ shop

    def _shop(self, city_name, street, building):
        city, _ = City.objects.get_or_create(name=city_name)
        shop = CoffeeShop.objects.filter(city=city, street=street).first()

        if shop is None:
            shop = CoffeeShop(
                city=city,
                street=street,
                building_number=building,
                # Сетевые дефолты: единственные записи, если они заведены.
                crm_system=CrmSystem.objects.order_by("id").first(),
                acquiring=Acquiring.objects.order_by("id").first(),
            )
            shop.save()
            self.stdout.write(self.style.SUCCESS(f"  создана кофейня (д. {building or '—'})"))
        else:
            if building and shop.building_number != building:
                shop.building_number = building
                shop.save(update_fields=["building_number"])
            self.stdout.write("  кофейня уже есть")
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
        """Активный сезон доступен, остальные — скрыты, но остаются в базе.

        Наборы всех сезонов лежат в базе постоянно; какой показывать —
        решает флаг ``SeasonMenu.is_active``, а не наличие записей. Раньше
        сезон переключали перезапуском этой команды.
        """
        for name, sections in seasonal.items():
            on = active == "all" or name == active
            ids = [p.id for products in sections.values() for p in products]
            Product.objects.filter(id__in=ids).update(availability=on)

            for title, products in sections.items():
                menu, _ = SeasonMenu.objects.get_or_create(
                    coffee_shop=shop,
                    season=name,
                    seasonal_section=title,
                    defaults={"is_active": on},
                )
                if menu.is_active != on:
                    menu.is_active = on
                    menu.save(update_fields=["is_active"])
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
