from django.core.management.base import BaseCommand
from coffee_shop.models import City, CoffeeShop, CrmSystem, Acquiring
from menu_coffee_product.models import Category, Product
from django.db import transaction
from django.contrib.auth import get_user_model
from staff.models import Staff

class Command(BaseCommand):
    help = 'Populates the database with mock cities, coffee shops, categories, and products.'

    def handle(self, *args, **options):
        self.stdout.write("Seeding data...")

        with transaction.atomic():
            # 1. Create or get CrmSystem
            crm, _ = CrmSystem.objects.get_or_create(
                name="QuickRestoApi"
            )

            # 2. Create or get Acquiring
            acquiring, _ = Acquiring.objects.get_or_create(
                for_coffeeshop="Bali Main Shop",
                defaults={
                    "name": "RussianStandart",
                    "login": "mock_login",
                    "password": "mock_password"
                }
            )

            # 3. Create or get City
            city, _ = City.objects.get_or_create(name="Бали")
            self.stdout.write(f"Created/found City: {city.name}")

            # 4. Create or get CoffeeShop
            shop, shop_created = CoffeeShop.objects.get_or_create(
                city=city,
                street="Jalan Pantai Batu Bolong",
                building_number="42",
                defaults={
                    "email": "feedback@balicoffee.com",
                    "telegram_username": "@balicoffee",
                    "telegram_id": "123456789",
                    "crm_system": crm,
                    "acquiring": acquiring,
                    "time_open": "08:00:00",
                    "time_close": "22:00:00",
                    "crm_email": "crm@balicoffee.com",
                    "crm_password": "crmpassword",
                    "crm_layer_name": "MainLayer"
                }
            )
            if shop_created:
                self.stdout.write(f"Created new CoffeeShop at {shop.street} {shop.building_number}")
            else:
                self.stdout.write(f"Using existing CoffeeShop at {shop.street}")

            # 5. Create Categories
            coffee_category, _ = Category.objects.get_or_create(
                coffee_shop=shop,
                name="Кофе",
                defaults={"which_menu": "main_menu"}
            )
            tea_category, _ = Category.objects.get_or_create(
                coffee_shop=shop,
                name="Чай и Матча",
                defaults={"which_menu": "main_menu"}
            )
            self.stdout.write("Created/found categories: Кофе, Чай и Матча")

            # 6. Create Products
            # Product 1
            p1, p1_created = Product.objects.get_or_create(
                coffee_shop=shop,
                category=coffee_category,
                product="Капучино",
                defaults={
                    "price": 250.00,
                    "availability": True,
                    "product_type": "coffee",
                    "can_be_hot_and_cold": True,
                    "temperature_type": "All",
                    "price_s": 200.00,
                    "price_m": 250.00,
                    "price_l": 300.00,
                }
            )
            if p1_created:
                self.stdout.write("Created product: Капучино")

            # Product 2
            p2, p2_created = Product.objects.get_or_create(
                coffee_shop=shop,
                category=coffee_category,
                product="Американо",
                defaults={
                    "price": 180.00,
                    "availability": True,
                    "product_type": "coffee",
                    "can_be_hot_and_cold": False,
                    "temperature_type": "Hot",
                    "price_s": 150.00,
                    "price_m": 180.00,
                    "price_l": 220.00,
                }
            )
            if p2_created:
                self.stdout.write("Created product: Американо")

            # Product 3
            p3, p3_created = Product.objects.get_or_create(
                coffee_shop=shop,
                category=tea_category,
                product="Матча Латте",
                defaults={
                    "price": 280.00,
                    "availability": True,
                    "product_type": "matcha",
                    "can_be_hot_and_cold": True,
                    "temperature_type": "All",
                    "price_s": 230.00,
                    "price_m": 280.00,
                    "price_l": 330.00,
                }
            )
            if p3_created:
                self.stdout.write("Created product: Матча Латте")

            # 7. Create Barista User and Staff Profile
            User = get_user_model()
            barista_user, barista_created = User.objects.get_or_create(
                login="barista",
                defaults={
                    "first_name": "Иван",
                    "last_name": "Бариста",
                    "role": "employee",
                    "is_staff": True,
                    "phone_number": "+79998887766"
                }
            )
            if barista_created:
                barista_user.set_password("1")
                barista_user.save()
                self.stdout.write("Created User: barista (password: 1)")

            # Create Staff record
            staff_record, staff_created = Staff.objects.get_or_create(
                users=barista_user,
                defaults={"place_of_work": shop}
            )
            if staff_created:
                self.stdout.write(f"Linked barista user to CoffeeShop at {shop.street}")

            # 8. Create Regular Customer User
            client_user, client_created = User.objects.get_or_create(
                login="client",
                defaults={
                    "first_name": "Петр",
                    "last_name": "Клиент",
                    "role": "user",
                    "is_staff": False,
                    "phone_number": "+79991112233"
                }
            )
            if client_created:
                client_user.set_password("1")
                client_user.save()
                self.stdout.write("Created User: client (password: 1)")

        self.stdout.write(self.style.SUCCESS("Database seeding completed successfully!"))
