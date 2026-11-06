"""Charge Locust sur le parcours visiteur et le tableau staff.

Avec Docker Compose, le service locust vise http://web:8000.
L'interface est sur http://localhost:8089.

Sans fichier load/billets.txt, le scénario utilise les billets de
démonstration créés par peupler_billets. Un utilisateur Locust = un billet.
Pour en avoir davantage :

    docker compose exec web python manage.py preparer_charge --nombre 200
"""

import os
import queue
import random
import re
import threading
import time
from pathlib import Path

from locust import HttpUser, between, events, task

ICI = Path(__file__).resolve().parent
PROJET = ICI.parent
FICHIER_BILLETS = Path(
    os.environ.get("LOCUST_BILLETS", ICI / "billets.txt")
)
FICHIER_DEMO = PROJET / "home" / "donnees_billets.py"

FILE = "attraction"
POOL = queue.Queue()
_BILLETS_CHARGES = 0
_dernier_vidage = 0.0
_verrou_vidage = threading.Lock()
VIDAGE_TOUTES_LES = 180


def _lire_billets():
    if FICHIER_BILLETS.is_file():
        return [
            ligne.strip()
            for ligne in FICHIER_BILLETS.read_text().splitlines()
            if ligne.strip() and not ligne.startswith("#")
        ]

    if not FICHIER_DEMO.is_file():
        return []

    trouves = re.findall(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        FICHIER_DEMO.read_text(),
    )
    vus = []
    deja = set()
    for identifiant in trouves:
        if identifiant not in deja:
            deja.add(identifiant)
            vus.append(identifiant)
    return vus


def charger_billets():
    global _BILLETS_CHARGES
    identifiants = _lire_billets()
    _BILLETS_CHARGES = len(identifiants)
    while not POOL.empty():
        try:
            POOL.get_nowait()
        except queue.Empty:
            break
    for identifiant in identifiants:
        POOL.put(identifiant)


def prendre_billet():
    try:
        return POOL.get_nowait()
    except queue.Empty:
        return None


def rendre_billet(identifiant):
    if identifiant:
        POOL.put(identifiant)


def entetes_csrf(client, referer):
    jeton = client.cookies.get("csrftoken", "")
    entetes = {"Referer": referer}
    if jeton:
        entetes["X-CSRFToken"] = jeton
    return jeton, entetes


def billets_du_tableau(html):
    """Lit les billets affichés sur le tableau staff."""
    appeles = []
    en_attente = []
    for ligne in html.split("<tr>")[1:]:
        trouve = re.search(
            r"<code>([0-9a-f-]{36})</code>",
            ligne,
        )
        if not trouve:
            continue
        identifiant = trouve.group(1)
        if "Appelé" in ligne:
            appeles.append(identifiant)
        elif "En attente" in ligne:
            en_attente.append(identifiant)
    return appeles, en_attente


@events.test_start.add_listener
def au_demarrage(environment, **kwargs):
    charger_billets()
    source = FICHIER_BILLETS if FICHIER_BILLETS.is_file() else FICHIER_DEMO
    print(f"{_BILLETS_CHARGES} billet(s) chargé(s) depuis {source}")
    if _BILLETS_CHARGES == 0:
        print(
            "Aucun billet. Le service web lance peupler_billets au démarrage. "
            "Pour aller plus loin : "
            "docker compose exec web python manage.py preparer_charge --nombre 200"
        )


class Visiteur(HttpUser):
    """Rejoint la file, rafraîchit sa position, puis la quitte."""

    wait_time = between(1, 3)
    weight = 9

    def on_start(self):
        self.billet = prendre_billet()
        self.en_file = False
        self.appele = False
        self.dans_attraction = False
        self.client.get("/home/", name="/home/")

    def on_stop(self):
        rendre_billet(self.billet)
        self.billet = None

    @task(2)
    def pages_publiques(self):
        self.client.get("/home/", name="/home/")
        self.client.get("/home/a-propos/", name="/home/a-propos/")

    @task(6)
    def consulter_la_file(self):
        if not self.billet:
            return

        if self.en_file or self.dans_attraction:
            with self.client.get(
                f"/visiteur/{self.billet}/",
                headers={"HX-Request": "true"},
                name="/visiteur/[billet]/ (position)",
                catch_response=True,
            ) as reponse:
                self._lire_reponse(reponse)
            return

        with self.client.get(
            f"/visiteur/{self.billet}/",
            name="/visiteur/[billet]/ (rejoindre)",
            catch_response=True,
        ) as reponse:
            self._lire_reponse(reponse)

    @task(1)
    def quitter_la_file(self):
        if not self.billet or not self.en_file or self.dans_attraction:
            return
        # Un appelé se présente en général ; il part parfois sans venir.
        if self.appele and random.random() < 0.8:
            return

        jeton, entetes = entetes_csrf(
            self.client,
            f"{self.host}/visiteur/{self.billet}/",
        )
        with self.client.post(
            f"/visiteur/{self.billet}/",
            data={"csrfmiddlewaretoken": jeton},
            headers=entetes,
            name="/visiteur/[billet]/ (quitter)",
            catch_response=True,
        ) as reponse:
            self._lire_reponse(reponse)

    def _lire_reponse(self, reponse):
        if reponse.status_code == 404:
            reponse.failure("Billet introuvable")
            self.billet = None
            self.en_file = False
            self.appele = False
            self.dans_attraction = False
            return False
        if reponse.status_code != 200:
            reponse.failure(f"HTTP {reponse.status_code}")
            return False
        reponse.success()
        self._lire_page(reponse.text)
        return True

    def _lire_page(self, html):
        if "Bon amusement" in html:
            self.dans_attraction = True
            self.en_file = False
            self.appele = False
        elif "Tu es appelé" in html:
            self.dans_attraction = False
            self.en_file = True
            self.appele = True
        elif "Tu n'es plus dans la file" in html or "Billet expiré" in html:
            self.dans_attraction = False
            self.en_file = False
            self.appele = False
        elif "File d'attente" in html:
            self.dans_attraction = False
            self.en_file = True
            self.appele = False


