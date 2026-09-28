import json

from django.db import IntegrityError, transaction
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST
from django.views.decorators.http import require_POST
from django.http import HttpResponse
from django.shortcuts import render

from home.models import Billet, EnFile, EtatFile

TEMPS_MOYEN_PAR_PERSONNE = 120
ATTENTE_PRIORITE_SAIYAN = 25 * 60
DELAI_PRESENTATION = 10 * 60


def home(request):
    return render(request, 'home.html')

def _instant(etat, maintenant):
    """Horloge de la file : figée tant que la pause est active."""
    if etat is not None and etat.en_pause and etat.mise_en_pause_le is not None:
        return etat.mise_en_pause_le
    return maintenant


def _attente_secondes(entree, etat, maintenant):
    fin = _instant(etat, maintenant)
    if entree.date_entree >= fin:
        return 0
    return max(
        0,
        int((fin - entree.date_entree).total_seconds()) - entree.secondes_pause,
    )


def _secondes_restantes_appel(entree, etat, maintenant):
    if not entree.appele or entree.date_appel is None:
        return None
    fin = _instant(etat, maintenant)
    if entree.date_appel >= fin:
        ecoule = 0
    else:
        ecoule = int((fin - entree.date_appel).total_seconds()) - entree.secondes_pause_appel
    return max(0, DELAI_PRESENTATION - max(0, ecoule))


def _prochain_saiyan_ou_humain(entrees, etat, maintenant):
    saiyans = [
        entree for entree in entrees
        if entree.numero_de_billet.priorite == Billet.Priorite.SAIYAN
    ]
    humains = [
        entree for entree in entrees
        if entree.numero_de_billet.priorite == Billet.Priorite.HUMAN
    ]
    saiyan = min(saiyans, key=lambda entree: (entree.date_entree, entree.pk), default=None)
    humain = min(humains, key=lambda entree: (entree.date_entree, entree.pk), default=None)
    if saiyan is None:
        return humain
    if humain is None:
        return saiyan
    if _attente_secondes(saiyan, etat, maintenant) > ATTENTE_PRIORITE_SAIYAN:
        return saiyan
    if saiyan.date_entree <= humain.date_entree:
        return saiyan
    return humain


def _ordre_attente(entrees, etat, maintenant):
    """Ordre d'appel : Super Saiyan, puis Saiyan/Humain selon l'attente figée."""
    en_ligne = [entree for entree in entrees if not entree.appele]
    super_saiyans = sorted(
        (
            entree for entree in en_ligne
            if entree.numero_de_billet.priorite == Billet.Priorite.SUPER_SAIYAN
        ),
        key=lambda entree: (entree.date_entree, entree.pk),
    )
    autres = [
        entree for entree in en_ligne
        if entree.numero_de_billet.priorite != Billet.Priorite.SUPER_SAIYAN
    ]
    ordre = list(super_saiyans)
    while autres:
        suivant = _prochain_saiyan_ou_humain(autres, etat, maintenant)
        ordre.append(suivant)
        autres.remove(suivant)
    return ordre


def _personnes_devant(entree):
    """Visiteurs déjà en attente qui passeront avant cette entrée."""
    etat = EtatFile.objects.filter(nom_file=entree.nom_file).first()
    maintenant = timezone.now()
    entrees = list(
        EnFile.objects.filter(nom_file=entree.nom_file, appele=False)
        .select_related("numero_de_billet")
    )
    for index, candidat in enumerate(_ordre_attente(entrees, etat, maintenant)):
        if candidat.pk == entree.pk:
            return index
    return len(entrees)


def _formater_duree(secondes):
    if secondes <= 0:
        return "0 min"
    if secondes < 60:
        return "moins d'une minute"
    return f"{secondes // 60} min"


