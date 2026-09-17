"""
qr_code_generation.py
=====================

Génère un billet fictif (identifiant unique, nom, prénom, date de validité,
statut) et produit l'image du QR code correspondant.

Le billet est encodé en JSON directement dans le QR code.

Dépendances :
    pip install qrcode[pil]

Utilisation en ligne de commande :
    python generation_billet.py --nom Dupont --prenom Jean --statut "Saiyan"

    python generation_billet.py --nom Dupont --prenom Jean \
        --date-validite 2026-12-31 --statut "Super Saiyan"

Utilisation comme module :
    from generation_billet import creer_billet, generer_qr_code

    billet = creer_billet("Dupont", "Jean", "2026-12-31", "Saiyan")
    chemin_image = generer_qr_code(billet)
"""

from __future__ import annotations

import argparse
import json
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
    image.save(chemin_image)

    return chemin_image


def creer_et_generer(
    nom: str,
    prenom: str,
    date_validite: str | None = None,
    statut: str = "Humain",
    dossier_sortie: str | Path = DOSSIER_SORTIE_DEFAUT,
) -> tuple[dict, Path]:
    """
    Crée un billet et génère directement son QR code.
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


def _main() -> None:
    parser = argparse.ArgumentParser(
        description="Crée un billet fictif avec QR code pour une attraction."
    )

    parser.add_argument(
        "--nom",
        required=True,
        help="Nom du client"
    )

    parser.add_argument(
        "--prenom",
        required=True,
        help="Prénom du client"
    )

    parser.add_argument(
        "--date-validite",
        default=None,
        help="Date de validité au format AAAA-MM-JJ "
             "(par défaut : aujourd'hui)"
    )

    parser.add_argument(
        "--statut",
        required=True,
        choices=sorted(STATUTS_AUTORISES),
        help="Statut du billet : Super Saiyan, Saiyan ou Humain"
    )

    parser.add_argument(
        "--dossier-sortie",
        default=DOSSIER_SORTIE_DEFAUT,
        help=f"Dossier où enregistrer le QR code "
             f"(défaut : {DOSSIER_SORTIE_DEFAUT})"
    )

    args = parser.parse_args()

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

    print("Billet créé :")
    print(f"  ID             : {billet['id']}")
    print(f"  Nom            : {billet['nom']}")
    print(f"  Prénom         : {billet['prenom']}")
    print(f"  Date validité  : {billet['date_validite']}")
    print(f"  Statut         : {billet['statut']}")
    print(f"\nQR code enregistré : {chemin_image}")


if __name__ == "__main__":
    _main()