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

    def _ticket(
        self,
        number,
        first="Son",
        last="Goku",
        priority=Billet.Priorite.HUMAN,
    ):
        return Billet.objects.create(
            numero_de_billet=number,
            date=self.today,
            prenom=first,
            nom=last,
            priorite=priority,
        )

    def test_joins_the_queue_and_shows_the_wait(self):
        self._ticket(
            "H1",
            first="Krilin",
            last="Brief",
        )

        response = self.client.get("/visiteur/H1/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Krilin Brief")
        self.assertContains(response, "File d'attente")
        self.assertContains(response, "Position")
        self.assertContains(response, "0 min")
        self.assertContains(response, 'hx-trigger="every 2s"')
        self.assertNotContains(response, "Choisis ton attraction")

        self.assertTrue(
            EnFile.objects.filter(
                numero_de_billet_id="H1",
                nom_file="attraction",
            ).exists()
        )

    def test_second_visitor_waits_behind_the_first(self):
        self._ticket("H1")

        self._ticket(
            "H2",
            first="Son",
            last="Gohan",
        )

        self.client.get("/visiteur/H1/")

        response = self.client.get("/visiteur/H2/")

        self.assertContains(response, "Position")
        self.assertContains(response, ">2<")
        self.assertContains(
            response,
            "moins d&#x27;une minute",
        )

    def test_opening_the_page_twice_does_not_join_again(self):
        self._ticket("H1")

        self.client.get("/visiteur/H1/")
        self.client.get("/visiteur/H1/")

        self.assertEqual(
            EnFile.objects.filter(
                numero_de_billet_id="H1",
                nom_file="attraction",
            ).count(),
            1,
        )

    def test_position_updates_when_someone_passes(self):
        self._ticket(
            "H1",
            first="Krilin",
            last="Brief",
        )

        self.client.get("/visiteur/H1/")

        self._ticket(
            "SS1",
            first="Vegeta",
            last="Prince",
            priority=Billet.Priorite.SUPER_SAIYAN,
        )

        self.client.get("/visiteur/SS1/")

        response = self.client.get(
            "/visiteur/H1/",
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, ">2<")
        self.assertContains(
            response,
            "moins d&#x27;une minute",
        )
        self.assertNotContains(response, "<html")

    def test_refresh_does_not_rejoin_after_removal(self):
        self._ticket("H1")

        self.client.get("/visiteur/H1/")

        EnFile.objects.all().delete()

        response = self.client.get(
            "/visiteur/H1/",
            HTTP_HX_REQUEST="true",
        )

        self.assertContains(
            response,
            "Tu n'es plus dans la file",
        )

        self.assertContains(
            response,
            'data-redirect="/home/"',
        )

        self.assertNotContains(
            response,
            'hx-trigger="every 2s"',
        )

        self.assertFalse(
            EnFile.objects.filter(
                numero_de_billet_id="H1"
            ).exists()
        )

    def test_unknown_ticket_is_not_found(self):
        response = self.client.get(
            "/visiteur/inconnu/"
        )

        self.assertEqual(
            response.status_code,
            404,
        )

    def test_entry_asks_for_a_ticket(self):
        response = self.client.get(
            "/visiteur/"
        )

        self.assertContains(
            response,
            "Numéro de billet",
        )

    def test_home_form_opens_the_visitor_page(self):
        self._ticket("H1")

        page = self.client.get(
            "/home/"
        )

        self.assertContains(
            page,
            'action="/visiteur/"',
        )

        self.assertContains(
            page,
            'name="billet"',
        )

        response = self.client.get(
            "/visiteur/",
            {
                "billet": "H1"
            },
        )

        self.assertContains(
            response,
            "Son Goku",
        )

        self.assertContains(
            response,
            "File d'attente",
        )

        self.assertTrue(
            EnFile.objects.filter(
                numero_de_billet_id="H1",
                nom_file="attraction",
            ).exists()
        )

    def test_page_offers_to_leave_the_queue(self):
        self._ticket("H1")

        response = self.client.get(
            "/visiteur/H1/"
        )

        self.assertContains(
            response,
            "Quitter la file",
        )

        self.assertContains(
            response,
            "planifierRetourAccueil",
        )

    def test_leaving_removes_the_visitor(self):
        self._ticket("H1")

        self.client.get("/visiteur/H1/")

        response = self.client.post(
            "/visiteur/H1/",
            HTTP_HX_REQUEST="true",
        )

        self.assertContains(
            response,
            "Tu n'es plus dans la file",
        )

        self.assertContains(
            response,
            'data-redirect="/home/"',
        )

        self.assertContains(
            response,
            "Retour à l'accueil...",
        )

        self.assertNotContains(
            response,
            'hx-trigger="every 2s"',
        )

        self.assertNotContains(
            response,
            "Quitter la file",
        )

        self.assertFalse(
            EnFile.objects.filter(
                numero_de_billet_id="H1",
                nom_file="attraction",
            ).exists()
        )

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User

