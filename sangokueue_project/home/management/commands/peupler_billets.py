from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from home.donnees_billets import BILLETS, VALIDITE_JOURS
from home.models import Billet


class Command(BaseCommand):
    help = (
        "Crée ou met à jour les billets de démonstration. "
        "Ne vide pas la file et ne supprime pas les autres billets."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--jours",
            type=int,
            default=VALIDITE_JOURS,
            help=(
                "Nombre de jours de validité à compter d'aujourd'hui "
                f"(défaut : {VALIDITE_JOURS})."
            ),
        )

    def handle(self, *args, **options):
        if options["jours"] < 0:
            raise CommandError("Le nombre de jours doit être positif ou nul.")

        jour = timezone.localdate() + timedelta(days=options["jours"])
        crees = 0
        mis_a_jour = 0
        for numero, prenom, nom, priorite in BILLETS:
            _, created = Billet.objects.update_or_create(
                numero_de_billet=numero,
                defaults={
                    "date": jour,
                    "prenom": prenom,
                    "nom": nom,
                    "priorite": priorite,
                },
            )
            if created:
                crees += 1
            else:
                mis_a_jour += 1
            self.stdout.write(f"{numero}  {prenom} {nom}  valide jusqu'au {jour}")

        self.stdout.write(
            self.style.SUCCESS(
                f"{crees} billet(s) créé(s), {mis_a_jour} mis à jour."
            )
        )
