import json
import random
from datetime import timedelta
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from home.models import (
    Billet,
    EnFile,
    EtatFile,
    PushSubscription,
    VisiteurEnAttraction,
)
from home.push_notifications import send_push_notification
from home.views import (
    QUEUE_NAME,
    TEMPS_MOYEN_PAR_PERSONNE,
    _formater_duree,
    _ordre_attente,
    _secondes_restantes_appel,
    clear_visitors,
    envoyer_notifications_attente,
    remove_visitor,
    set_queue_pause,
)


CAPACITE_MAX = 50

MESSAGE_APPEL = (
    "C'est à vous ! "
    "Présentez-vous maintenant à l'entrée de l'attraction."
)


PRIORITY_LABELS = {
    Billet.Priorite.HUMAN: "Humain",
    Billet.Priorite.SAIYAN: "Saiyan",
    Billet.Priorite.SUPER_SAIYAN: "Super Saiyan",
}


def login_view(request):
    if request.user.is_authenticated:
        return redirect("staff:staff")

    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]

        user = authenticate(
            request,
            username=username,
            password=password,
        )

        if user is not None:
            login(request, user)
            return redirect("staff:staff")

        return render(
            request,
            "login.html",
            {
                "error": "Mauvais pseudo ou mot de passe"
            },
        )

    return render(
        request,
        "login.html",
    )


@login_required
def logout_view(request):
    logout(request)

    return render(
        request,
        "logout.html",
    )


def _queue_names():
    from_entries = set(
        EnFile.objects.values_list(
            "nom_file",
            flat=True,
        )
    )

    from_states = set(
        EtatFile.objects.values_list(
            "nom_file",
            flat=True,
        )
    )

    return sorted(
        from_entries | from_states
    )


def _counts():
    return {
        row["nom_file"]: row["total"]
        for row in (
            EnFile.objects
            .values("nom_file")
            .annotate(total=Count("pk"))
        )
    }


def _line(
    entry,
    position,
    wait_seconds,
    remaining_call,
):
    ticket = entry.numero_de_billet

    if remaining_call is not None:
        status = "Appelé"

        detail = (
            "Il reste "
            f"{_formater_duree(remaining_call)} "
            "pour se présenter"
        )

    else:
        status = "En attente"

        detail = _formater_duree(
            wait_seconds
        )

    return {
        "visitor_id": ticket.pk,
        "name": (
            f"{ticket.prenom} "
            f"{ticket.nom}"
        ),
        "priority": PRIORITY_LABELS.get(
            ticket.priorite,
            str(ticket.priorite),
        ),
        "position": position,
        "status": status,
        "detail": detail,
        "called": entry.appele,
    }


def _queue_detail(name):
    state = EtatFile.objects.filter(
        nom_file=name
    ).first()

    now = timezone.now()

    entries = list(
        EnFile.objects.filter(
            nom_file=name
        ).select_related(
            "numero_de_billet"
        )
    )

    waiting = []

    for position, entry in enumerate(
        _ordre_attente(
            entries,
            state,
            now,
        ),
        start=1,
    ):
        waiting.append(
            _line(
                entry,
                position,
                (
                    position - 1
                ) * TEMPS_MOYEN_PAR_PERSONNE,
                None,
            )
        )

    called = []

    called_entries = sorted(
        (
            entry
            for entry in entries
            if entry.appele
        ),
        key=lambda entry: (
            entry.date_appel
            or entry.date_entree,
            entry.pk,
        ),
    )

    for entry in called_entries:
        called.append(
            _line(
                entry,
                None,
                None,
                _secondes_restantes_appel(
                    entry,
                    state,
                    now,
                ),
            )
        )

    return {
        "name": name,
        "paused": bool(
            state
            and state.en_pause
        ),
        "waiting": waiting,
        "called": called,
        "total": len(entries),
    }


def _back(queue):
    url = reverse(
        "staff:staff"
    )

    if queue:
        url = (
            f"{url}?"
            f"{urlencode({'queue': queue})}"
        )

    return redirect(url)


@login_required
def staff_view(request):
    names = _queue_names()

    selected = (
        request.GET.get("queue")
        or ""
    ).strip()

    if selected not in names:
        selected = (
            names[0]
            if names
            else ""
        )

    counts = _counts()

    template = (
        "staff_board.html"
        if request.headers.get("HX-Request")
        else "staff.html"
    )

    return render(
        request,
        template,
        {
            "queues": [
                {
                    "name": name,
                    "total": counts.get(
                        name,
                        0,
                    ),
                }
                for name in names
            ],
            "queue": (
                _queue_detail(selected)
                if selected
                else None
            ),
        },
    )


@login_required
@require_POST
def pause_view(request):
    queue = (
        request.POST.get("queue")
        or ""
    ).strip()

    if not queue:
        messages.error(
            request,
            "Aucune file sélectionnée.",
        )

        return redirect(
            "staff:staff"
        )

    paused = (
        request.POST.get("action")
        == "pause"
    )

    result = set_queue_pause(
        queue,
        paused,
    )

    if result["paused"]:
        messages.success(
            request,
            f"La file « {queue} » est en pause.",
        )
    else:
        messages.success(
            request,
            f"La file « {queue} » a repris.",
        )

    return _back(queue)


@login_required
@require_POST
def clear_view(request):
    queue = (
        request.POST.get("queue")
        or ""
    ).strip()

    if not queue:
        messages.error(
            request,
            "Aucune file sélectionnée.",
        )

        return redirect(
            "staff:staff"
        )

    result = clear_visitors(
        queue
    )

    messages.success(
        request,
        (
            f"{result['removed']} "
            "visiteur(s) retiré(s) "
            f"de « {queue} »."
        ),
    )

    return _back(queue)