def _message_notification(position, secondes):
    return (
        "Vous avez rejoint la file. "
        f"Position {position}. Temps estimé : {_formater_duree(secondes)}."
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


def _duree_a_exclure(debut_chrono, debut_pause, maintenant):
    if debut_chrono >= maintenant:
        return 0
    if debut_chrono >= debut_pause:
        return int((maintenant - debut_chrono).total_seconds())
    return int((maintenant - debut_pause).total_seconds())


def _reprendre(queue, etat, maintenant):
    debut = etat.mise_en_pause_le
    if debut is not None:
        for entree in EnFile.objects.filter(nom_file=queue):
            entree.secondes_pause += _duree_a_exclure(
                entree.date_entree, debut, maintenant,
            )
            if entree.date_appel is not None:
                entree.secondes_pause_appel += _duree_a_exclure(
                    entree.date_appel, debut, maintenant,
                )
            entree.save(update_fields=["secondes_pause", "secondes_pause_appel"])
    etat.en_pause = False
    etat.mise_en_pause_le = None
    etat.save(update_fields=["en_pause", "mise_en_pause_le"])


def _message_pause(en_pause, position, secondes, restant_appel):
    if restant_appel is not None:
        temps = _formater_duree(restant_appel)
        if en_pause:
            return f"La file est en pause. Il vous reste {temps} pour vous présenter."
        return f"La file a repris. Il vous reste {temps} pour vous présenter."
    if position is None:
        if en_pause:
            return "La file est en pause. Votre passage est suspendu."
        return "La file a repris. Vous pouvez vous présenter."
    temps = _formater_duree(secondes)
    if en_pause:
        return f"La file est en pause. Position {position}. Temps estimé : {temps}."
    return f"La file a repris. Position {position}. Temps estimé : {temps}."


def _notifications_file(queue, etat, maintenant):
    entrees = list(
        EnFile.objects.filter(nom_file=queue).select_related("numero_de_billet")
    )
    ordre = _ordre_attente(entrees, etat, maintenant)
    positions = {entree.pk: position for position, entree in enumerate(ordre, start=1)}
    notifications = []
    for entree in sorted(
        entrees,
        key=lambda item: (
            item.appele,
            positions.get(item.pk, 0),
            item.date_entree,
            item.pk,
        ),
    ):
        restant = _secondes_restantes_appel(entree, etat, maintenant)
        position = None if entree.appele else positions[entree.pk]
        secondes = None if position is None else (position - 1) * TEMPS_MOYEN_PAR_PERSONNE
        notifications.append({
            "visitorId": entree.numero_de_billet_id,
            "position": position,
            "estimatedWaitSeconds": secondes,
            "remainingCallSeconds": restant,
            "message": _message_pause(etat.en_pause, position, secondes or 0, restant),
        })
    return notifications


@csrf_exempt
@require_http_methods(["PATCH"])
def pause_queue(request):
    """Met une file en pause ou la reprend, sans faire avancer les délais."""
    try:
        corps = json.loads(request.body.decode() or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _erreur("Corps JSON invalide.", 400)

    if not isinstance(corps, dict):
        return _erreur("Corps JSON invalide.", 400)

    queue = corps.get("queue")
    paused = corps.get("paused")
    if not isinstance(queue, str) or not queue.strip():
        return _erreur("queue est requis.", 400)
    if not isinstance(paused, bool):
        return _erreur("paused est requis.", 400)

    queue = queue.strip()
    maintenant = timezone.now()

    with transaction.atomic():
        etat, _cree = EtatFile.objects.get_or_create(nom_file=queue)
        if paused and not etat.en_pause:
            etat.en_pause = True
            etat.mise_en_pause_le = maintenant
            etat.save(update_fields=["en_pause", "mise_en_pause_le"])
        elif not paused and etat.en_pause:
            _reprendre(queue, etat, maintenant)

    return JsonResponse({
        "queue": queue,
        "paused": etat.en_pause,
        "notifications": _notifications_file(queue, etat, timezone.now()),
    })
