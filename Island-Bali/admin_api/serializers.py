from rest_framework import serializers
from users.models import CustomUser, UserCard
from coffee_shop.models import City, CoffeeShop, CrmSystem, Acquiring
from menu_coffee_product.models import Category, Product, Addon, AdditiveFlavors, SeasonMenu
from orders.models import Orders, CheckOrder, Notification
from cart.models import ShoppingCart, CartItem
from staff.models import Staff, Shift
from reviews.models import ReviewsCoffeeShop
from franchise.models import FranchiseRequest, FranchiseInfo
from bonus_system.models import DiscountCard
from .models import AdminActivityLog


class AdminUserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    orders_count = serializers.SerializerMethodField()
    discount_rate = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = [
            'id', 'login', 'first_name', 'last_name', 'full_name',
            'phone_number', 'email', 'role', 'is_active', 'is_staff',
            'is_superuser', 'photo', 'orders_count', 'discount_rate'
        ]

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name or ''}".strip() or obj.login

    def get_orders_count(self, obj):
        return Orders.objects.filter(user=obj).count()

    def get_discount_rate(self, obj):
        card = DiscountCard.objects.filter(user=obj, is_active=True).first()
        return card.discount_rate if card else None


class AdminUserCardSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserCard
        fields = ['id', 'card_number', 'expiration_date']


class AdminUserDetailSerializer(AdminUserSerializer):
    cards = AdminUserCardSerializer(many=True, read_only=True)

    class Meta(AdminUserSerializer.Meta):
        fields = AdminUserSerializer.Meta.fields + ['cards', 'fcm_token']


class AdminCitySerializer(serializers.ModelSerializer):
    shops_count = serializers.SerializerMethodField()

    class Meta:
        model = City
        fields = ['id', 'name', 'shops_count']

    def get_shops_count(self, obj):
        return obj.coffeeshop_set.count() if hasattr(obj, 'coffeeshop_set') else CoffeeShop.objects.filter(city=obj).count()


class AdminCrmSystemSerializer(serializers.ModelSerializer):
    class Meta:
        model = CrmSystem
        fields = ['id', 'name']


class AdminAcquiringSerializer(serializers.ModelSerializer):
    class Meta:
        model = Acquiring
        fields = ['id', 'for_coffeeshop', 'name', 'login', 'password']
        extra_kwargs = {'password': {'write_only': True}}


class AdminCoffeeShopSerializer(serializers.ModelSerializer):
    city_name = serializers.CharField(source='city.name', read_only=True)

    class Meta:
        model = CoffeeShop
        fields = [
            'id', 'city', 'city_name', 'street', 'building_number', 'email',
            'telegram_username', 'telegram_id', 'crm_system', 'acquiring',
            'time_open', 'time_close', 'crm_email', 'crm_password', 'crm_layer_name',
            'lifepay_api_key', 'lifepay_login', 'inn', 'phone_number'
        ]
        extra_kwargs = {
            'crm_password': {'write_only': True, 'required': False},
            'lifepay_api_key': {'write_only': True, 'required': False},
        }


class AdminCategorySerializer(serializers.ModelSerializer):
    coffee_shop_street = serializers.CharField(source='coffee_shop.street', read_only=True)
    products_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'coffee_shop', 'coffee_shop_street', 'name', 'which_menu', 'products_count']

    def get_products_count(self, obj):
        return obj.products.count()


class AdminAdditiveFlavorsSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdditiveFlavors
        fields = ['id', 'coffee_shop', 'name']


class AdminAddonSerializer(serializers.ModelSerializer):
    flavors_details = AdminAdditiveFlavorsSerializer(source='flavors', many=True, read_only=True)

    class Meta:
        model = Addon
        fields = ['id', 'coffee_shop', 'name', 'description', 'price', 'flavors', 'flavors_details']


class AdminProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    coffee_shop_name = serializers.CharField(source='coffee_shop.__str__', read_only=True)
    addons_details = AdminAddonSerializer(source='addons', many=True, read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'coffee_shop', 'coffee_shop_name', 'category', 'category_name',
            'product', 'price', 'price_s', 'price_m', 'price_l',
            'availability', 'product_type', 'can_be_hot_and_cold',
            'temperature_type', 'which_menu', 'addons', 'addons_details'
        ]


class AdminCartItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.product', read_only=True)
    item_total = serializers.DecimalField(source='item_total_price', max_digits=10, decimal_places=2, read_only=True)
    addons_names = serializers.SerializerMethodField()
    flavors_names = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = ['id', 'product', 'product_name', 'size', 'amount', 'addons_names', 'flavors_names', 'item_total']

    def get_addons_names(self, obj):
        return [addon.name for addon in obj.addons.all()]

    def get_flavors_names(self, obj):
        return [flavor.name for flavor in obj.flavors.all()]


