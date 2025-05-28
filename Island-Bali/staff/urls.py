from django.urls import path

from staff import views
from staff.views import ShiftCloseOpenView

urlpatterns = [
    path("", views.PendingOrdersAcceptView.as_view()),
    path("complete_order/", views.CompleteOrdersView.as_view()),
    path("toggle-shift/", views.ShiftToggleView.as_view()),
    path("upload_receipt_photo/",
         views.UploadReceiptPhotoView.as_view()),
    path('orders/',
         views.OrdersByTimeView.as_view()),
    path('orders_by_status/',
         views.FilterOrdersByStatus.as_view()),
    path('staff/<int:pk>/', views.StaffDetailView.as_view(),
         name='staff-detail'),
    path('shift/close-open/', ShiftCloseOpenView.as_view(),
         name='shift-close-open'),
#     path("new-orders/", views.NewOrdersView.as_view(), name="new-orders"),

]
