from django.urls import path

from .consumers import NotificationConsumer


websocket_urlpatterns = [
    path(
        "ws/notifications/<str:visitor_id>/",
        NotificationConsumer.as_asgi(),
    ),
]