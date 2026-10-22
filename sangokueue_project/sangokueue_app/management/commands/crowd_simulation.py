import time

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from home.models import EnFile, EtatFile, VisiteurEnAttraction
from home.views import (
    CAPACITE_MAX,
    QUEUE_NAME,
    appeler_suivants,
    expirer_appels,
)


class Command(BaseCommand):
    help = "Gère les sorties automatiques et l'appel de la file d'attente"

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS("Démarrage du gestionnaire d'affluence...")
        )

        while True:
            with transaction.atomic():
                maintenant = timezone.now()
                sortants = VisiteurEnAttraction.objects.filter(
                    heure_sortie_prevue__lte=maintenant,
                )
                for visiteur in sortants:
                    self.stdout.write(
                        f"Sortie : Billet {visiteur.billet_id}"
                    )
                sortants.delete()

            files = sorted(
                set(EnFile.objects.values_list("nom_file", flat=True))
                | set(EtatFile.objects.values_list("nom_file", flat=True))
                | {QUEUE_NAME}
            )
            for nom in files:
                expirer_appels(nom)
                appeles = appeler_suivants(nom)
                for entree in appeles:
                    places = CAPACITE_MAX - VisiteurEnAttraction.objects.count()
                    self.stdout.write(self.style.SUCCESS(
                        f"Appel du billet {entree.numero_de_billet_id} "
                        f"({places} places restantes hors appelés)."
                    ))

            time.sleep(1)
