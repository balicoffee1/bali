from cart.models import CartItem, ShoppingCartfrom cart.serializers import CartItemSerializerfrom coffee_shop.models import City, CoffeeShopfrom menu_coffee_product.models import Productdef get_menu_item(menu_item_id):    """Эта функция будет отвечать за поиск продукта в базе данных    и обработку случая, если продукт не найден."""    try:        return Product.objects.get(id=menu_item_id)    except Product.DoesNotExist:        return Nonedef get_or_create_user_cart(user):    """Эта функция создаёт или возвращает существующую корзину пользователя."""    return ShoppingCart.objects.get_or_create(user=user)def add_or_update_cart_item(cart, menu_item, quantity):    """    Эта функция обновляет количество товара в корзине или    добавляет новый товар.    """    cart_item, created = CartItem.objects.get_or_create(cart=cart,                                                        product=menu_item)    cart_item.quantity += int(quantity)    cart_item.save()    return cart_itemdef get_city_and_coffee_shop(city_id, coffee_shop_id):    """Эта функция будет отвечать за проверку существования     города и кофейни в базе данных"""    try:        city = City.objects.get(id=city_id)        coffee_shop = CoffeeShop.objects.get(id=coffee_shop_id)        return city, coffee_shop    except (City.DoesNotExist, CoffeeShop.DoesNotExist):        return None, Nonedef check_temperature_requirements(menu_item, temperature_type):    if menu_item.can_be_hot_and_cold and not temperature_type:        return ("For items that can be hot and cold, "                "temperature type must be specified.")    if menu_item.product_type == 'coffee' and not temperature_type:        return "For coffee, temperature type must be specified."    if menu_item.product_type == 'tea' and not temperature_type:        return "For tea, temperature type must be specified."    if menu_item.product_type == 'cocktail' and temperature_type != "Cold":        return "Cocktails must be cold."    if (menu_item.product_type in            ['ice_cream',             'fresh_juice'] and temperature_type != "Cold"):        return "Ice cream and fresh juice must be cold."    if menu_item.product_type == 'matcha' and not temperature_type:        return "For matcha, temperature type must be specified."    return Nonedef process_cart_item(user, menu_item, quantity):    cart, created = get_or_create_user_cart(user)    cart_item = add_or_update_cart_item(cart, menu_item, quantity)    return CartItemSerializer(cart_item).data