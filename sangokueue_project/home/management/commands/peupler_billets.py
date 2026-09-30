import os
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from home.donnees_billets import BILLETS, VALIDITE_JOURS
from home.models import Billet

ADMIN_USERNAME = "admin"


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

        self._assurer_admin()
        self.stdout.write(
            self.style.SUCCESS(
                f"{crees} billet(s) créé(s), {mis_a_jour} mis à jour."
            )
        )

    def _assurer_admin(self):
        password = os.environ.get("ADMIN_PASSWORD", "admin")
        user, created = User.objects.get_or_create(
            username=ADMIN_USERNAME,
            defaults={"is_staff": True, "is_superuser": True},
        )
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.set_password(password)
        user.save()
        etat = "créé" if created else "à jour"
        self.stdout.write(self.style.SUCCESS(f"Compte {ADMIN_USERNAME} {etat}."))
