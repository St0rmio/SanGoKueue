from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.models import User

from datetime import timedelta, date
from unittest.mock import patch

from home import queues
from home.models import Billet, EnFile, VisiteurEnAttraction
from home.tests_all.tests_queues import _FakeRedis
from home.tests_all.tests_append_to_queue import TestAppendToQueue
from home.tests_all.tests_clear_queue import TestClearQueue
from home.tests_all.tests_leave_queue import TestLeaveQueue
from home.tests_all.tests_notifications import NotificationWebSocketTests
from home.tests_all.tests_pause_queue import TestPauseQueue, TestPauseQueueHorloge
from home.tests_all.tests_peupler_billets import (
    TestDemarrageProduction,
    TestJeuDeBillets,
    TestReessaiConnexion,
)
from home.tests_all.tests_qr_code import TestBillets
from home.tests_all.tests_queues import TestQueues
from home.tests_all.tests_scenario_file import TestScenarioFile
from home.tests_all.tests_visitor import TestVisitorPage, TestAppelSelonPlaces
from home.views import CAPACITE_MAX, appeler_suivants

__all__ = [
    "AffluenceAttractionTests",
    "NotificationWebSocketTests",
    "TestAppendToQueue",
    "TestAppelSelonPlaces",
    "TestBillets",
    "TestClearQueue",
    "TestDemarrageProduction",
    "TestJeuDeBillets",
    "TestLeaveQueue",
    "TestPauseQueue",
    "TestPauseQueueHorloge",
    "TestQueues",
    "TestReessaiConnexion",
    "TestScenarioFile",
    "TestVisitorPage",
]


class AffluenceAttractionTests(TestCase):
    def setUp(self):
        queues._client = _FakeRedis()
        self.notification = patch("home.views.send_notification")
        self.notification.start()
        self.push = patch("home.views.send_push_notification")
        self.push.start()

        b1 = Billet.objects.create(
            numero_de_billet="B1", date=date.today(), prenom="Jean", nom="A"
        )
        b2 = Billet.objects.create(
            numero_de_billet="B2", date=date.today(), prenom="Marie", nom="B"
        )
        b3 = Billet.objects.create(
            numero_de_billet="B3", date=date.today(), prenom="Luc", nom="C"
        )
        self.billet_1 = EnFile.objects.create(
            numero_de_billet=b1, nom_file="attraction", appele=False
        )
        self.billet_2 = EnFile.objects.create(
            numero_de_billet=b2, nom_file="attraction", appele=False
        )
        self.billet_3 = EnFile.objects.create(
            numero_de_billet=b3, nom_file="attraction", appele=False
        )
        queues.append_to_queue("attraction", "B1", Billet.Priorite.HUMAN)
        queues.append_to_queue("attraction", "B2", Billet.Priorite.HUMAN)
        queues.append_to_queue("attraction", "B3", Billet.Priorite.HUMAN)
        self.url_scan = reverse("staff:scan_billet")
        self.staff_user = User.objects.create_superuser(
            "staff_test", "staff@test.com", "password"
        )
        self.client.force_login(self.staff_user)

    def tearDown(self):
        queues._client = None
        self.notification.stop()
        self.push.stop()

    @patch("home.views.random.randint")
    def test_scan_billet_succes(self, mock_randint):
        mock_randint.return_value = 60
        appeler_suivants("attraction", nombre=1)

        response = self.client.post(
            self.url_scan,
            data='{"numero_billet": "B1"}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(VisiteurEnAttraction.objects.count(), 1)
        visiteur = VisiteurEnAttraction.objects.first()
        self.assertEqual(visiteur.billet_id, "B1")
        diff = visiteur.heure_sortie_prevue - visiteur.heure_entree
        self.assertAlmostEqual(diff.total_seconds(), 60, delta=1)
        self.assertFalse(EnFile.objects.filter(numero_de_billet_id="B1").exists())

    def test_scan_billet_capacite_max(self):
        for i in range(CAPACITE_MAX):
            b = Billet.objects.create(
                numero_de_billet=f"X{i}", date=date.today(), prenom="X", nom="Y"
            )
            VisiteurEnAttraction.objects.create(
                billet=b,
                heure_entree=timezone.now(),
                heure_sortie_prevue=timezone.now() + timedelta(minutes=1),
            )

        response = self.client.post(
            self.url_scan,
            data='{"numero_billet": "B1"}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(VisiteurEnAttraction.objects.count(), CAPACITE_MAX)

    def test_logique_simulation_sortie_et_appel(self):
        heure_passee = timezone.now() - timedelta(minutes=2)
        VisiteurEnAttraction.objects.create(
            billet=self.billet_1.numero_de_billet,
            heure_entree=heure_passee,
            heure_sortie_prevue=heure_passee + timedelta(minutes=1),
        )
        EnFile.objects.filter(pk=self.billet_1.pk).delete()

        maintenant = timezone.now()
        VisiteurEnAttraction.objects.filter(
            heure_sortie_prevue__lte=maintenant
        ).delete()
        appeler_suivants("attraction")

        self.assertEqual(VisiteurEnAttraction.objects.count(), 0)
        self.billet_2.refresh_from_db()
        self.billet_3.refresh_from_db()
        self.assertTrue(self.billet_2.appele)
        self.assertTrue(self.billet_3.appele)
