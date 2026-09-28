import json

from django.db import IntegrityError, transaction
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

from home.models import Billet, EnFile

TEMPS_MOYEN_PAR_PERSONNE = 120


def index(request):
    return HttpResponse("Hello, world. You're at the home index.")


def _personnes_devant(entree):
    """Visiteurs déjà en attente qui passeront avant cette entrée."""
    attente = EnFile.objects.filter(
        nom_file=entree.nom_file,
        appele=False,
    ).exclude(pk=entree.pk)
    if entree.numero_de_billet.priorite == Billet.Priorite.SUPER_SAIYAN:
        attente = attente.filter(
            numero_de_billet__priorite=Billet.Priorite.SUPER_SAIYAN,
        )
    return (
        attente.filter(date_entree__lt=entree.date_entree).count()
        + attente.filter(date_entree=entree.date_entree, pk__lt=entree.pk).count()
    )


def _message_notification(position, secondes):
    if secondes <= 0:
        temps = "0 min"
    elif secondes < 60:
        temps = "moins d'une minute"
    else:
        temps = f"{secondes // 60} min"
    return (
        "Vous avez rejoint la file. "
        f"Position {position}. Temps estimé : {temps}."
    )


def _erreur(message, status):
    return JsonResponse({"error": message}, status=status)


@csrf_exempt
@require_POST
def append_to_queue(request):
    """Inscrit un billet déjà authentifié dans la file et renvoie l'estimation."""
    try:
        corps = json.loads(request.body.decode() or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _erreur("Corps JSON invalide.", 400)

    if not isinstance(corps, dict):
        return _erreur("Corps JSON invalide.", 400)

    visitor_id = corps.get("visitorId")
    queue = corps.get("queue")
    if not isinstance(visitor_id, str) or not visitor_id.strip():
        return _erreur("visitorId est requis.", 400)
    if not isinstance(queue, str) or not queue.strip():
        return _erreur("queue est requis.", 400)

    visitor_id = visitor_id.strip()
    queue = queue.strip()

    try:
        billet = Billet.objects.get(pk=visitor_id)
    except Billet.DoesNotExist:
        return _erreur("Billet introuvable.", 404)

    if billet.date < timezone.localdate():
        return _erreur("Billet expiré.", 400)

    if EnFile.objects.filter(numero_de_billet=billet, nom_file=queue).exists():
        return _erreur("Ce billet est déjà dans la file.", 409)

    try:
        with transaction.atomic():
            entree = EnFile.objects.create(
                numero_de_billet=billet,
                nom_file=queue,
            )
    except IntegrityError:
        return _erreur("Ce billet est déjà dans la file.", 409)

    devant = _personnes_devant(entree)
    position = devant + 1
    secondes = devant * TEMPS_MOYEN_PAR_PERSONNE

    return JsonResponse(
        {
            "visitorId": visitor_id,
            "queue": queue,
            "position": position,
            "estimatedWaitSeconds": secondes,
            "notification": _message_notification(position, secondes),
        },
        status=201,
    )


MESSAGE_FILE_VIDEE = "La file a été vidée. Vous n'êtes plus en attente."


@csrf_exempt
@require_http_methods(["DELETE"])
def clear_queue(request):
    """Retire immédiatement tous les visiteurs d'une file et les notifie."""
    queue = request.GET.get("queue")
    if not isinstance(queue, str) or not queue.strip():
        return _erreur("queue est requis.", 400)

    queue = queue.strip()
    entrees = list(
        EnFile.objects.filter(nom_file=queue)
        .select_related("numero_de_billet")
        .order_by("date_entree", "pk")
    )
    notifications = [
        {
            "visitorId": entree.numero_de_billet_id,
            "message": MESSAGE_FILE_VIDEE,
        }
        for entree in entrees
    ]
    if entrees:
        EnFile.objects.filter(pk__in=[entree.pk for entree in entrees]).delete()

    return JsonResponse(
        {
            "queue": queue,
            "removed": len(notifications),
            "notifications": notifications,
        }
    )