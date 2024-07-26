from django.urls import path

from .views import FranchiseRequestDetailView, FranchiseRequestViewSet

urlpatterns = [
    path("", FranchiseRequestViewSet.as_view()),
    path("detail/", FranchiseRequestDetailView.as_view()),
]
