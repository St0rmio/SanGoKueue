import json
import time
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from home import queues
from home.models import Billet, EnFile
from home.tests_all.tests_queues import _FakeRedis
from home.views import TEMPS_MOYEN_PAR_PERSONNE


class TestAppendToQueue(TestCase):
    def setUp(self):
        self.file = "attraction"
        self.aujourdhui = timezone.localdate()
        queues._client = _FakeRedis()

    def tearDown(self):
        queues._client = None

    def _billet(self, numero, priorite=Billet.Priorite.HUMAN, jour=None):
        return Billet.objects.create(
            numero_de_billet=numero,
            date=self.aujourdhui if jour is None else jour,
            prenom="Son",
            nom="Goku",
            priorite=priorite,
        )

    def _rejoindre(self, visitor_id, queue=None, brut=None):
        if brut is None:
            brut = json.dumps({
                "visitorId": visitor_id,
                "queue": self.file if queue is None else queue,
            })

        return self.client.post(
            "/appendToQueue",
            data=brut,
            content_type="application/json",
        )

    def test_billet_authentifie_rejoint_une_file_vide(self):
        self._billet("H1")

        response = self._rejoindre("H1")

        self.assertEqual(response.status_code, 201)

        corps = response.json()

        self.assertEqual(corps["visitorId"], "H1")
        self.assertEqual(corps["queue"], self.file)
        self.assertEqual(corps["position"], 1)
        self.assertEqual(corps["estimatedWaitSeconds"], 0)

        self.assertEqual(
            corps["notification"],
            "Vous avez rejoint la file. Position 1. Temps estimé : 0 min.",
        )

        entree = EnFile.objects.get(
            numero_de_billet_id="H1"
        )

        self.assertEqual(
            entree.nom_file,
            self.file,
        )
        self.assertFalse(entree.appele)
        self.assertFalse(entree.deja_appele)

    def test_temps_estime_compte_les_personnes_devant(self):
        self._billet("H1")
        self._billet("H2")

        self._rejoindre("H1")

        response = self._rejoindre("H2")

        self.assertEqual(
            response.status_code,
            201,
        )

        corps = response.json()

        self.assertEqual(
            corps["position"],
            2,
        )

        self.assertEqual(
            corps["estimatedWaitSeconds"],
            TEMPS_MOYEN_PAR_PERSONNE,
        )

        self.assertIn(
            "Position 2",
            corps["notification"],
        )

        self.assertIn(
            "moins d'une minute",
            corps["notification"],
        )

    def test_super_saiyan_passe_devant_les_autres(self):
        self._billet("H1")
        self._billet(
            "S1",
            Billet.Priorite.SAIYAN,
        )
        self._billet(
            "SS1",
            Billet.Priorite.SUPER_SAIYAN,
        )

        self._rejoindre("H1")
        self._rejoindre("S1")

        response = self._rejoindre("SS1")

        self.assertEqual(
            response.status_code,
            201,
        )

        corps = response.json()

        self.assertEqual(
            corps["position"],
            1,
        )

        self.assertEqual(
            corps["estimatedWaitSeconds"],
            0,
        )

    def test_super_saiyan_attend_les_super_saiyan_deja_presents(self):
        self._billet(
            "SS1",
            Billet.Priorite.SUPER_SAIYAN,
        )
        self._billet("H1")
        self._billet(
            "SS2",
            Billet.Priorite.SUPER_SAIYAN,
        )

        self._rejoindre("SS1")
        self._rejoindre("H1")

        response = self._rejoindre("SS2")

        self.assertEqual(
            response.status_code,
            201,
        )

        corps = response.json()

        self.assertEqual(
            corps["position"],
            2,
        )

        self.assertEqual(
            corps["estimatedWaitSeconds"],
            TEMPS_MOYEN_PAR_PERSONNE,
        )

    def test_saiyan_qui_vient_d_entrer_reste_derriere(self):
        self._billet("H1")
        self._billet(
            "S1",
            Billet.Priorite.SAIYAN,
        )

        self._rejoindre("H1")

        response = self._rejoindre("S1")

        self.assertEqual(
            response.status_code,
            201,
        )
        
        time.sleep(0.05)
        self.assertEqual(
            response.json()["position"],
            2,
        )

    def test_les_files_sont_independantes(self):
        self._billet("H1")

        self._rejoindre(
            "H1",
            queue="attraction-a",
        )

        self._billet("H2")

        response = self._rejoindre(
            "H2",
            queue="attraction-b",
        )

        self.assertEqual(
            response.status_code,
            201,
        )

        self.assertEqual(
            response.json()["position"],
            1,
        )

        self.assertEqual(
            response.json()["queue"],
            "attraction-b",
        )

    def test_meme_billet_peut_rejoindre_une_autre_file(self):
        self._billet("H1")

        self._rejoindre(
            "H1",
            queue="attraction-a",
        )

        response = self._rejoindre(
            "H1",
            queue="attraction-b",
        )

        self.assertEqual(
            response.status_code,
            201,
        )

        self.assertEqual(
            EnFile.objects.filter(
                numero_de_billet_id="H1"
            ).count(),
            2,
        )

    def test_billet_deja_dans_la_file(self):
        self._billet("H1")
        self._rejoindre("H1")

        response = self._rejoindre("H1")

        self.assertEqual(
            response.status_code,
            409,
        )

        self.assertEqual(
            response.json()["error"],
            "Ce billet est déjà dans la file.",
        )

        self.assertEqual(
            EnFile.objects.filter(
                numero_de_billet_id="H1"
            ).count(),
            1,
        )

    def test_billet_inconnu(self):
        response = self._rejoindre(
            "INCONNU"
        )

        self.assertEqual(
            response.status_code,
            404,
        )

        self.assertEqual(
            response.json()["error"],
            "Billet introuvable.",
        )

        self.assertEqual(
            EnFile.objects.count(),
            0,
        )

    def test_billet_expire(self):
        self._billet(
            "H1",
            jour=self.aujourdhui
            - timedelta(days=1),
        )

        response = self._rejoindre("H1")

        self.assertEqual(
            response.status_code,
            400,
        )

        self.assertEqual(
            response.json()["error"],
            "Billet expiré.",
        )

        self.assertEqual(
            EnFile.objects.count(),
            0,
        )

    def test_billet_valide_dans_le_futur(self):
        self._billet(
            "H1",
            jour=self.aujourdhui
            + timedelta(days=3),
        )

        response = self._rejoindre("H1")

        self.assertEqual(
            response.status_code,
            201,
        )

    def test_corps_invalide(self):
        response = self._rejoindre(
            None,
            brut="{",
        )

        self.assertEqual(
            response.status_code,
            400,
        )

        self.assertEqual(
            response.json()["error"],
            "Corps JSON invalide.",
        )

    def test_visitor_id_manquant(self):
        response = self._rejoindre(
            None,
            brut=json.dumps({
                "queue": self.file,
            }),
        )

        self.assertEqual(
            response.status_code,
            400,
        )

        self.assertEqual(
            response.json()["error"],
            "visitorId est requis.",
        )

    def test_queue_manquante(self):
        self._billet("H1")

        response = self._rejoindre(
            None,
            brut=json.dumps({
                "visitorId": "H1",
            }),
        )

        self.assertEqual(
            response.status_code,
            400,
        )

        self.assertEqual(
            response.json()["error"],
            "queue est requis.",
        )

        self.assertEqual(
            EnFile.objects.count(),
            0,
        )

    def test_methode_non_autorisee(self):
        response = self.client.get(
            "/appendToQueue"
        )

        self.assertEqual(
            response.status_code,
            405,
        )

    def test_inscrit_aussi_dans_redis(self):
        self._billet("H1")

        response = self._rejoindre("H1")

        self.assertEqual(
            response.status_code,
            201,
        )

        self.assertEqual(
            queues.pop_from_queue(
                self.file
            ),
            "H1",
        )