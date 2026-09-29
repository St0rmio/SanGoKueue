from unittest.mock import patch
from django.test import TestCase
from django.utils import timezone

from home import queues
from home.models import Billet, EnFile
from home.tests_all.tests_queues import _FakeRedis
from home.views import MESSAGE_FILE_VIDEE


class TestClearQueue(TestCase):
    def setUp(self):
        self.file = "attraction"
        self.aujourdhui = timezone.localdate()
        queues._client = _FakeRedis()

        self.notification_patcher = patch("home.views.send_notification")
        self.mock_send_notification = self.notification_patcher.start()

    def tearDown(self):
        queues._client = None
        self.notification_patcher.stop()

    def _billet(self, numero):
        return Billet.objects.create(
            numero_de_billet=numero,
            date=self.aujourdhui,
            prenom="Son",
            nom="Goku",
        )

    def _entrer(self, numero, queue=None, appele=False):
        self._billet(numero)
        return EnFile.objects.create(
            numero_de_billet_id=numero,
            nom_file=self.file if queue is None else queue,
            appele=appele,
        )

    def _vider(self, queue=None):
        cible = self.file if queue is None else queue
        return self.client.delete(f"/clearQueue?queue={cible}")

    def test_vide_la_file_et_notifie_chaque_visiteur(self):
        self._entrer("H1")
        self._entrer("H2")

        response = self._vider()
        self.mock_send_notification.assert_any_call(
            "H1",
            MESSAGE_FILE_VIDEE,
        )
        self.mock_send_notification.assert_any_call(
            "H2",
            MESSAGE_FILE_VIDEE,
        )

        self.assertEqual(
            self.mock_send_notification.call_count,
            2,
        )
        self.assertEqual(response.status_code, 200)
        corps = response.json()
        self.assertEqual(corps["queue"], self.file)
        self.assertEqual(corps["removed"], 2)
        self.assertEqual(
            corps["notifications"],
            [
                {"visitorId": "H1", "message": MESSAGE_FILE_VIDEE},
                {"visitorId": "H2", "message": MESSAGE_FILE_VIDEE},
            ],
        )
        self.assertEqual(EnFile.objects.filter(nom_file=self.file).count(), 0)
        self.assertEqual(Billet.objects.filter(pk__in=["H1", "H2"]).count(), 2)

    def test_retire_aussi_les_visiteurs_deja_appeles(self):
        self._entrer("H1", appele=True)

        response = self._vider()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["removed"], 1)
        self.assertFalse(EnFile.objects.filter(nom_file=self.file).exists())

    def test_ne_touche_pas_aux_autres_files(self):
        self._entrer("H1", queue="attraction-a")
        self._entrer("H2", queue="attraction-b")

        response = self._vider("attraction-a")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["removed"], 1)
        self.assertEqual(response.json()["notifications"][0]["visitorId"], "H1")
        self.assertTrue(EnFile.objects.filter(numero_de_billet_id="H2").exists())

    def test_file_deja_vide(self):
        response = self._vider()

        self.assertEqual(response.status_code, 200)
        corps = response.json()
        self.assertEqual(corps["removed"], 0)
        self.assertEqual(corps["notifications"], [])

    def test_queue_manquante(self):
        self._entrer("H1")

        response = self.client.delete("/clearQueue")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "queue est requis.")
        self.assertEqual(EnFile.objects.filter(nom_file=self.file).count(), 1)

    def test_methode_non_autorisee(self):
        response = self.client.get("/clearQueue?queue=attraction")

        self.assertEqual(response.status_code, 405)
        self.assertEqual(EnFile.objects.count(), 0)

    def test_vide_aussi_redis(self):
        self._entrer("H1")
        queues.append_to_queue(self.file, "H1", Billet.Priorite.HUMAN)

        response = self._vider()

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(queues.pop_from_queue(self.file))
