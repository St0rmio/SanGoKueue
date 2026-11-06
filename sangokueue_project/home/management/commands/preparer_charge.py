import random
import uuid
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from home.donnees_billets import VALIDITE_JOURS
from home.models import Billet

PRENOMS = ("Son", "Bulma", "Krillin", "Yamcha", "Chiaotzu")
NOMS = ("Goku", "Brief", "Desert", "Crane", "Ox")


class Command(BaseCommand):
    help = (
        "Crée des billets valides pour Locust et écrit leurs identifiants "
        "dans load/billets.txt. Ne vide pas la file."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--nombre",
            type=int,
            default=100,
            help="Nombre de billets à créer (défaut : 100).",
        )
        parser.add_argument(
            "--sortie",
            default="",
            help="Fichier d'identifiants (défaut : load/billets.txt).",
        )

    def handle(self, *args, **options):
        nombre = options["nombre"]
        if nombre < 0:
            raise CommandError("Le nombre de billets doit être positif ou nul.")

        jour = timezone.localdate() + timedelta(days=VALIDITE_JOURS)
        for indice in range(nombre):
            Billet.objects.create(
                numero_de_billet=str(uuid.uuid4()),
                date=jour,
                prenom=PRENOMS[indice % len(PRENOMS)],
                nom=NOMS[indice % len(NOMS)],
                priorite=random.choices(
                    [
                        Billet.Priorite.HUMAN,
                        Billet.Priorite.SAIYAN,
                        Billet.Priorite.SUPER_SAIYAN,
                    ],
                    weights=[70, 20, 10],
                )[0],
            )

        sortie = Path(options["sortie"] or settings.BASE_DIR / "load" / "billets.txt")
        identifiants = list(
            Billet.objects.filter(date__gte=timezone.localdate())
            .order_by("numero_de_billet")
            .values_list("numero_de_billet", flat=True)
        )
        sortie.parent.mkdir(parents=True, exist_ok=True)
        sortie.write_text(
            "# Identifiants de billets pour Locust, un par ligne.\n"
            + "\n".join(identifiants)
            + ("\n" if identifiants else "")
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"{nombre} billet(s) créé(s), "
                f"{len(identifiants)} écrit(s) dans {sortie}."
            )
        )
