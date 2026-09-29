from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from home import queues
from home.models import Billet, EnFile, EtatFile
from home.tests_all.tests_queues import _FakeRedis


class StaffInterfaceTests(TestCase):
    def setUp(self):
        self.queue = "kamehouse"
        self.today = timezone.localdate()
        queues._client = _FakeRedis()
        self.user = User.objects.create_user("trunks", password="capsule")
        self.client.login(username="trunks", password="capsule")

    def tearDown(self):
        queues._client = None

    def _ticket(self, number, priority=Billet.Priorite.HUMAN, first="Son", last="Goku"):
        return Billet.objects.create(
            numero_de_billet=number,
            date=self.today,
            prenom=first,
            nom=last,
            priorite=priority,
        )

    def _join(self, number, queue=None, priority=Billet.Priorite.HUMAN, first="Son", last="Goku"):
        self._ticket(number, priority, first, last)
        return EnFile.objects.create(
            numero_de_billet_id=number,
            nom_file=self.queue if queue is None else queue,
        )

    def test_anonymous_user_is_sent_to_login(self):
        self.client.logout()
        response = self.client.get("/staff/")
        self.assertRedirects(response, "/staff/login?next=/staff/")

    def test_lists_waiting_visitors_in_call_order(self):
        self._join("H1", first="Krilin", last="Brief")
        self._join(
            "SS1",
            priority=Billet.Priorite.SUPER_SAIYAN,
            first="Vegeta",
            last="Prince",
        )
        self._join("Y1", queue="tenkaichi", first="Yamcha", last="Desert")

        response = self.client.get("/staff/?queue=kamehouse")

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertLess(html.index("SS1"), html.index("H1"))
        self.assertNotContains(response, "Yamcha")
        self.assertContains(response, "Vegeta Prince")
        self.assertContains(response, "Super Saiyan")

    def test_pause_and_resume(self):
        self._join("H1")

        pause = self.client.post("/staff/pause", {"queue": self.queue, "action": "pause"})
        self.assertRedirects(pause, f"/staff/?queue={self.queue}")
        self.assertTrue(EtatFile.objects.get(nom_file=self.queue).en_pause)
        self.assertTrue(queues.is_paused(self.queue))

        resume = self.client.post("/staff/pause", {"queue": self.queue, "action": "resume"})
        self.assertRedirects(resume, f"/staff/?queue={self.queue}")
        self.assertFalse(EtatFile.objects.get(nom_file=self.queue).en_pause)
        self.assertFalse(queues.is_paused(self.queue))

    def test_clear_removes_every_visitor(self):
        self._join("H1")
        self._join("H2", first="Son", last="Gohan")

        response = self.client.post("/staff/clear", {"queue": self.queue})

        self.assertRedirects(response, f"/staff/?queue={self.queue}")
        self.assertFalse(EnFile.objects.filter(nom_file=self.queue).exists())

    def test_remove_one_visitor(self):
        self._join("H1")
        self._join("H2", first="Son", last="Gohan")
        queues.append_to_queue(self.queue, "H1", Billet.Priorite.HUMAN)
        queues.append_to_queue(self.queue, "H2", Billet.Priorite.HUMAN)

        response = self.client.post("/staff/remove", {
            "queue": self.queue,
            "visitor_id": "H1",
        })

        self.assertRedirects(response, f"/staff/?queue={self.queue}")
        self.assertFalse(EnFile.objects.filter(numero_de_billet_id="H1").exists())
        self.assertTrue(EnFile.objects.filter(numero_de_billet_id="H2").exists())

    def test_actions_require_login(self):
        self.client.logout()
        response = self.client.post("/staff/pause", {"queue": self.queue, "action": "pause"})
        self.assertEqual(response.status_code, 302)
        self.assertIn("/staff/login", response.url)
