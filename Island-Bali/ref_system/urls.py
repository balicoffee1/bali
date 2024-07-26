from django.urls import path

from ref_system import views

urlpatterns = [path("", views.send_ref_link, name="send_ref_link")]
