import json
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

from sangokueue_app.qr_code_generation import (
    creer_billet,
    generer_qr_code,
)

from sangokueue_app.qr_code_lecture import (
    lire_billet,
    ErreurLectureBillet,
)


class TestBillets(SimpleTestCase):

    def test_creation_des_trois_statuts(self):
        """Vérifie que les trois statuts peuvent être créés."""

        statuts = [
            "Super Saiyan",
            "Saiyan",
            "Humain",
        ]

        for statut in statuts:
            billet = creer_billet(
                "Test",
                "Utilisateur",
                "2026-12-31",
                statut,
            )

            self.assertEqual(billet["nom"], "Test")
            self.assertEqual(billet["prenom"], "Utilisateur")
            self.assertEqual(billet["date_validite"], "2026-12-31")
            self.assertEqual(billet["statut"], statut)
            self.assertIn("id", billet)

    def test_generation_et_lecture_qr(self):
        """
        Vérifie le cycle complet :

        billet -> QR code -> lecture QR -> billet.
        """

        statuts = [
            "Super Saiyan",
            "Saiyan",
            "Humain",
        ]

        with tempfile.TemporaryDirectory() as dossier:

            for statut in statuts:

                billet_original = creer_billet(
                    "Goku",
                    "Son",
                    "2026-12-31",
                    statut,
                )

                chemin_qr = generer_qr_code(
                    billet_original,
                    dossier,
                )

                self.assertTrue(
                    Path(chemin_qr).exists()
                )

                billet_lu = lire_billet(
                    chemin_qr
                )

                self.assertEqual(
                    billet_lu,
                    billet_original,
                )

    def test_statut_invalide(self):
        """Vérifie qu'un statut inconnu est refusé."""

        with self.assertRaises(ValueError):
            creer_billet(
                "Test",
                "Utilisateur",
                "2026-12-31",
                "Super Saiyan 2",
            )

    def test_qr_code_invalide(self):
        """Vérifie qu'un QR contenant un billet incomplet est refusé."""

        with tempfile.TemporaryDirectory() as dossier:

            chemin = Path(dossier) / "invalide.png"

            # Billet volontairement incomplet :
            billet = {
                "id": "123",
                "nom": "Test",
                "prenom": "Utilisateur",
                "date_validite": "2026-12-31",
            }

            import qrcode

            qr = qrcode.QRCode()
            qr.add_data(
                json.dumps(billet)
            )
            qr.make(fit=True)

            image = qr.make_image(
                fill_color="black",
                back_color="white",
            )

            image.save(chemin)

            with self.assertRaises(ErreurLectureBillet):
                lire_billet(chemin)