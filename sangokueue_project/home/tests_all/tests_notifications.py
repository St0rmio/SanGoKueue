from django.test import SimpleTestCase, override_settings
from channels.testing import WebsocketCommunicator
from channels.layers import get_channel_layer

from sangokueue_app.asgi import application


@override_settings(
    CHANNEL_LAYERS={
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        }
    }
)
class NotificationWebSocketTests(SimpleTestCase):

    async def test_receive_notification(self):
        communicator = WebsocketCommunicator(
            application,
            "/ws/notifications/H1/",
        )

        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        channel_layer = get_channel_layer()

        await channel_layer.group_send(
            "notifications_H1",
            {
                "type": "notification_message",
                "message": "Test notification",
            },
        )

        response = await communicator.receive_json_from()

        self.assertEqual(
            response["message"],
            "Test notification",
        )

        await communicator.disconnect()


    async def test_clear_queue_notification(self):
        communicator = WebsocketCommunicator(
            application,
            "/ws/notifications/H1/",
        )

        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        channel_layer = get_channel_layer()

        await channel_layer.group_send(
            "notifications_H1",
            {
                "type": "notification_message",
                "message": "La file a été vidée. Vous n'êtes plus en attente.",
            },
        )

        response = await communicator.receive_json_from()

        self.assertEqual(
            response["message"],
            "La file a été vidée. Vous n'êtes plus en attente.",
        )

        await communicator.disconnect()