class AdminOrderSerializer(serializers.ModelSerializer):
    user_login = serializers.CharField(source='user.login', read_only=True)
    user_full_name = serializers.CharField(source='user.__str__', read_only=True)
    city_name = serializers.CharField(source='city_choose.name', read_only=True)
    coffee_shop_address = serializers.CharField(source='coffee_shop.__str__', read_only=True)
    staff_name = serializers.CharField(source='staff.users.__str__', read_only=True, default=None)
    items = serializers.SerializerMethodField()
    review_details = serializers.SerializerMethodField()

    class Meta:
        model = Orders
        fields = [
            'id', 'user', 'user_login', 'user_full_name', 'city_choose', 'city_name',
            'coffee_shop', 'coffee_shop_address', 'staff', 'staff_name',
            'client_comments', 'staff_comments', 'time_is_finish',
            'status_orders', 'payment_status', 'receipt_photo', 'full_price',
            'cancellation_reason', 'client_confirmed', 'issued', 'is_testing',
            'created_at', 'updated_at', 'items', 'review_details'
        ]
        # M1 п.18/23: status_orders/payment_status раньше были обычными
        # writable-полями ModelSerializer — значит обычный PATCH/PUT
        # /api/admin/orders/<id>/ (стандартный ModelViewSet action, НЕ
        # update_status) мог сменить статус заказа в обход какой-либо
        # проверки, атомарности и audit trail. Единственный разрешённый путь
        # изменения статуса для админки — action update_status ->
        # OrderStateService.admin_override (см. admin_api/views.py).
        read_only_fields = ['status_orders', 'payment_status']

    def get_items(self, obj):
        if obj.cart:
            return AdminCartItemSerializer(obj.cart.items.all(), many=True).data
        return []

    def get_review_details(self, obj):
        if hasattr(obj, 'review'):
            return {
                'evaluation': obj.review.evaluation,
                'comments': obj.review.comments,
                'very_tasty': obj.review.very_tasty,
                'wide_range': obj.review.wide_range,
                'nice_prices': obj.review.nice_prices,
            }
        return None


class AdminStaffSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='users.__str__', read_only=True)
    user_phone = serializers.CharField(source='users.phone_number', read_only=True)
    place_of_work_name = serializers.CharField(source='place_of_work.__str__', read_only=True)
    current_shift_status = serializers.SerializerMethodField()

    class Meta:
        model = Staff
        fields = ['id', 'users', 'user_name', 'user_phone', 'place_of_work', 'place_of_work_name', 'current_shift_status']

    def get_current_shift_status(self, obj):
        shift = Shift.objects.filter(staff=obj).order_by('-id').first()
        return shift.status_shift if shift else "Closed"


class AdminShiftSerializer(serializers.ModelSerializer):
    staff_name = serializers.CharField(source='staff.users.__str__', read_only=True)
    coffee_shop_name = serializers.CharField(source='staff.place_of_work.__str__', read_only=True)

    class Meta:
        model = Shift
        fields = [
            'id', 'staff', 'staff_name', 'coffee_shop_name',
            'start_time', 'end_time', 'number_orders_closed',
            'amount_closed_orders', 'status_shift'
        ]


class AdminReviewSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.__str__', read_only=True)
    user_phone = serializers.CharField(source='user.phone_number', read_only=True)
    coffee_shop_name = serializers.CharField(source='coffee_shop.__str__', read_only=True)
    order_price = serializers.DecimalField(source='orders.full_price', max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = ReviewsCoffeeShop
        fields = [
            'id', 'coffee_shop', 'coffee_shop_name', 'user', 'user_name', 'user_phone',
            'orders', 'order_price', 'evaluation', 'very_tasty', 'wide_range',
            'nice_prices', 'comments'
        ]


class AdminFranchiseRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = FranchiseRequest
        fields = ['id', 'name', 'number_phone', 'text', 'status', 'manager_comment', 'created_at']
        read_only_fields = ['created_at']


class AdminDiscountCardSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.__str__', read_only=True)
    user_phone = serializers.CharField(source='user.phone_number', read_only=True)
    coffee_shop_name = serializers.CharField(source='coffee_shop.__str__', read_only=True)

    class Meta:
        model = DiscountCard
        fields = [
            'id', 'user', 'user_name', 'user_phone', 'is_active',
            'qr_code', 'qr_code_image', 'discount_rate', 'coffee_shop', 'coffee_shop_name'
        ]


class AdminActivityLogSerializer(serializers.ModelSerializer):
    user_login = serializers.CharField(source='user.login', read_only=True, default="Система")
    user_name = serializers.CharField(source='user.__str__', read_only=True, default="Система")

    class Meta:
        model = AdminActivityLog
        fields = [
            'id', 'user', 'user_login', 'user_name', 'action', 'entity_name',
            'entity_id', 'summary', 'changes', 'ip_address', 'created_at'
        ]


class AdminNotificationBroadcastSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200, default="Happy Island")
    message = serializers.CharField(max_length=1000)
    city_id = serializers.IntegerField(required=False, allow_null=True)
    coffee_shop_id = serializers.IntegerField(required=False, allow_null=True)
    user_id = serializers.IntegerField(required=False, allow_null=True)
