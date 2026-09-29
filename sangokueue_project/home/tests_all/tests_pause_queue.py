import json
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from home import queues
from home.models import Billet, EnFile, EtatFile
from home.tests_all.tests_queues import _FakeRedis
from home.views import ATTENTE_PRIORITE_SAIYAN, DELAI_PRESENTATION


class _Horloge:
    def __init__(self):
        self.maintenant = timezone.now().replace(
            hour=12, minute=0, second=0, microsecond=0,
        )

    def now(self):
        return self.maintenant

    def avancer(self, secondes):
        self.maintenant += timedelta(seconds=secondes)


class TestPauseQueue(TestCase):
    def setUp(self):
        self.file = "attraction"
        self.aujourdhui = timezone.localdate()
        queues._client = _FakeRedis()
        self.notification_patcher = patch("home.views.send_notification")
        self.mock_send_notification = self.notification_patcher.start()

    def tearDown(self):
        queues._client = None
        self.notification_patcher.stop()

    def _billet(self, numero, priorite=Billet.Priorite.HUMAN):
        return Billet.objects.create(
            numero_de_billet=numero,
            date=self.aujourdhui,
            prenom="Son",
            nom="Goku",
            priorite=priorite,
        )

    def _entrer(self, numero, queue=None, priorite=Billet.Priorite.HUMAN):
        self._billet(numero, priorite)
        return EnFile.objects.create(
            numero_de_billet_id=numero,
            nom_file=self.file if queue is None else queue,
        )

    def _pause(self, paused, queue=None, brut=None):
        if brut is None:
            brut = json.dumps({
                "queue": self.file if queue is None else queue,
                "paused": paused,
            })
        return self.client.patch(
            "/pauseQueue",
            data=brut,
            content_type="application/json",
        )

    def _par_visiteur(self, response):
        return {
            notification["visitorId"]: notification
            for notification in response.json()["notifications"]
        }

    def test_met_en_pause_et_notifie_avec_la_position(self):
        self._entrer("H1")
        self._entrer("SS1", priorite=Billet.Priorite.SUPER_SAIYAN)

        response = self._pause(True)
        self.mock_send_notification.assert_any_call(
            "SS1",
            "La file est en pause. Position 1. Temps estimé : 0 min.",
        )
        self.mock_send_notification.assert_any_call(
            "H1",
            "La file est en pause. Position 2. Temps estimé : 2 min.",
        )

        self.assertEqual(
            self.mock_send_notification.call_count,
            2,
        )
        self.assertEqual(response.status_code, 200)
        corps = response.json()
        self.assertEqual(corps["queue"], self.file)
        self.assertTrue(corps["paused"])
        notifications = self._par_visiteur(response)
        self.assertEqual(notifications["SS1"]["position"], 1)
        self.assertEqual(notifications["SS1"]["estimatedWaitSeconds"], 0)
        self.assertEqual(
            notifications["SS1"]["message"],
            "La file est en pause. Position 1. Temps estimé : 0 min.",
        )
        self.assertEqual(notifications["H1"]["position"], 2)
        self.assertTrue(EtatFile.objects.get(nom_file=self.file).en_pause)

    def test_reprend_la_file(self):
        self._entrer("H1")
        self._pause(True)
        self.mock_send_notification.reset_mock()
        response = self._pause(False)
        self.mock_send_notification.assert_called_once_with(
            "H1",
            "La file a repris. Position 1. Temps estimé : 0 min.",
        )
        self.assertEqual(response.status_code, 200)
        corps = response.json()
        self.assertFalse(corps["paused"])
        self.assertEqual(
            corps["notifications"][0]["message"],
            "La file a repris. Position 1. Temps estimé : 0 min.",
        )
        etat = EtatFile.objects.get(nom_file=self.file)
        self.assertFalse(etat.en_pause)
        self.assertIsNone(etat.mise_en_pause_le)

    def test_file_vide(self):
        response = self._pause(True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["notifications"], [])
        self.assertTrue(EtatFile.objects.get(nom_file=self.file).en_pause)

    def test_ne_pause_pas_les_autres_files(self):
        self._entrer("H1", queue="attraction-a")
        self._entrer("H2", queue="attraction-b")

        response = self._pause(True, queue="attraction-a")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["visitorId"] for item in response.json()["notifications"]],
            ["H1"],
        )
        self.assertTrue(EtatFile.objects.get(nom_file="attraction-a").en_pause)
        self.assertFalse(EtatFile.objects.filter(nom_file="attraction-b").exists())

    def test_vider_la_file_laisse_la_pause(self):
        self._entrer("H1")
        self._pause(True)

        self.client.delete(f"/clearQueue?queue={self.file}")

        self.assertFalse(EnFile.objects.filter(nom_file=self.file).exists())
        self.assertTrue(EtatFile.objects.get(nom_file=self.file).en_pause)

    def test_corps_invalide(self):
        response = self._pause(None, brut="{")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Corps JSON invalide.")

    def test_paused_manquant(self):
        response = self._pause(None, brut=json.dumps({"queue": self.file}))

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "paused est requis.")
        self.assertFalse(EtatFile.objects.filter(nom_file=self.file).exists())

    def test_methode_non_autorisee(self):
        response = self.client.get("/pauseQueue")

        self.assertEqual(response.status_code, 405)

    def test_met_aussi_redis_en_pause(self):
        self._entrer("H1")

        response = self._pause(True)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(queues.is_paused(self.file))

        self._pause(False)

        self.assertFalse(queues.is_paused(self.file))


