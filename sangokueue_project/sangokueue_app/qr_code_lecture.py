"""
qr_code_lecture.py
==================

Lit un QR code de billet (généré par generation_billet.py) et affiche les
informations du billet : identifiant, nom, prénom, date de validité et statut.

Dépendances :
    pip install opencv-python-headless

Utilisation en ligne de commande :
    python lecture_billet.py billets/billet_xxxxxxxx.png

Utilisation comme module :
    from lecture_billet import lire_billet

    billet = lire_billet("billets/billet_xxxxxxxx.png")
    print(billet["nom"])
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2


# Les seuls statuts autorisés
STATUTS_AUTORISES = {
    "Super Saiyan",
    "Saiyan",
    "Humain",
}


class ErreurLectureBillet(Exception):
    """Levée quand un billet ne peut pas être lu ou n'est pas valide."""


def _charger_image(chemin_image: str | Path):
    chemin_image = Path(chemin_image)

    if not chemin_image.exists():
        raise ErreurLectureBillet(
            f"Fichier introuvable : {chemin_image}"
        )

    image = cv2.imread(str(chemin_image))

    if image is None:
        raise ErreurLectureBillet(
            f"Impossible de lire l'image : {chemin_image}"
        )

    return image


def _decoder_qr_code(image) -> str:
    detecteur = cv2.QRCodeDetector()

    donnees, points, _ = detecteur.detectAndDecode(image)

    if not donnees:
        raise ErreurLectureBillet(
            "Aucun QR code détecté dans l'image."
        )

    return donnees


def lire_billet(chemin_image: str | Path) -> dict:
    """
    Lit un QR code de billet et retourne ses informations.

    :param chemin_image: chemin de l'image contenant le QR code
    :return: dictionnaire du billet
    :raises ErreurLectureBillet: si l'image est illisible, sans QR code,
                                 ou si le contenu n'est pas un billet valide
    """

    image = _charger_image(chemin_image)

    contenu_brut = _decoder_qr_code(image)

    # Conversion du JSON
    try:
        billet = json.loads(contenu_brut)

    except json.JSONDecodeError as erreur:
        raise ErreurLectureBillet(
            "Le QR code lu ne contient pas un billet valide "
            f"(contenu : {contenu_brut!r})"
        ) from erreur

    # Vérification des champs obligatoires
    champs_attendus = {
        "id",
        "nom",
        "prenom",
        "date_validite",
        "statut",
    }

    champs_manquants = champs_attendus - billet.keys()

    if champs_manquants:
        raise ErreurLectureBillet(
            "Billet incomplet, champ(s) manquant(s) : "
            f"{', '.join(sorted(champs_manquants))}"
        )

    # Vérification du statut
    if billet["statut"] not in STATUTS_AUTORISES:
        raise ErreurLectureBillet(
            f"Statut de billet invalide : {billet['statut']!r}. "
            "Les statuts autorisés sont : "
            f"{', '.join(sorted(STATUTS_AUTORISES))}"
        )

    return billet


def _main() -> None:
    parser = argparse.ArgumentParser(
        description="Lit un QR code de billet et affiche ses informations."
    )

    parser.add_argument(
        "chemin_image",
        help="Chemin vers l'image du QR code à lire"
    )

    args = parser.parse_args()

    try:
        billet = lire_billet(args.chemin_image)

    except ErreurLectureBillet as erreur:
        print(f"Erreur : {erreur}", file=sys.stderr)
        sys.exit(1)

    print("Billet identifié :")
    print(f"  ID             : {billet['id']}")
    print(f"  Nom            : {billet['nom']}")
    print(f"  Prénom         : {billet['prenom']}")
    print(f"  Date validité  : {billet['date_validite']}")
    print(f"  Statut         : {billet['statut']}")


if __name__ == "__main__":
    _main()