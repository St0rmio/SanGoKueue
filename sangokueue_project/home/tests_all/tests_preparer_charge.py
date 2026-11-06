from datetime import timedelta
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from home.models import Billet, EnFile


class TestPreparerCharge(TestCase):
    def setUp(self):
        self.sortie = Path(f"{self.id().replace('.', '_')}_billets.txt")

    def tearDown(self):
        self.sortie.unlink(missing_ok=True)

    def test_cree_des_billets_valides_et_les_ecrit(self):
        call_command(
            "preparer_charge",
            nombre=5,
            sortie=str(self.sortie),
            stdout=StringIO(),
        )

        self.assertEqual(Billet.objects.count(), 5)
        self.assertTrue(
            all(billet.date >= timezone.localdate() for billet in Billet.objects.all())
        )
        identifiants = [
            ligne.strip()
            for ligne in self.sortie.read_text().splitlines()
            if ligne.strip() and not ligne.startswith("#")
        ]
        self.assertEqual(
            identifiants,
            sorted(Billet.objects.values_list("numero_de_billet", flat=True)),
        )

    def test_ne_vide_pas_la_file_et_garde_les_billets_existants(self):
        existant = Billet.objects.create(
            numero_de_billet="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            date=timezone.localdate() + timedelta(days=1),
            prenom="Son",
            nom="Goku",
        )
        EnFile.objects.create(numero_de_billet=existant, nom_file="attraction")

        call_command(
            "preparer_charge",
            nombre=2,
            sortie=str(self.sortie),
            stdout=StringIO(),
        )

        self.assertEqual(Billet.objects.count(), 3)
        self.assertTrue(
            EnFile.objects.filter(numero_de_billet=existant).exists()
        )
        self.assertIn(existant.pk, self.sortie.read_text())

    def test_refuse_un_nombre_negatif(self):
        with self.assertRaises(CommandError):
            call_command("preparer_charge", nombre=-1, stdout=StringIO())
