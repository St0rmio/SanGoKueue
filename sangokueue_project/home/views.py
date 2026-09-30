import json
import queue

from django.db import IntegrityError, transaction
from django.http import Http404, HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST
from django.shortcuts import render
from home import queues
from home.models import Billet, EnFile, EtatFile, PushSubscription
from home.notifications import send_notification
from django.conf import settings


TEMPS_MOYEN_PAR_PERSONNE = 40
ATTENTE_PRIORITE_SAIYAN = 25 * 60
DELAI_PRESENTATION = 10 * 60
QUEUE_NAME = "attraction"


def home(request):
    return render(request, 'home.html')


def service_worker(request):
    return render(
        request,
        "service-worker.js",
        content_type="application/javascript",
    )


def _join_queue(billet):
    """Place le billet dans la file unique. None si le billet est expiré."""
    if billet.date < timezone.localdate():
        return None

    entree = EnFile.objects.filter(
        numero_de_billet=billet,
        nom_file=QUEUE_NAME,
    ).first()

    if entree is not None:
        return entree

    try:
        with transaction.atomic():
            entree = EnFile.objects.create(
                numero_de_billet=billet,
                nom_file=QUEUE_NAME,
            )
            queues.append_to_queue(
                QUEUE_NAME,
                billet.pk,
                billet.priorite,
            )
            return entree

    except IntegrityError:
        return EnFile.objects.get(
            numero_de_billet=billet,
            nom_file=QUEUE_NAME,
        )


def _wait_context(billet, entree):
    if entree is None:
        return {
            "billet": billet,
            "expire": billet.date < timezone.localdate(),
            "absent": True,
        }

    if entree.appele:
        etat = EtatFile.objects.filter(
            nom_file=entree.nom_file
        ).first()

        restant = _secondes_restantes_appel(
            entree,
            etat,
            timezone.now(),
        )

        return {
            "billet": billet,
            "position": None,
            "attente_minutes": (restant or 0) // 60,
            "appele": True,
        }

    devant = _personnes_devant(entree)
    position = devant + 1
    attente_secondes = devant * TEMPS_MOYEN_PAR_PERSONNE

    return {
        "billet": billet,
        "position": position,
        "attente_texte": _formater_duree(attente_secondes),
        "appele": False,
    }


def visitor(request, numero=None):
    """Affiche l'espace visiteur et l'inscrit dans la file."""
    numero = (numero or request.GET.get("billet") or "").strip()

    if not numero:
        return render(
            request,
            "interface_visiteur.html",
            {"billet": None},
        )

    try:
        billet = Billet.objects.get(pk=numero)
    except Billet.DoesNotExist:
        raise Http404("Billet introuvable.")

    refreshing = bool(request.headers.get("HX-Request"))

    if request.method == "POST":
        remove_visitor(billet.pk, QUEUE_NAME)
        entree = None

    elif refreshing:
        entree = EnFile.objects.filter(
            numero_de_billet=billet,
            nom_file=QUEUE_NAME,
        ).first()

    else:
        entree = _join_queue(billet)

    context = _wait_context(billet, entree)

    if request.method == "POST":
        context["quitte"] = True

    if not refreshing:
        context["vapid_public_key"] = settings.VAPID_PUBLIC_KEY

    template = (
        "visitor_position.html"
        if refreshing
        else "interface_visiteur.html"
    )

    return render(request, template, context)


def _instant(etat, maintenant):
    """Horloge de la file : figée tant que la pause est active."""
    if (
        etat is not None
        and etat.en_pause
        and etat.mise_en_pause_le is not None
    ):
        return etat.mise_en_pause_le

    return maintenant


def _attente_secondes(entree, etat, maintenant):
    fin = _instant(etat, maintenant)

    if entree.date_entree >= fin:
        return 0

    return max(
        0,
        int(
            (fin - entree.date_entree).total_seconds()
        ) - entree.secondes_pause,
    )


def _secondes_restantes_appel(entree, etat, maintenant):
    if not entree.appele or entree.date_appel is None:
        return None

    fin = _instant(etat, maintenant)

    if entree.date_appel >= fin:
        ecoule = 0
    else:
        ecoule = (
            int(
                (fin - entree.date_appel).total_seconds()
            )
            - entree.secondes_pause_appel
        )

    return max(
        0,
        DELAI_PRESENTATION - max(0, ecoule),
    )


