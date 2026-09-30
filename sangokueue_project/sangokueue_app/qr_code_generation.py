"""
qr_code_generation.py
=====================

Génère l'image du QR code d'un billet (identifiant unique, nom, prénom,
date de validité, statut).

Le billet est encodé en JSON directement dans le QR code.

Deux façons de l'utiliser :

1. À partir d'un ou plusieurs numéros de billet DÉJÀ enregistrés en base.
   Le script va chercher lui-même le nom, le prénom, la date et le statut.
   À lancer depuis le dossier qui contient manage.py :

       python sangokueue_app/qr_code_generation.py 97fd2a68-3107-4e46-8b91-87f6a8c1ee10
       python sangokueue_app/qr_code_generation.py NUMERO_1 NUMERO_2 NUMERO_3

2. En créant un billet fictif (comme avant, il n'est PAS enregistré en base) :

       python sangokueue_app/qr_code_generation.py --nom Dupont --prenom Jean --statut "Saiyan"

Dépendances :
    pip install qrcode[pil]

Utilisation comme module :
    from qr_code_generation import creer_billet, generer_qr_code

    billet = creer_billet("Dupont", "Jean", "2026-12-31", "Saiyan")
    chemin_image = generer_qr_code(billet)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import date
from pathlib import Path

import qrcode


DOSSIER_SORTIE_DEFAUT = "billets"

# Les seuls statuts autorisés
STATUTS_AUTORISES = {
    "Super Saiyan",
    "Saiyan",
    "Humain",
}

# Priorité enregistrée en base (Billet.priorite) -> statut écrit dans le QR code
STATUT_PAR_PRIORITE = {
    0: "Humain",
    1: "Saiyan",
    2: "Super Saiyan",
}


def creer_billet(
    nom: str,
    prenom: str,
    date_validite: str | None = None,
    statut: str = "Humain",
) -> dict:
    """
    Construit un billet fictif avec un identifiant unique (UUID).

    :param nom: nom du client
    :param prenom: prénom du client
    :param date_validite: date de validité au format "AAAA-MM-JJ".
                           Si non fournie, la date du jour est utilisée.
    :param statut: statut du client :
                   "Super Saiyan", "Saiyan" ou "Humain".
    :return: dictionnaire représentant le billet
    """

    if statut not in STATUTS_AUTORISES:
        raise ValueError(
            f"Statut invalide : {statut!r}. "
            f"Les statuts autorisés sont : "
            f"{', '.join(sorted(STATUTS_AUTORISES))}"
        )

    if date_validite is None:
        date_validite = date.today().isoformat()

    return {
        "id": str(uuid.uuid4()),
        "nom": nom,
        "prenom": prenom,
        "date_validite": date_validite,
        "statut": statut,
    }


def _initialiser_django() -> None:
    """Permet à ce script d'utiliser la base de données du projet Django."""
    racine = Path(__file__).resolve().parent.parent   # le dossier qui contient manage.py
    if str(racine) not in sys.path:
        sys.path.insert(0, str(racine))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sangokueue_app.settings")

    import django
    django.setup()


def lire_billet_en_base(numero_de_billet: str) -> dict:
    """
    Récupère un billet dans la base à partir de son numéro et le met
    au même format que creer_billet().

    :param numero_de_billet: numéro du billet (Billet.numero_de_billet)
    :return: dictionnaire représentant le billet
    :raises ValueError: si le billet n'existe pas ou a une priorité inconnue
    """

    _initialiser_django()
    from home.models import Billet

    numero = numero_de_billet.strip()

    try:
        billet = Billet.objects.get(pk=numero)
    except Billet.DoesNotExist:
        raise ValueError(f"Billet introuvable en base : {numero!r}") from None

    statut = STATUT_PAR_PRIORITE.get(billet.priorite)
    if statut is None:
        raise ValueError(
            f"Priorité inconnue ({billet.priorite!r}) pour le billet {numero!r}."
        )

    return {
        "id": billet.pk,
        "nom": billet.nom,
        "prenom": billet.prenom,
        "date_validite": billet.date.isoformat(),
        "statut": statut,
    }


