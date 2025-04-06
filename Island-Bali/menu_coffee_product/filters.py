import django_filters
from .models import SeasonMenu, CoffeeShop
from .models import Addon

class SeasonMenuFilter(django_filters.FilterSet):
    city_id = django_filters.NumberFilter(
        field_name='coffee_shop__city__id',
        label="ID города",
    )
    coffee_shop = django_filters.CharFilter(
        field_name='coffee_shop__street',
        lookup_expr='icontains',
        label="Улица кофейни",
    )
    coffee_shop_id = django_filters.NumberFilter(
        field_name='coffee_shop__id',
        label="ID кофейни",
    )

    class Meta:
        model = SeasonMenu
        fields = ['city_id', 'coffee_shop', 'coffee_shop_id']



class AddonFilter(django_filters.FilterSet):
    city_id = django_filters.NumberFilter(
        field_name='coffee_shop__city__id',
        label="ID города",
    )
    coffee_shop = django_filters.CharFilter(
        field_name='coffee_shop__street',
        lookup_expr='icontains',
        label="Улица кофейни",
    )
    coffee_shop_id = django_filters.NumberFilter(
        field_name='coffee_shop__id',
        label="ID кофейни",
    )
    product_id = django_filters.NumberFilter(
        field_name='product__id',
        label="ID продукта",
        method='filter_by_product'
    )

    class Meta:
        model = Addon
        fields = [
            'city_id',
            'coffee_shop',
            'coffee_shop_id',
            'product_id'
        ]
    
    def filter_by_product(self, queryset, name, value):
        return queryset.filter(product__id=value).distinct()