def _prochain_saiyan_ou_humain(entrees, etat, maintenant):
    saiyans = [
        entree
        for entree in entrees
        if (
            entree.numero_de_billet.priorite
            == Billet.Priorite.SAIYAN
        )
    ]

    humains = [
        entree
        for entree in entrees
        if (
            entree.numero_de_billet.priorite
            == Billet.Priorite.HUMAN
        )
    ]

    saiyan = min(
        saiyans,
        key=lambda entree: (
            entree.date_entree,
            entree.pk,
        ),
        default=None,
    )

    humain = min(
        humains,
        key=lambda entree: (
            entree.date_entree,
            entree.pk,
        ),
        default=None,
    )

    if saiyan is None:
        return humain

    if humain is None:
        return saiyan

    if (
        _attente_secondes(
            saiyan,
            etat,
            maintenant,
        )
        > ATTENTE_PRIORITE_SAIYAN
    ):
        return saiyan

    if saiyan.date_entree <= humain.date_entree:
        return saiyan

    return humain


def _ordre_attente(entrees, etat, maintenant):
    """Ordre d'appel : Super Saiyan, puis Saiyan/Humain selon l'attente figée."""
    en_ligne = [
        entree
        for entree in entrees
        if not entree.appele
    ]

    super_saiyans = sorted(
        (
            entree
            for entree in en_ligne
            if (
                entree.numero_de_billet.priorite
                == Billet.Priorite.SUPER_SAIYAN
            )
        ),
        key=lambda entree: (
            entree.date_entree,
            entree.pk,
        ),
    )

    autres = [
        entree
        for entree in en_ligne
        if (
            entree.numero_de_billet.priorite
            != Billet.Priorite.SUPER_SAIYAN
        )
    ]

    ordre = list(super_saiyans)

    while autres:
        suivant = _prochain_saiyan_ou_humain(
            autres,
            etat,
            maintenant,
        )
        ordre.append(suivant)
        autres.remove(suivant)

    return ordre


def _personnes_devant(entree):
    """Visiteurs déjà en attente qui passeront avant cette entrée."""
    etat = EtatFile.objects.filter(
        nom_file=entree.nom_file
    ).first()

    maintenant = timezone.now()

    entrees = list(
        EnFile.objects.filter(
            nom_file=entree.nom_file,
            appele=False,
        ).select_related("numero_de_billet")
    )

    for index, candidat in enumerate(
        _ordre_attente(
            entrees,
            etat,
            maintenant,
        )
    ):
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
        f"Position {position}. "
        f"Temps estimé : {_formater_duree(secondes)}."
    )


def _erreur(message, status):
    return JsonResponse(
        {"error": message},
        status=status,
    )


@require_POST
def subscribe_push(request):
    try:
        data = json.loads(
            request.body.decode() or "{}"
        )

    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
    ):
        return JsonResponse(
            {"success": False},
            status=400,
        )

    try:
        billet = Billet.objects.get(
            pk=data["visitorId"]
        )

        subscription = data["subscription"]
        keys = subscription["keys"]

        PushSubscription.objects.update_or_create(
            endpoint=subscription["endpoint"],
            defaults={
                "numero_de_billet": billet,
                "p256dh": keys["p256dh"],
                "auth": keys["auth"],
            },
        )

    except (
        KeyError,
        Billet.DoesNotExist,
    ):
        return JsonResponse(
            {"success": False},
            status=400,
        )

    return JsonResponse(
        {"success": True}
    )


@csrf_exempt
@require_POST
def append_to_queue(request):
    """Inscrit un billet déjà authentifié dans la file et renvoie l'estimation."""
    try:
        corps = json.loads(
            request.body.decode() or "{}"
        )

    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
    ):
        return _erreur(
            "Corps JSON invalide.",
            400,
        )

    if not isinstance(corps, dict):
        return _erreur(
            "Corps JSON invalide.",
            400,
        )

    visitor_id = corps.get("visitorId")
    queue = corps.get("queue")

    if (
        not isinstance(visitor_id, str)
        or not visitor_id.strip()
    ):
        return _erreur(
            "visitorId est requis.",
            400,
        )

    if (
        not isinstance(queue, str)
        or not queue.strip()
    ):
        return _erreur(
            "queue est requis.",
            400,
        )

    visitor_id = visitor_id.strip()
    queue = queue.strip()

    try:
        billet = Billet.objects.get(
            pk=visitor_id
        )

    except Billet.DoesNotExist:
        return _erreur(
            "Billet introuvable.",
            404,
        )

    if billet.date < timezone.localdate():
        return _erreur(
            "Billet expiré.",
            400,
        )

    if EnFile.objects.filter(
        numero_de_billet=billet,
        nom_file=queue,
    ).exists():
        return _erreur(
            "Ce billet est déjà dans la file.",
            409,
        )

    try:
        with transaction.atomic():
            entree = EnFile.objects.create(
                numero_de_billet=billet,
                nom_file=queue,
            )

            queues.append_to_queue(
                queue,
                visitor_id,
                billet.priorite,
            )

    except IntegrityError:
        return _erreur(
            "Ce billet est déjà dans la file.",
            409,
        )

    devant = _personnes_devant(entree)
    position = devant + 1
    secondes = (
        devant
        * TEMPS_MOYEN_PAR_PERSONNE
    )

    return JsonResponse(
        {
            "visitorId": visitor_id,
            "queue": queue,
            "position": position,
            "estimatedWaitSeconds": secondes,
            "notification": _message_notification(
                position,
                secondes,
            ),
        },
        status=201,
    )