def generer_qr_code(
    billet: dict,
    dossier_sortie: str | Path = DOSSIER_SORTIE_DEFAUT
) -> Path:
    """
    Génère l'image du QR code d'un billet et l'enregistre sur disque.

    Le contenu du QR code est le billet sérialisé en JSON.

    :param billet: dictionnaire billet (voir creer_billet)
    :param dossier_sortie: dossier où enregistrer l'image PNG
    :return: chemin de l'image générée
    """

    dossier_sortie = Path(dossier_sortie)
    dossier_sortie.mkdir(parents=True, exist_ok=True)

    contenu = json.dumps(billet, ensure_ascii=False)

    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )

    qr.add_data(contenu)
    qr.make(fit=True)

    image = qr.make_image(
        fill_color="black",
        back_color="white"
    )

    chemin_image = dossier_sortie / f"billet_{billet['id']}.png"
    # OpenCV ne détecte pas toujours les PNG 1 bit produits par défaut.
    image.convert("RGB").save(chemin_image)

    return chemin_image


def creer_et_generer(
    nom: str,
    prenom: str,
    date_validite: str | None = None,
    statut: str = "Humain",
    dossier_sortie: str | Path = DOSSIER_SORTIE_DEFAUT,
) -> tuple[dict, Path]:
    """
    Crée un billet fictif et génère directement son QR code.
    """

    billet = creer_billet(
        nom,
        prenom,
        date_validite,
        statut
    )

    chemin_image = generer_qr_code(
        billet,
        dossier_sortie
    )

    return billet, chemin_image


def generer_depuis_base(
    numero_de_billet: str,
    dossier_sortie: str | Path = DOSSIER_SORTIE_DEFAUT,
) -> tuple[dict, Path]:
    """
    Génère le QR code d'un billet déjà enregistré en base, à partir
    de son seul numéro.
    """

    billet = lire_billet_en_base(numero_de_billet)
    chemin_image = generer_qr_code(billet, dossier_sortie)

    return billet, chemin_image


def _afficher(billet: dict, chemin_image: Path) -> None:
    print("Billet :")
    print(f"  ID             : {billet['id']}")
    print(f"  Nom            : {billet['nom']}")
    print(f"  Prénom         : {billet['prenom']}")
    print(f"  Date validité  : {billet['date_validite']}")
    print(f"  Statut         : {billet['statut']}")
    print(f"  QR code        : {chemin_image}\n")


def _main() -> None:
    parser = argparse.ArgumentParser(
        description="Génère le QR code d'un ou plusieurs billets."
    )

    parser.add_argument(
        "numeros",
        nargs="*",
        metavar="NUMERO",
        help="Numéro(s) de billet déjà enregistré(s) en base : "
             "le nom, le prénom, la date et le statut sont récupérés "
             "automatiquement"
    )

    parser.add_argument(
        "--nom",
        help="Nom du client (billet fictif, sans numéro)"
    )

    parser.add_argument(
        "--prenom",
        help="Prénom du client (billet fictif, sans numéro)"
    )

    parser.add_argument(
        "--date-validite",
        default=None,
        help="Date de validité au format AAAA-MM-JJ "
             "(billet fictif, par défaut : aujourd'hui)"
    )

    parser.add_argument(
        "--statut",
        choices=sorted(STATUTS_AUTORISES),
        help="Statut du billet fictif : Super Saiyan, Saiyan ou Humain"
    )

    parser.add_argument(
        "--dossier-sortie",
        default=DOSSIER_SORTIE_DEFAUT,
        help=f"Dossier où enregistrer les QR codes "
             f"(défaut : {DOSSIER_SORTIE_DEFAUT})"
    )

    args = parser.parse_args()

    # --- Mode 1 : à partir de numéros de billet enregistrés en base ---
    if args.numeros:
        if args.nom or args.prenom or args.statut or args.date_validite:
            parser.error(
                "Avec des numéros de billet, n'utilisez pas "
                "--nom, --prenom, --statut ni --date-validite : "
                "ces informations viennent de la base."
            )

        erreurs = 0
        for numero in args.numeros:
            try:
                billet, chemin_image = generer_depuis_base(
                    numero,
                    args.dossier_sortie
                )
            except ValueError as erreur:
                print(f"Erreur : {erreur}\n")
                erreurs += 1
                continue

            _afficher(billet, chemin_image)

        sys.exit(1 if erreurs else 0)

    # --- Mode 2 : billet fictif (comportement d'origine) ---
    if not (args.nom and args.prenom and args.statut):
        parser.error(
            "Indiquez un ou plusieurs numéros de billet, "
            "ou bien --nom, --prenom et --statut pour un billet fictif."
        )

    try:
        billet, chemin_image = creer_et_generer(
            args.nom,
            args.prenom,
            args.date_validite,
            args.statut,
            args.dossier_sortie
        )

    except ValueError as erreur:
        print(f"Erreur : {erreur}")
        sys.exit(1)

    _afficher(billet, chemin_image)


if __name__ == "__main__":
    _main()