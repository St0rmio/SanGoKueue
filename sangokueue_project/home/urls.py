from django.urls import path

from . import views

app_name = 'home'

urlpatterns = [
    path("", views.home, name="home"),
    path("a-propos/", views.a_propos, name="a_propos"),

    path(
        "push/subscribe",
        views.subscribe_push,
        name="subscribe_push",
    ),

    path(
        "visiteur/",
        views.visitor,
        name="visitor",
    ),
]