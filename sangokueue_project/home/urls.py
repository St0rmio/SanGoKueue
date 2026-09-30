from django.urls import path

from . import views

app_name = 'home'

urlpatterns = [
    path("", views.home, name="home"),
    path("visiteur/", views.visitor, name="visitor"),   # ← la ligne ajoutée
]