def remove_visitor(visitor_id, queue):
    """Remove a ticket from a queue. None if it is not queued."""
    try:
        entree = EnFile.objects.get(
            numero_de_billet_id=visitor_id,
            nom_file=queue,
        )

    except EnFile.DoesNotExist:
        return None

    entree.delete()

    queues.remove_from_queue(
        queue,
        visitor_id,
    )

    return {
        "visitorId": visitor_id,
        "queue": queue,
        "left": True,
    }


@csrf_exempt
@require_http_methods(["DELETE"])
def leave_queue(request):
    """Permet à un participant de quitter une file d'attente."""
    visitor_id = request.GET.get(
        "visitorId"
    )

    queue = request.GET.get(
        "queue"
    )

    if (
        not isinstance(visitor_id, str)
        or not visitor_id.strip()
    ):
        return _erreur(
            "visitorId est requis.",
            400,
        )

    if (
        not isinstance(queue, str)
        or not queue.strip()
    ):
        return _erreur(
            "queue est requis.",
            400,
        )

    result = remove_visitor(
        visitor_id.strip(),
        queue.strip(),
    )

    if result is None:
        return _erreur(
            "Ce billet n'est pas dans la file.",
            404,
        )

    return JsonResponse(result)


MESSAGE_FILE_VIDEE = (
    "La file a été vidée. "
    "Vous n'êtes plus en attente."
)


def clear_visitors(queue):
    """Remove every visitor from a queue."""
    entrees = list(
        EnFile.objects.filter(
            nom_file=queue
        )
        .select_related(
            "numero_de_billet"
        )
        .order_by(
            "date_entree",
            "pk",
        )
    )

    notifications = [
        {
            "visitorId":
                entree.numero_de_billet_id,
            "message":
                MESSAGE_FILE_VIDEE,
        }
        for entree in entrees
    ]

    for notification in notifications:
        send_notification(
            notification["visitorId"],
            notification["message"],
        )

    if entrees:
        EnFile.objects.filter(
            pk__in=[
                entree.pk
                for entree in entrees
            ]
        ).delete()

    queues.clear_queue(queue)

    etat = EtatFile.objects.filter(
        nom_file=queue
    ).first()

    if (
        etat is not None
        and etat.en_pause
    ):
        queues.pause_queue(
            queue,
            True,
        )

    return {
        "queue": queue,
        "removed": len(notifications),
        "notifications": notifications,
    }


@csrf_exempt
@require_http_methods(["DELETE"])
def clear_queue(request):
    """Retire immédiatement tous les visiteurs d'une file et les notifie."""
    queue = request.GET.get("queue")

    if (
        not isinstance(queue, str)
        or not queue.strip()
    ):
        return _erreur(
            "queue est requis.",
            400,
        )

    return JsonResponse(
        clear_visitors(
            queue.strip()
        )
    )


def _duree_a_exclure(
    debut_chrono,
    debut_pause,
    maintenant,
):
    if debut_chrono >= maintenant:
        return 0

    if debut_chrono >= debut_pause:
        return int(
            (
                maintenant
                - debut_chrono
            ).total_seconds()
        )

    return int(
        (
            maintenant
            - debut_pause
        ).total_seconds()
    )


def _reprendre(
    queue,
    etat,
    maintenant,
):
    debut = etat.mise_en_pause_le

    if debut is not None:
        for entree in EnFile.objects.filter(
            nom_file=queue
        ):
            entree.secondes_pause += (
                _duree_a_exclure(
                    entree.date_entree,
                    debut,
                    maintenant,
                )
            )

            if entree.date_appel is not None:
                entree.secondes_pause_appel += (
                    _duree_a_exclure(
                        entree.date_appel,
                        debut,
                        maintenant,
                    )
                )

            entree.save(
                update_fields=[
                    "secondes_pause",
                    "secondes_pause_appel",
                ]
            )

    etat.en_pause = False
    etat.mise_en_pause_le = None

    etat.save(
        update_fields=[
            "en_pause",
            "mise_en_pause_le",
        ]
    )


