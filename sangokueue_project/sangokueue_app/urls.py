"""
URL configuration for sangokueue_app project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from home import views as home_views

urlpatterns = [
    path(
        "service-worker.js",
        home_views.service_worker,
        name="service_worker",
    ),
    path("appendToQueue", home_views.append_to_queue, name="append_to_queue"),
    path("leaveQueue", home_views.leave_queue, name="leave_queue"),
    path("clearQueue", home_views.clear_queue, name="clear_queue"),
    path("pauseQueue", home_views.pause_queue, name="pause_queue"),
    path("admin/", admin.site.urls),
    path("visiteur/", home_views.visitor, name="visitor"),
    path("visiteur/<str:numero>/", home_views.visitor, name="visitor_billet"),
    path("home/", include("home.urls")),
    path("staff/", include("staff.urls")),
    path("", RedirectView.as_view(url="home/", permanent=True)),
    
]
