import json

from django.conf import settings
from pywebpush import WebPushException, webpush

from home.models import PushSubscription


def send_push_notification(visitor_id, message):
    subscriptions = PushSubscription.objects.filter(
        numero_de_billet_id=visitor_id
    )

    for subscription in subscriptions:
        try:
            webpush(
                subscription_info={
                    "endpoint": subscription.endpoint,
                    "keys": {
                        "p256dh": subscription.p256dh,
                        "auth": subscription.auth,
                    },
                },
                data=json.dumps({
                    "title": "SanGoKueue",
                    "message": message,
                }),
                vapid_private_key=str(settings.VAPID_PRIVATE_KEY),
                vapid_claims=settings.VAPID_CLAIMS,
            )

        except WebPushException:
            pass