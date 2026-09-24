import time

import redis
from django.conf import settings

from home.models import Billet

_client = None

SAIYAN_PRIORITY_WAIT_SECONDS = 25 * 60
CALLED_WAIT_SECONDS = 10 * 60

_LANES = {
    Billet.Priorite.HUMAN: "human",
    Billet.Priorite.SAIYAN: "saiyan",
    Billet.Priorite.SUPER_SAIYAN: "super_saiyan",
}


def get_redis():
    global _client
    if _client is None:
        url = settings.CACHES["default"]["LOCATION"]
        _client = redis.Redis.from_url(url, decode_responses=True)
    return _client


def _lane_key(queue: str, lane: str) -> str:
    return f"queue:{queue}:{lane}"


def _called_key(queue: str) -> str:
    return f"queue:{queue}:called"


def _paused_key(queue: str) -> str:
    return f"queue:{queue}:paused"


def _lock_key(queue: str) -> str:
    return f"queue:{queue}:lock"


def _all_lane_keys(queue: str) -> list[str]:
    return [_lane_key(queue, lane) for lane in _LANES.values()]


def _head(client, key: str) -> tuple[str, float] | None:
    result = client.zrange(key, 0, 0, withscores=True)
    if not result:
        return None
    ticket_id, entered_at = result[0]
    return ticket_id, entered_at


def _pop_lane(client, key: str) -> str | None:
    result = client.zpopmin(key, count=1)
    if not result:
        return None
    ticket_id, _entered_at = result[0]
    return ticket_id


def _expire_called(client, queue: str) -> list[str]:
    key = _called_key(queue)
    overdue = client.zrangebyscore(key, min=0, max=time.time())
    if overdue:
        client.zrem(key, *overdue)
    return list(overdue)


def _mark_called(client, queue: str, ticket_id: str) -> None:
    deadline = time.time() + CALLED_WAIT_SECONDS
    client.zadd(_called_key(queue), {ticket_id: deadline})


def _next_from_lanes(client, queue: str) -> str | None:
    super_saiyan = _pop_lane(client, _lane_key(queue, "super_saiyan"))
    if super_saiyan is not None:
        return super_saiyan

    saiyan_key = _lane_key(queue, "saiyan")
    human_key = _lane_key(queue, "human")
    saiyan = _head(client, saiyan_key)
    human = _head(client, human_key)

    if saiyan is None and human is None:
        return None
    if saiyan is None:
        return _pop_lane(client, human_key)
    if human is None:
        return _pop_lane(client, saiyan_key)

    _saiyan_id, saiyan_entered_at = saiyan
    _human_id, human_entered_at = human
    saiyan_waited = time.time() - saiyan_entered_at

    if saiyan_waited > SAIYAN_PRIORITY_WAIT_SECONDS:
        return _pop_lane(client, saiyan_key)
    if saiyan_entered_at <= human_entered_at:
        return _pop_lane(client, saiyan_key)
    return _pop_lane(client, human_key)


def append_to_queue(queue: str, ticket_id: str, priorite: int) -> None:
    lane = _LANES[priorite]
    get_redis().zadd(_lane_key(queue, lane), {ticket_id: time.time()})


def pop_from_queue(queue: str) -> str | None:
    """Appelle le prochain visiteur et le place en file d'attente de validation (10 min)."""
    client = get_redis()
    if client.exists(_paused_key(queue)):
        return None

    with client.lock(_lock_key(queue), timeout=5, blocking_timeout=5):
        _expire_called(client, queue)
        ticket_id = _next_from_lanes(client, queue)
        if ticket_id is None:
            return None
        _mark_called(client, queue, ticket_id)
        return ticket_id


def validate_entry(queue: str, ticket_id: str) -> bool:
    """Le visiteur se présente à l'entrée. False s'il a dépassé les 10 min."""
    client = get_redis()
    with client.lock(_lock_key(queue), timeout=5, blocking_timeout=5):
        _expire_called(client, queue)
        removed = client.zrem(_called_key(queue), ticket_id)
        return bool(removed)


def expire_called(queue: str) -> list[str]:
    """Retire les visiteurs appelés qui n'ont pas validé dans les 10 min."""
    client = get_redis()
    with client.lock(_lock_key(queue), timeout=5, blocking_timeout=5):
        return _expire_called(client, queue)


def remove_from_queue(queue: str, ticket_id: str) -> None:
    client = get_redis()
    for key in _all_lane_keys(queue):
        client.zrem(key, ticket_id)
    client.zrem(_called_key(queue), ticket_id)


def clear_queue(queue: str) -> None:
    get_redis().delete(
        *_all_lane_keys(queue),
        _called_key(queue),
        _paused_key(queue),
    )


def pause_queue(queue: str, paused: bool) -> None:
    key = _paused_key(queue)
    if paused:
        get_redis().set(key, "1")
    else:
        get_redis().delete(key)


def is_paused(queue: str) -> bool:
    return bool(get_redis().exists(_paused_key(queue)))
