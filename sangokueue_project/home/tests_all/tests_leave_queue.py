from django.test import TestCase
from django.utils import timezone

from home.models import Billet, EnFile


class TestLeaveQueue(TestCase):
    def setUp(self):
        self.file = "attraction"
        self.aujourdhui = timezone.localdate()

    def _billet(self, numero):
        return Billet.objects.create(
            numero_de_billet=numero,
            date=self.aujourdhui,
            prenom="Son",
            nom="Goku",
        )

    def _entrer(self, numero, queue=None):
        self._billet(numero)
        return EnFile.objects.create(
            numero_de_billet_id=numero,
            nom_file=self.file if queue is None else queue,
        )

    def _quitter(self, visitor_id, queue=None):
        cible = self.file if queue is None else queue
        return self.client.delete(
            f"/leaveQueue?visitorId={visitor_id}&queue={cible}"
        )

    def test_un_participant_peut_quitter_la_file(self):
        self._entrer("H1")

        response = self._quitter("H1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "visitorId": "H1",
            "queue": self.file,
            "left": True,
        })
        self.assertFalse(
            EnFile.objects.filter(
                numero_de_billet_id="H1",
                nom_file=self.file,
            ).exists()
        )

    def test_le_billet_n_est_pas_supprime(self):
        self._entrer("H1")

        self._quitter("H1")

        self.assertTrue(Billet.objects.filter(pk="H1").exists())

    def test_ne_quitte_pas_une_autre_file(self):
        self._billet("H1")
        EnFile.objects.create(
            numero_de_billet_id="H1",
            nom_file="attraction-a",
        )
        EnFile.objects.create(
            numero_de_billet_id="H1",
            nom_file="attraction-b",
        )

        response = self._quitter("H1", queue="attraction-a")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            EnFile.objects.filter(
                numero_de_billet_id="H1",
                nom_file="attraction-a",
            ).exists()
        )
        self.assertTrue(
            EnFile.objects.filter(
                numero_de_billet_id="H1",
                nom_file="attraction-b",
            ).exists()
        )

    def test_billet_pas_dans_la_file(self):
        self._billet("H1")

        response = self._quitter("H1")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json()["error"],
            "Ce billet n'est pas dans la file.",
        )

    def test_visitor_id_manquant(self):
        response = self.client.delete(
            "/leaveQueue?queue=attraction"
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["error"],
            "visitorId est requis.",
        )

    def test_queue_manquante(self):
        response = self.client.delete(
            "/leaveQueue?visitorId=H1"
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["error"],
            "queue est requis.",
        )

    def test_methode_non_autorisee(self):
        response = self.client.get(
            "/leaveQueue?visitorId=H1&queue=attraction"
        )

        self.assertEqual(response.status_code, 405)