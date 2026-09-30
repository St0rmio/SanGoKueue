import json
import random
from datetime import timedelta

from urllib.parse import urlencode

from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from home.models import Billet, EnFile, EtatFile, EnFile, VisiteurEnAttraction
from home.views import (
    TEMPS_MOYEN_PAR_PERSONNE,
    _formater_duree,
    _ordre_attente,
    _secondes_restantes_appel,
    clear_visitors,
    remove_visitor,
    set_queue_pause,
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
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect("staff:staff")
        return render(request, "login.html", {"error": "Mauvais pseudo ou mot de passe"})
    return render(request, "login.html")


@login_required
def logout_view(request):
    logout(request)
    return render(request, "logout.html")


def _queue_names():
    from_entries = set(EnFile.objects.values_list("nom_file", flat=True))
    from_states = set(EtatFile.objects.values_list("nom_file", flat=True))
    return sorted(from_entries | from_states)


def _counts():
    return {
        row["nom_file"]: row["total"]
        for row in EnFile.objects.values("nom_file").annotate(total=Count("pk"))
    }


def _line(entry, position, wait_seconds, remaining_call):
    ticket = entry.numero_de_billet
    if remaining_call is not None:
        status = "Appelé"
        detail = f"Il reste {_formater_duree(remaining_call)} pour se présenter"
    else:
        status = "En attente"
        detail = _formater_duree(wait_seconds)
    return {
        "visitor_id": ticket.pk,
        "name": f"{ticket.prenom} {ticket.nom}",
        "priority": PRIORITY_LABELS.get(ticket.priorite, str(ticket.priorite)),
        "position": position,
        "status": status,
        "detail": detail,
        "called": entry.appele,
    }


def _queue_detail(name):
    state = EtatFile.objects.filter(nom_file=name).first()
    now = timezone.now()
    entries = list(
        EnFile.objects.filter(nom_file=name).select_related("numero_de_billet")
    )
    waiting = []
    for position, entry in enumerate(_ordre_attente(entries, state, now), start=1):
        waiting.append(_line(entry, position, (position - 1) * TEMPS_MOYEN_PAR_PERSONNE, None))
    called = []
    called_entries = sorted(
        (entry for entry in entries if entry.appele),
        key=lambda entry: (entry.date_appel or entry.date_entree, entry.pk),
    )
    for entry in called_entries:
        called.append(_line(entry, None, None, _secondes_restantes_appel(entry, state, now)))
    return {
        "name": name,
        "paused": bool(state and state.en_pause),
        "waiting": waiting,
        "called": called,
        "total": len(entries),
    }


def _back(queue):
    url = reverse("staff:staff")
    if queue:
        url = f"{url}?{urlencode({'queue': queue})}"
    return redirect(url)


@login_required
def staff_view(request):
    names = _queue_names()
    selected = (request.GET.get("queue") or "").strip()
    if selected not in names:
        selected = names[0] if names else ""
    counts = _counts()
    template = "staff_board.html" if request.headers.get("HX-Request") else "staff.html"
    return render(request, template, {
        "queues": [{"name": name, "total": counts.get(name, 0)} for name in names],
        "queue": _queue_detail(selected) if selected else None,
    })


@login_required
@require_POST
def pause_view(request):
    queue = (request.POST.get("queue") or "").strip()
    if not queue:
        messages.error(request, "Aucune file sélectionnée.")
        return redirect("staff:staff")
    paused = request.POST.get("action") == "pause"
    result = set_queue_pause(queue, paused)
    if result["paused"]:
        messages.success(request, f"La file « {queue} » est en pause.")
    else:
        messages.success(request, f"La file « {queue} » a repris.")
    return _back(queue)


@login_required
@require_POST
def clear_view(request):
    queue = (request.POST.get("queue") or "").strip()
    if not queue:
        messages.error(request, "Aucune file sélectionnée.")
        return redirect("staff:staff")
    result = clear_visitors(queue)
    messages.success(
        request,
        f"{result['removed']} visiteur(s) retiré(s) de « {queue} ».",
    )
    return _back(queue)


@login_required
@require_POST
def remove_view(request):
    queue = (request.POST.get("queue") or "").strip()
    visitor_id = (request.POST.get("visitor_id") or "").strip()
    if not queue or not visitor_id:
        messages.error(request, "Visiteur ou file manquant.")
        return _back(queue)
    entry = (
        EnFile.objects.select_related("numero_de_billet")
        .filter(numero_de_billet_id=visitor_id, nom_file=queue)
        .first()
    )
    if entry is None:
        messages.error(request, "Ce billet n'est pas dans la file.")
        return _back(queue)
    name = f"{entry.numero_de_billet.prenom} {entry.numero_de_billet.nom}"
    remove_visitor(visitor_id, queue)
    messages.success(request, f"{name} a été retiré de « {queue} ».")
    return _back(queue)


@login_required
@require_POST
def staff_scan_billet(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            numero_billet = data.get('numero_billet')
            
            # Vérification 1 : Le billet est-il enregistré dans la file courante ?
            en_file = EnFile.objects.get(numero_de_billet_id=numero_billet)
            
            # Vérification 2 : Éviter le double scan
            if hasattr(en_file, 'visiteurenattraction'):
                return JsonResponse({
                    'status': 'error', 
                    'message': "Ce visiteur est déjà dans l'attraction !"
                })
            
            # Succès : Création du visiteur en attraction (sans supprimer EnFile pour garder la liaison OneToOne)
            duree_secondes = random.randint(30, 90)
            heure_sortie = timezone.now() + timedelta(seconds=duree_secondes)
            
            VisiteurEnAttraction.objects.create(
                billet=en_file,
                heure_sortie_prevue=heure_sortie
            )
            
            return JsonResponse({
                'status': 'success', 
                'message': "Billet valide. Visiteur entré dans l'attraction."
            })
            
        except EnFile.DoesNotExist:
            # Rejet : Le billet n'est pas dans EnFile
            return JsonResponse({
                'status': 'error', 
                'message': "Billet invalide ou visiteur non présent dans la file d'attente."
            })