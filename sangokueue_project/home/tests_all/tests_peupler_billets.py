import os
import uuid
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from home import queues
from home.donnees_billets import BILLETS, VALIDITE_JOURS
from home.models import Billet, EnFile
from home.tests_all.tests_queues import _FakeRedis


class TestJeuDeBillets(TestCase):
    def test_les_numeros_sont_des_uuid(self):
        numeros = [numero for numero, *_reste in BILLETS]
        self.assertEqual(len(numeros), len(set(numeros)))
        for numero, _prenom, _nom, _priorite in BILLETS:
            identifiant = uuid.UUID(numero)
            self.assertEqual(str(identifiant), numero)
            self.assertEqual(identifiant.version, 4)
            self.assertEqual(len(numero), 36)

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
        numero, _prenom, _nom, _priorite = BILLETS[0]
        call_command("peupler_billets", stdout=StringIO())
        Billet.objects.filter(pk=numero).update(
            prenom="Ancien",
            date=timezone.localdate() - timedelta(days=2),
        )
        EnFile.objects.create(
            numero_de_billet_id=numero,
            nom_file="attraction",
        )

        call_command("peupler_billets", stdout=StringIO())

        self.assertEqual(Billet.objects.count(), len(BILLETS))
        billet = Billet.objects.get(pk=numero)
        self.assertEqual(billet.prenom, "Son")
        self.assertGreaterEqual(billet.date, timezone.localdate())
        self.assertTrue(EnFile.objects.filter(numero_de_billet_id=numero).exists())

    def test_la_saisie_retrouve_le_numero_exact_apres_strip(self):
        queues._client = _FakeRedis()
        self.addCleanup(setattr, queues, "_client", None)
        call_command("peupler_billets", stdout=StringIO())
        numero_goku = BILLETS[0][0]
        numero_vegeta = BILLETS[7][0]

        response = self.client.get("/visiteur/", {"billet": f"  {numero_goku}  "})

        self.assertContains(response, "Son Goku")
        self.assertTrue(
            EnFile.objects.filter(
                numero_de_billet_id=numero_goku,
                nom_file="attraction",
            ).exists()
        )
        self.assertEqual(
            self.client.get("/visiteur/", {"billet": numero_goku.upper()}).status_code,
            404,
        )
        self.assertEqual(self.client.get(f"/visiteur/{numero_vegeta}/").status_code, 200)
        self.assertContains(self.client.get(f"/visiteur/{numero_vegeta}/"), "Vegeta Prince")


class TestDemarrageProduction(SimpleTestCase):
    @patch("sangokueue_app.demarrage.call_command")
    def test_hors_production_ne_touche_pas_la_base(self, commande):
        from sangokueue_app.demarrage import preparer_production

        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            preparer_production()

        commande.assert_not_called()

    @patch("sangokueue_app.demarrage.call_command")
    def test_en_production_migre_puis_peuple(self, commande):
        from sangokueue_app.demarrage import preparer_production

        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            preparer_production()

        commande.assert_any_call("migrate", interactive=False, verbosity=1)
        commande.assert_any_call("peupler_billets")
