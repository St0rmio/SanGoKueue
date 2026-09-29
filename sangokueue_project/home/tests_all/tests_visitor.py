from django.test import TestCase
from django.utils import timezone

from home import queues
from home.models import Billet, EnFile
from home.tests_all.tests_queues import _FakeRedis


class TestVisitorPage(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        queues._client = _FakeRedis()

    def tearDown(self):
        queues._client = None

    def _ticket(self, number, first="Son", last="Goku", priority=Billet.Priorite.HUMAN):
        return Billet.objects.create(
            numero_de_billet=number,
            date=self.today,
            prenom=first,
            nom=last,
            priorite=priority,
        )

    def test_joins_the_queue_and_shows_the_wait(self):
        self._ticket("H1", first="Krilin", last="Brief")

        response = self.client.get("/visiteur/H1/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Krilin Brief")
        self.assertContains(response, "File d'attente")
        self.assertContains(response, "Position")
        self.assertContains(response, "0 min")
        self.assertContains(response, 'hx-trigger="every 2s"')
        self.assertNotContains(response, "Choisis ton attraction")
        self.assertTrue(
            EnFile.objects.filter(numero_de_billet_id="H1", nom_file="attraction").exists()
        )

    def test_second_visitor_waits_behind_the_first(self):
        self._ticket("H1")
        self._ticket("H2", first="Son", last="Gohan")
        self.client.get("/visiteur/H1/")

        response = self.client.get("/visiteur/H2/")

        self.assertContains(response, "Position")
        self.assertContains(response, ">2<")
        self.assertContains(response, "2 min")

    def test_opening_the_page_twice_does_not_join_again(self):
        self._ticket("H1")
        self.client.get("/visiteur/H1/")
        self.client.get("/visiteur/H1/")

        self.assertEqual(
            EnFile.objects.filter(numero_de_billet_id="H1", nom_file="attraction").count(),
            1,
        )

    def test_position_updates_when_someone_passes(self):
        self._ticket("H1", first="Krilin", last="Brief")
        self.client.get("/visiteur/H1/")
        self._ticket("SS1", first="Vegeta", last="Prince", priority=Billet.Priorite.SUPER_SAIYAN)
        self.client.get("/visiteur/SS1/")

        response = self.client.get("/visiteur/H1/", HTTP_HX_REQUEST="true")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, ">2<")
        self.assertContains(response, "2 min")
        self.assertNotContains(response, "<html")

    def test_refresh_does_not_rejoin_after_removal(self):
        self._ticket("H1")
        self.client.get("/visiteur/H1/")
        EnFile.objects.all().delete()

        response = self.client.get("/visiteur/H1/", HTTP_HX_REQUEST="true")

        self.assertContains(response, "Tu n'es plus dans la file")
        self.assertFalse(EnFile.objects.filter(numero_de_billet_id="H1").exists())

    def test_unknown_ticket_is_not_found(self):
        response = self.client.get("/visiteur/inconnu/")
        self.assertEqual(response.status_code, 404)

    def test_entry_asks_for_a_ticket(self):
        response = self.client.get("/visiteur/")
        self.assertContains(response, "Numéro de billet")