class Staff(HttpUser):
    """Administre la file : appels, entrées, sorties, retraits et pause."""

    wait_time = between(1, 3)
    weight = 2

    def on_start(self):
        self.connecte = False
        self.appeles = []
        self.en_attente = []
        self.en_pause = False
        page = self.client.get("/staff/login", name="/staff/login")
        if page.status_code != 200:
            return

        jeton, entetes = entetes_csrf(
            self.client,
            f"{self.host}/staff/login",
        )
        with self.client.post(
            "/staff/login",
            data={
                "username": os.environ.get("STAFF_USERNAME", "admin"),
                "password": os.environ.get(
                    "STAFF_PASSWORD",
                    os.environ.get("ADMIN_PASSWORD", "admin"),
                ),
                "csrfmiddlewaretoken": jeton,
            },
            headers=entetes,
            name="/staff/login (connexion)",
            catch_response=True,
        ) as reponse:
            if reponse.status_code == 200 and "/login" not in reponse.url:
                reponse.success()
                self.connecte = True
            else:
                reponse.failure("Connexion staff refusée")

    @task(8)
    def tableau(self):
        if not self.connecte:
            return
        self._actualiser_file()

    @task(8)
    def attraction(self):
        """Affiche l'attraction et fait sortir ceux dont le temps est écoulé."""
        if not self.connecte:
            return
        self.client.get(
            "/staff/attraction-board/",
            name="/staff/attraction-board/ (sorties)",
        )

    @task(5)
    def faire_entrer(self):
        if not self.connecte:
            return
        self._actualiser_file()
        if not self.appeles:
            return

        identifiant = self.appeles[0]
        _unused, entetes = entetes_csrf(
            self.client,
            f"{self.host}/staff/",
        )
        with self.client.post(
            "/staff/scan/",
            json={"numero_billet": identifiant},
            headers=entetes,
            name="/staff/scan/ (entrée attraction)",
            catch_response=True,
        ) as reponse:
            if reponse.status_code in (200, 400):
                reponse.success()
            else:
                reponse.failure(f"HTTP {reponse.status_code}")

    @task(2)
    def retirer(self):
        if not self.connecte:
            return
        self._actualiser_file()
        if not self.en_attente:
            return
        self._poster(
            "/staff/remove",
            {
                "queue": FILE,
                "visitor_id": random.choice(self.en_attente),
            },
            "/staff/remove (retirer)",
        )

    @task(1)
    def basculer_pause(self):
        if not self.connecte:
            return
        self._actualiser_file()
        action = "resume" if self.en_pause else "pause"
        if self._poster(
            "/staff/pause",
            {"queue": FILE, "action": action},
            f"/staff/pause ({action})",
        ):
            self.en_pause = action == "pause"

    @task(1)
    def vider_la_file(self):
        if not self.connecte:
            return
        global _dernier_vidage
        maintenant = time.monotonic()
        with _verrou_vidage:
            if maintenant - _dernier_vidage < VIDAGE_TOUTES_LES:
                return
            _dernier_vidage = maintenant
        self._poster(
            "/staff/clear",
            {"queue": FILE},
            "/staff/clear (vider)",
        )

    def _actualiser_file(self):
        with self.client.get(
            f"/staff/?queue={FILE}",
            headers={"HX-Request": "true"},
            name="/staff/ (tableau)",
            catch_response=True,
        ) as reponse:
            if reponse.status_code != 200 or "/login" in reponse.url:
                reponse.failure("Tableau staff inaccessible")
                if "/login" in reponse.url:
                    self.connecte = False
                return
            reponse.success()
            self.appeles, self.en_attente = billets_du_tableau(reponse.text)
            self.en_pause = "En pause" in reponse.text

    def _poster(self, chemin, donnees, nom):
        jeton, entetes = entetes_csrf(
            self.client,
            f"{self.host}/staff/",
        )
        with self.client.post(
            chemin,
            data={**donnees, "csrfmiddlewaretoken": jeton},
            headers=entetes,
            name=nom,
            catch_response=True,
        ) as reponse:
            if reponse.status_code == 200 and "/login" not in reponse.url:
                reponse.success()
                return True
            reponse.failure(f"HTTP {reponse.status_code}")
            return False