@login_required
@require_POST
def remove_view(request):
    queue = (
        request.POST.get("queue")
        or ""
    ).strip()

    visitor_id = (
        request.POST.get("visitor_id")
        or ""
    ).strip()

    if not queue or not visitor_id:
        messages.error(
            request,
            "Visiteur ou file manquant.",
        )

        return _back(queue)

    entry = (
        EnFile.objects
        .select_related(
            "numero_de_billet"
        )
        .filter(
            numero_de_billet_id=visitor_id,
            nom_file=queue,
        )
        .first()
    )

    if entry is None:
        messages.error(
            request,
            "Ce billet n'est pas dans la file.",
        )

        return _back(queue)

    name = (
        f"{entry.numero_de_billet.prenom} "
        f"{entry.numero_de_billet.nom}"
    )

    remove_visitor(
        visitor_id,
        queue,
    )

    messages.success(
        request,
        (
            f"{name} a été retiré "
            f"de « {queue} »."
        ),
    )

    return _back(queue)


@login_required
@require_POST
def staff_scan_billet(request):
    try:
        data = json.loads(
            request.body
        )

        numero_billet = data.get(
            "numero_billet"
        )

        # 1. Vérifier si le visiteur
        # est déjà dans l'attraction
        if VisiteurEnAttraction.objects.filter(
            billet_id=numero_billet
        ).exists():
            return JsonResponse(
                {
                    "status": "error",
                    "message": (
                        "Ce visiteur est déjà "
                        "dans l'attraction !"
                    ),
                }
            )

        # 2. Récupérer le visiteur
        # dans la file d'attente
        en_file = EnFile.objects.get(
            numero_de_billet_id=numero_billet
        )

        queue = en_file.nom_file

        # 3. Faire entrer le visiteur
        # dans l'attraction
        duree_secondes = random.randint(
            30,
            90,
        )

        heure_sortie = (
            timezone.now()
            + timedelta(
                seconds=duree_secondes
            )
        )

        VisiteurEnAttraction.objects.create(
            billet=en_file.numero_de_billet,
            heure_sortie_prevue=heure_sortie,
        )

        # 4. Le retirer proprement
        # de la file.
        # remove_visitor recalcule aussi
        # les notifications des personnes derrière.
        remove_visitor(
            numero_billet,
            queue,
        )

        return JsonResponse(
            {
                "status": "success",
                "message": (
                    "Billet valide. "
                    "Visiteur entré dans l'attraction."
                ),
            }
        )

    except EnFile.DoesNotExist:
        return JsonResponse(
            {
                "status": "error",
                "message": (
                    "Billet invalide ou non présent "
                    "dans la file d'attente."
                ),
            }
        )


@login_required
def attraction_board(request):
    maintenant = timezone.now()

    appeles = []

    with transaction.atomic():
        # 1. Faire sortir automatiquement
        # les visiteurs dont le temps est terminé
        VisiteurEnAttraction.objects.filter(
            heure_sortie_prevue__lte=maintenant
        ).delete()

        # 2. Compter les personnes
        # réellement dans l'attraction
        affluence = (
            VisiteurEnAttraction.objects.count()
        )

        # 3. Compter les visiteurs déjà appelés
        # mais pas encore scannés
        deja_appeles = (
            EnFile.objects.filter(
                nom_file=QUEUE_NAME,
                appele=True,
            ).count()
        )

        # Une personne déjà appelée
        # réserve déjà une place
        places_libres = max(
            0,
            (
                CAPACITE_MAX
                - affluence
                - deja_appeles
            ),
        )

        # 4. Vérifier si la file est en pause
        etat = EtatFile.objects.filter(
            nom_file=QUEUE_NAME
        ).first()

        file_en_pause = (
            etat is not None
            and etat.en_pause
        )

        # 5. Appeler autant de personnes
        # qu'il y a de places disponibles
        if (
            places_libres > 0
            and not file_en_pause
        ):
            entrees = list(
                EnFile.objects
                .select_for_update()
                .filter(
                    nom_file=QUEUE_NAME,
                    appele=False,
                )
                .select_related(
                    "numero_de_billet"
                )
            )

            ordre = _ordre_attente(
                entrees,
                etat,
                maintenant,
            )

            prochains = (
                ordre[:places_libres]
            )

            for prochain in prochains:
                prochain.appele = True

                prochain.date_appel = (
                    maintenant
                )

                prochain.save(
                    update_fields=[
                        "appele",
                        "date_appel",
                    ]
                )

                appeles.append(
                    prochain.pk
                )

    # 6. Envoyer "C'est à vous !"
    # aux personnes qui viennent d'être appelées
    for entree_id in appeles:
        prochain = (
            EnFile.objects.filter(
                pk=entree_id
            ).first()
        )

        if prochain is None:
            continue

        abonnement_existe = (
            PushSubscription.objects.filter(
                numero_de_billet_id=(
                    prochain.numero_de_billet_id
                )
            ).exists()
        )

        if (
            abonnement_existe
            and not prochain.notification_appel_envoyee
        ):
            send_push_notification(
                prochain.numero_de_billet_id,
                MESSAGE_APPEL,
            )

            prochain.notification_appel_envoyee = True

            prochain.save(
                update_fields=[
                    "notification_appel_envoyee"
                ]
            )

    # 7. Les personnes restantes
    # ont peut-être avancé dans la file
    if appeles:
        envoyer_notifications_attente(
            QUEUE_NAME
        )

    visiteurs = (
        VisiteurEnAttraction.objects
        .select_related("billet")
        .order_by("heure_entree")
    )

    compteur = visiteurs.count()

    return render(
        request,
        "staff_en_attraction.html",
        {
            "visiteurs": visiteurs,
            "compteur": compteur,
            "capacite_max": CAPACITE_MAX,
        },
    )