def _message_pause(
    en_pause,
    position,
    secondes,
    restant_appel,
):
    if restant_appel is not None:
        temps = _formater_duree(
            restant_appel
        )

        if en_pause:
            return (
                "La file est en pause. "
                f"Il vous reste {temps} "
                "pour vous présenter."
            )

        return (
            "La file a repris. "
            f"Il vous reste {temps} "
            "pour vous présenter."
        )

    if position is None:
        if en_pause:
            return (
                "La file est en pause. "
                "Votre passage est suspendu."
            )

        return (
            "La file a repris. "
            "Vous pouvez vous présenter."
        )

    temps = _formater_duree(
        secondes
    )

    if en_pause:
        return (
            "La file est en pause. "
            f"Position {position}. "
            f"Temps estimé : {temps}."
        )

    return (
        "La file a repris. "
        f"Position {position}. "
        f"Temps estimé : {temps}."
    )


def _notifications_file(
    queue,
    etat,
    maintenant,
):
    entrees = list(
        EnFile.objects.filter(
            nom_file=queue
        ).select_related(
            "numero_de_billet"
        )
    )

    ordre = _ordre_attente(
        entrees,
        etat,
        maintenant,
    )

    positions = {
        entree.pk: position
        for position, entree
        in enumerate(
            ordre,
            start=1,
        )
    }

    notifications = []

    for entree in sorted(
        entrees,
        key=lambda item: (
            item.appele,
            positions.get(
                item.pk,
                0,
            ),
            item.date_entree,
            item.pk,
        ),
    ):
        restant = (
            _secondes_restantes_appel(
                entree,
                etat,
                maintenant,
            )
        )

        position = (
            None
            if entree.appele
            else positions[entree.pk]
        )

        secondes = (
            None
            if position is None
            else (
                position - 1
            ) * TEMPS_MOYEN_PAR_PERSONNE
        )

        notifications.append(
            {
                "visitorId":
                    entree.numero_de_billet_id,
                "position":
                    position,
                "estimatedWaitSeconds":
                    secondes,
                "remainingCallSeconds":
                    restant,
                "message":
                    _message_pause(
                        etat.en_pause,
                        position,
                        secondes or 0,
                        restant,
                    ),
            }
        )

    return notifications


@csrf_exempt
@require_http_methods(["PATCH"])
def pause_queue(request):
    """Met une file en pause ou la reprend, sans faire avancer les délais."""
    try:
        corps = json.loads(
            request.body.decode()
            or "{}"
        )

    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
    ):
        return _erreur(
            "Corps JSON invalide.",
            400,
        )

    if not isinstance(corps, dict):
        return _erreur(
            "Corps JSON invalide.",
            400,
        )

    queue = corps.get("queue")
    paused = corps.get("paused")

    if (
        not isinstance(queue, str)
        or not queue.strip()
    ):
        return _erreur(
            "queue est requis.",
            400,
        )

    if not isinstance(
        paused,
        bool,
    ):
        return _erreur(
            "paused est requis.",
            400,
        )

    return JsonResponse(
        set_queue_pause(
            queue.strip(),
            paused,
        )
    )


def set_queue_pause(
    queue,
    paused,
):
    """Pause or resume a queue without advancing timers."""
    maintenant = timezone.now()

    with transaction.atomic():
        etat, _cree = (
            EtatFile.objects.get_or_create(
                nom_file=queue
            )
        )

        if (
            paused
            and not etat.en_pause
        ):
            etat.en_pause = True
            etat.mise_en_pause_le = (
                maintenant
            )

            etat.save(
                update_fields=[
                    "en_pause",
                    "mise_en_pause_le",
                ]
            )

        elif (
            not paused
            and etat.en_pause
        ):
            _reprendre(
                queue,
                etat,
                maintenant,
            )

        queues.pause_queue(
            queue,
            etat.en_pause,
        )

    notifications = _notifications_file(
        queue,
        etat,
        timezone.now(),
    )

    for notification in notifications:
        send_notification(
            notification["visitorId"],
            notification["message"],
        )

    return {
        "queue": queue,
        "paused": etat.en_pause,
        "notifications": notifications,
    }