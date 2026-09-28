from django.urls import path

from . import views

app_name = 'staff'

urlpatterns = [
    path("", views.staff_view, name='staff'),
    path("login", views.login_view, name="login"),
    path("logout", views.logout_view, name="logout"),
]