from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def send_notification(visitor_id, message):
    channel_layer = get_channel_layer()

    async_to_sync(channel_layer.group_send)(
        f"notifications_{visitor_id}",
        {
            "type": "notification_message",
            "message": message,
        },
    )