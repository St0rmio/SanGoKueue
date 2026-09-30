from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from home import queues
from home.donnees_billets import BILLETS, VALIDITE_JOURS
from home.models import Billet, EnFile
from home.tests_all.tests_queues import _FakeRedis

PREFIXE = {
    Billet.Priorite.HUMAN: "H",
    Billet.Priorite.SAIYAN: "S",
    Billet.Priorite.SUPER_SAIYAN: "SS",
}


class TestJeuDeBillets(TestCase):
    def test_le_numero_suit_le_prefixe_et_le_rang(self):
        for priorite, prefixe in PREFIXE.items():
            serie = [numero for numero, _prenom, _nom, p in BILLETS if p == priorite]
            self.assertGreaterEqual(len(serie), 1)
            for rang, numero in enumerate(serie, start=1):
                self.assertEqual(numero, f"{prefixe}{rang}")
                self.assertLessEqual(len(numero), 32)

    def test_saiyan_et_super_saiyan_ne_partagent_pas_de_numero(self):
        numeros = [numero for numero, *_reste in BILLETS]
        self.assertEqual(len(numeros), len(set(numeros)))
        for numero, _prenom, _nom, priorite in BILLETS:
            if priorite == Billet.Priorite.SAIYAN:
                self.assertRegex(numero, r"^S[1-9][0-9]*$")
            if priorite == Billet.Priorite.SUPER_SAIYAN:
                self.assertRegex(numero, r"^SS[1-9][0-9]*$")

    def test_peupler_renseigne_la_cle_le_nom_et_la_validite(self):
        call_command("peupler_billets", stdout=StringIO())

        self.assertEqual(Billet.objects.count(), len(BILLETS))
        validite = timezone.localdate() + timedelta(days=VALIDITE_JOURS)
        for numero, prenom, nom, priorite in BILLETS:
            billet = Billet.objects.get(pk=numero)
            self.assertEqual(billet.prenom, prenom)
            self.assertEqual(billet.nom, nom)
            self.assertEqual(billet.priorite, priorite)
            self.assertEqual(billet.date, validite)

    def test_relancer_met_a_jour_sans_dupliquer_ni_vider_la_file(self):
        call_command("peupler_billets", stdout=StringIO())
        Billet.objects.filter(pk="H1").update(
            prenom="Ancien",
            date=timezone.localdate() - timedelta(days=2),
        )
        EnFile.objects.create(
            numero_de_billet_id="H1",
            nom_file="attraction",
        )

        call_command("peupler_billets", stdout=StringIO())

        self.assertEqual(Billet.objects.count(), len(BILLETS))
        h1 = Billet.objects.get(pk="H1")
        self.assertEqual(h1.prenom, "Son")
        self.assertGreaterEqual(h1.date, timezone.localdate())
        self.assertTrue(EnFile.objects.filter(numero_de_billet_id="H1").exists())

    def test_la_saisie_retrouve_le_numero_exact_apres_strip(self):
        queues._client = _FakeRedis()
        self.addCleanup(setattr, queues, "_client", None)
        call_command("peupler_billets", stdout=StringIO())

        response = self.client.get("/visiteur/", {"billet": "  H1  "})

        self.assertContains(response, "Son Goku")
        self.assertTrue(
            EnFile.objects.filter(numero_de_billet_id="H1", nom_file="attraction").exists()
        )
        self.assertEqual(self.client.get("/visiteur/", {"billet": "h1"}).status_code, 404)
        self.assertEqual(self.client.get("/visiteur/S1/").status_code, 200)
        self.assertContains(self.client.get("/visiteur/SS1/"), "Vegeta Prince")