class TestPauseQueueHorloge(TestCase):
    def setUp(self):
        self.file = "attraction"
        self.horloge = _Horloge()
        self.time_patcher = patch("django.utils.timezone.now", self.horloge.now)
        self.time_patcher.start()
        queues._client = _FakeRedis()

    def tearDown(self):
        self.time_patcher.stop()
        queues._client = None

    def _entrer(self, numero, priorite=Billet.Priorite.HUMAN, appele=False, date_appel=None):
        Billet.objects.create(
            numero_de_billet=numero,
            date=timezone.localdate(),
            prenom="Son",
            nom="Goku",
            priorite=priorite,
        )
        return EnFile.objects.create(
            numero_de_billet_id=numero,
            nom_file=self.file,
            appele=appele,
            date_appel=date_appel,
        )

    def _pause(self, paused):
        return self.client.patch(
            "/pauseQueue",
            data=json.dumps({"queue": self.file, "paused": paused}),
            content_type="application/json",
        )

    def _par_visiteur(self, response):
        return {
            notification["visitorId"]: notification
            for notification in response.json()["notifications"]
        }

    def test_une_seconde_pause_ne_decale_pas_l_horloge(self):
        self._entrer("H1")
        self._pause(True)
        debut = EtatFile.objects.get(nom_file=self.file).mise_en_pause_le
        self.horloge.avancer(300)

        self._pause(True)

        self.assertEqual(
            EtatFile.objects.get(nom_file=self.file).mise_en_pause_le,
            debut,
        )

    def test_la_pause_ne_fait_pas_passer_le_saiyan(self):
        self._entrer("H1")
        self.horloge.avancer(60)
        self._entrer("S1", priorite=Billet.Priorite.SAIYAN)
        self.horloge.avancer(ATTENTE_PRIORITE_SAIYAN - 60)
        self._pause(True)
        self.horloge.avancer(10 * 60)

        response = self._pause(True)

        notifications = self._par_visiteur(response)
        self.assertEqual(notifications["H1"]["position"], 1)
        self.assertEqual(notifications["S1"]["position"], 2)

    def test_le_delai_saiyan_reprend_apres_la_pause(self):
        self._entrer("H1")
        self.horloge.avancer(60)
        self._entrer("S1", priorite=Billet.Priorite.SAIYAN)
        self.horloge.avancer(ATTENTE_PRIORITE_SAIYAN - 60)
        self._pause(True)
        self.horloge.avancer(10 * 60)
        self._pause(False)
        self.horloge.avancer(2 * 60)

        response = self._pause(True)

        notifications = self._par_visiteur(response)
        self.assertEqual(notifications["S1"]["position"], 1)
        self.assertEqual(notifications["H1"]["position"], 2)
        self.assertEqual(
            EnFile.objects.get(numero_de_billet_id="S1").secondes_pause,
            10 * 60,
        )

    def test_le_delai_de_presentation_est_fige_pendant_la_pause(self):
        maintenant = self.horloge.now()
        self._entrer(
            "H1",
            appele=True,
            date_appel=maintenant - timedelta(seconds=DELAI_PRESENTATION - 60),
        )
        self._pause(True)
        self.horloge.avancer(5 * 60)

        en_pause = self._par_visiteur(self._pause(True))["H1"]

        self.assertEqual(en_pause["remainingCallSeconds"], 60)
        self.assertIsNone(en_pause["position"])
        self.assertEqual(
            en_pause["message"],
            "La file est en pause. Il vous reste 1 min pour vous présenter.",
        )

        self._pause(False)
        self.horloge.avancer(30)
        repris = self._par_visiteur(self._pause(True))["H1"]

        self.assertEqual(repris["remainingCallSeconds"], 30)

    def test_un_arrive_pendant_la_pause_ne_compte_pas_ce_temps(self):
        self._pause(True)
        self.horloge.avancer(30)
        self._entrer("H1")
        self.horloge.avancer(30)
        self._pause(False)

        entree = EnFile.objects.get(numero_de_billet_id="H1")
        self.assertEqual(entree.secondes_pause, 30)
