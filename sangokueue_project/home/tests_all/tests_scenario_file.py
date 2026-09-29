import json
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from home import queues
from home.models import Billet, EnFile, EtatFile
from home.tests_all.tests_pause_queue import _Horloge
from home.tests_all.tests_queues import _FakeRedis
from home.views import ATTENTE_PRIORITE_SAIYAN, MESSAGE_FILE_VIDEE, TEMPS_MOYEN_PAR_PERSONNE


class TestScenarioFile(TestCase):
    """Dix visiteurs, priorités, limite Saiyan, pause, reprise, puis vidage."""

    def setUp(self):
        self.file = "attraction"
        self.horloge = _Horloge()
        self.time_patcher = patch("django.utils.timezone.now", self.horloge.now)
        self.time_patcher.start()
        queues._client = _FakeRedis()
        self.visiteurs = [
            ("H1", Billet.Priorite.HUMAN),
            ("S1", Billet.Priorite.SAIYAN),
            ("H2", Billet.Priorite.HUMAN),
            ("SS1", Billet.Priorite.SUPER_SAIYAN),
            ("S2", Billet.Priorite.SAIYAN),
            ("H3", Billet.Priorite.HUMAN),
            ("SS2", Billet.Priorite.SUPER_SAIYAN),
            ("S3", Billet.Priorite.SAIYAN),
            ("H4", Billet.Priorite.HUMAN),
            ("SS3", Billet.Priorite.SUPER_SAIYAN),
        ]

    def tearDown(self):
        self.time_patcher.stop()
        queues._client = None

    def _rejoindre(self, numero, priorite):
        Billet.objects.create(
            numero_de_billet=numero,
            date=timezone.localdate(),
            prenom="Son",
            nom="Goku",
            priorite=priorite,
        )
        return self.client.post(
            "/appendToQueue",
            data=json.dumps({"visitorId": numero, "queue": self.file}),
            content_type="application/json",
        )

    def _pause(self, paused):
        return self.client.patch(
            "/pauseQueue",
            data=json.dumps({"queue": self.file, "paused": paused}),
            content_type="application/json",
        )

    def _ordre(self, response):
        return [note["visitorId"] for note in response.json()["notifications"]]

    def _attente(self, numero):
        entree = EnFile.objects.get(numero_de_billet_id=numero)
        return (
            int((self.horloge.now() - entree.date_entree).total_seconds())
            - entree.secondes_pause
        )

    def test_dix_visiteurs_priorites_pause_reprise_et_vidage(self):
        for index, (numero, priorite) in enumerate(self.visiteurs):
            if index:
                self.horloge.avancer(60)
            reponse = self._rejoindre(numero, priorite)
            self.assertEqual(reponse.status_code, 201)

        self.assertEqual(EnFile.objects.filter(nom_file=self.file).count(), 10)
        self.assertLess(self._attente("S1"), ATTENTE_PRIORITE_SAIYAN)

        # Avant 25 min : Super Saiyan d'abord, puis l'arrivée la plus ancienne.
        ordre_initial = ["SS1", "SS2", "SS3", "H1", "S1", "H2", "S2", "H3", "S3", "H4"]
        mise_en_pause = self._pause(True)
        self.assertEqual(mise_en_pause.status_code, 200)
        self.assertTrue(mise_en_pause.json()["paused"])
        self.assertEqual(self._ordre(mise_en_pause), ordre_initial)
        for note in mise_en_pause.json()["notifications"]:
            self.assertEqual(
                note["estimatedWaitSeconds"],
                (note["position"] - 1) * TEMPS_MOYEN_PAR_PERSONNE,
            )
            self.assertIn("La file est en pause.", note["message"])

        # Le temps mural dépasse 25 min, mais l'ordre reste figé.
        self.horloge.avancer(30 * 60)
        attente_murale_s1 = int(
            (self.horloge.now() - EnFile.objects.get(numero_de_billet_id="S1").date_entree).total_seconds()
        )
        self.assertGreater(attente_murale_s1, ATTENTE_PRIORITE_SAIYAN)
        toujours_en_pause = self._pause(True)
        self.assertEqual(self._ordre(toujours_en_pause), ordre_initial)

        # La reprise reconstruit le même ordre, et le délai Saiyan reprend.
        reprise = self._pause(False)
        self.assertFalse(reprise.json()["paused"])
        self.assertEqual(self._ordre(reprise), ordre_initial)
        for note in reprise.json()["notifications"]:
            self.assertIn("La file a repris.", note["message"])
        for numero, _priorite in self.visiteurs:
            self.assertEqual(
                EnFile.objects.get(numero_de_billet_id=numero).secondes_pause,
                30 * 60,
            )

        attente_s1 = self._attente("S1")
        self.horloge.avancer(ATTENTE_PRIORITE_SAIYAN - attente_s1 + 1)
        self.assertGreater(self._attente("S1"), ATTENTE_PRIORITE_SAIYAN)
        self.assertLess(self._attente("S2"), ATTENTE_PRIORITE_SAIYAN)

        # S1 passe devant H1. Les Super Saiyan restent devant lui.
        ordre_apres_limite = ["SS1", "SS2", "SS3", "S1", "H1", "H2", "S2", "H3", "S3", "H4"]
        apres_limite = self._pause(True)
        self.assertEqual(self._ordre(apres_limite), ordre_apres_limite)
        self.assertEqual(
            [note["position"] for note in apres_limite.json()["notifications"]],
            list(range(1, 11)),
        )

        vidage = self.client.delete(f"/clearQueue?queue={self.file}")
        self.assertEqual(vidage.status_code, 200)
        corps = vidage.json()
        self.assertEqual(corps["removed"], 10)
        self.assertEqual(
            [note["visitorId"] for note in corps["notifications"]],
            ["H1", "S1", "H2", "SS1", "S2", "H3", "SS2", "S3", "H4", "SS3"],
        )
        self.assertTrue(all(note["message"] == MESSAGE_FILE_VIDEE for note in corps["notifications"]))
        self.assertEqual(EnFile.objects.filter(nom_file=self.file).count(), 0)
        self.assertEqual(Billet.objects.count(), 10)
        self.assertTrue(EtatFile.objects.get(nom_file=self.file).en_pause)
