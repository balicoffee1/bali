from django.urls import path
from .views import (
    FilterCustomersView,
    GetCustomerView,
    BalanceView,
    OperationHistoryView,
    DebitHoldView,
    CreditHoldView,
    ReverseView,
    ReadCustomerView,
    ListCustomersView,
    CreateCustomerView,
    UpdateCustomerView,
    RemoveCustomerView
)

urlpatterns = [
    path('bonuses/filter-customers/', FilterCustomersView.as_view(), name='filter_customers'),
    path('bonuses/get-customer/', GetCustomerView.as_view(), name='get_customer'),
    path('bonuses/balance/', BalanceView.as_view(), name='balance'),
    path('bonuses/operation-history/', OperationHistoryView.as_view(), name='operation_history'),
    path('bonuses/debit-hold/', DebitHoldView.as_view(), name='debit_hold'),
    path('bonuses/credit-hold/', CreditHoldView.as_view(), name='credit_hold'),
    path('bonuses/reverse/', ReverseView.as_view(), name='reverse'),
    path('api/read/', ReadCustomerView.as_view(), name='read_customer'),
    path('api/list/', ListCustomersView.as_view(), name='list_customers'),
    path('api/create/', CreateCustomerView.as_view(), name='create_customer'),
    path('api/update/', UpdateCustomerView.as_view(), name='update_customer'),
    path('api/remove/', RemoveCustomerView.as_view(), name='remove_customer'),
]
