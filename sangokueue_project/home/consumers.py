import json

from channels.generic.websocket import AsyncWebsocketConsumer


class NotificationConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.visitor_id = self.scope["url_route"]["kwargs"]["visitor_id"]
        self.group_name = f"notifications_{self.visitor_id}"

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name,
        )

        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name,
        )

    async def notification_message(self, event):
        await self.send(
            text_data=json.dumps({
                "message": event["message"],
            })
        )