from home.models import VisiteurEnAttraction
from home.views import CAPACITE_MAX, DELAI_PRESENTATION, appeler_suivants


class TestAppelSelonPlaces(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        queues._client = _FakeRedis()
        self.notification = patch("home.views.send_notification")
        self.notification.start()
        self.push = patch("home.views.send_push_notification")
        self.push.start()

    def tearDown(self):
        queues._client = None
        self.notification.stop()
        self.push.stop()

    def _ticket(self, number, first="Son", last="Goku"):
        return Billet.objects.create(
            numero_de_billet=number,
            date=self.today,
            prenom=first,
            nom=last,
        )

    def test_affiche_tu_es_appele(self):
        self._ticket("H1")
        self.client.get("/visiteur/H1/")
        appeler_suivants("attraction", nombre=1)

        response = self.client.get("/visiteur/H1/", HTTP_HX_REQUEST="true")

        self.assertContains(response, "Tu es appelé")
        self.assertContains(
            response,
            "Vous êtes appelés, veuillez vous rendre dans les 5 mins",
        )
        self.assertContains(response, "Temps restant")
        self.assertContains(response, "5 min")

    def test_appelle_selon_places_disponibles(self):
        for i in range(3):
            self._ticket(f"H{i}")
            self.client.get(f"/visiteur/H{i}/")
        for i in range(CAPACITE_MAX - 2):
            b = Billet.objects.create(
                numero_de_billet=f"X{i}",
                date=self.today,
                prenom="X",
                nom="Y",
            )
            VisiteurEnAttraction.objects.create(
                billet=b,
                heure_sortie_prevue=timezone.now() + timedelta(minutes=5),
            )

        appeles = appeler_suivants("attraction")
        self.assertEqual(len(appeles), 2)
        self.assertEqual(EnFile.objects.filter(appele=True).count(), 2)

    def test_staff_board_appelle_automatiquement(self):
        User.objects.create_user("trunks", password="capsule")
        self.client.login(username="trunks", password="capsule")
        self._ticket("H1")
        self.client.get("/visiteur/H1/")

        page = self.client.get("/staff/")

        self.assertEqual(page.status_code, 200)
        entree = EnFile.objects.get(numero_de_billet_id="H1")
        self.assertTrue(entree.appele)
        self.assertIsNotNone(entree.date_appel)

        visitor = self.client.get("/visiteur/H1/", HTTP_HX_REQUEST="true")
        self.assertContains(visitor, "Tu es appelé")

    def test_sans_validation_il_repart_en_fin_de_file(self):
        debut = timezone.now()
        with patch("django.utils.timezone.now", return_value=debut):
            self._ticket("H1", first="Krilin", last="Brief")
            self._ticket("H2", first="Son", last="Gohan")
            self.client.get("/visiteur/H1/")
            self.client.get("/visiteur/H2/")
            entree = EnFile.objects.get(numero_de_billet_id="H1")
            entree.appele = True
            entree.date_appel = debut
            entree.save()

        plus_tard = debut + timedelta(seconds=DELAI_PRESENTATION + 1)
        with patch("django.utils.timezone.now", return_value=plus_tard):
            response = self.client.get("/visiteur/H1/", HTTP_HX_REQUEST="true")

        self.assertContains(response, "Vous repartez en fin de file")
        self.assertContains(response, ">2<")
        h1 = EnFile.objects.get(numero_de_billet_id="H1")
        h2 = EnFile.objects.get(numero_de_billet_id="H2")
        self.assertFalse(h1.appele)
        self.assertGreater(h1.date_entree, h2.date_entree)

    def test_validation_staff_dans_les_cinq_minutes(self):
        User.objects.create_user("trunks", password="capsule")
        self.client.login(username="trunks", password="capsule")
        self._ticket("H1")
        self._ticket("H2")
        self.client.get("/visiteur/H1/")
        self.client.get("/visiteur/H2/")
        appeler_suivants("attraction", nombre=1)

        response = self.client.post(
            "/staff/scan/",
            data='{"numero_billet": "H1"}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(EnFile.objects.filter(numero_de_billet_id="H1").exists())
        self.assertTrue(VisiteurEnAttraction.objects.filter(billet_id="H1").exists())

        page = self.client.get("/visiteur/H1/", HTTP_HX_REQUEST="true")
        self.assertContains(page, "C'est validé")
        self.assertContains(page, "Bon amusement dans l'attraction.")
