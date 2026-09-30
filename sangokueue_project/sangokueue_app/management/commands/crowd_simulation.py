import time
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from home.models import VisiteurEnAttraction, EnFile

# from home.notifications import notifier_visiteur 

class Command(BaseCommand):
    help = "Gère les sorties automatiques et l'appel de la file d'attente"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Démarrage du gestionnaire d'affluence..."))
        CAPACITE_MAX = 50

        while True:
            maintenant = timezone.now()

            with transaction.atomic():
                # 1. Trouver ceux dont le temps de manège est terminé
                sortants = VisiteurEnAttraction.objects.filter(heure_sortie_prevue__lte=maintenant)
                nb_sortants = sortants.count()

                if nb_sortants > 0:
                    for visiteur in sortants:
                        self.stdout.write(f"Sortie : Le billet {visiteur.billet.id} a terminé.")
                        # Optionnel : archiver le billet dans l'historique avant de le supprimer
                    
                    # Retirer les visiteurs de l'attraction (libère de la place)
                    sortants.delete() 

                # 2. Vérifier combien de places sont maintenant disponibles
                affluence = VisiteurEnAttraction.objects.count()
                places_disponibles = CAPACITE_MAX - affluence

                # 3. Appeler les personnes en attente selon les places libres
                if places_disponibles > 0:
                    # Récupérer les prochains dans la file (adapter 'position' selon ton modèle)
                    prochains = EnFile.objects.filter(statut="en_attente").order_by('position')[:places_disponibles]
                    
                    for prochain in prochains:
                        self.stdout.write(self.style.SUCCESS(f"Appel du billet {prochain.id} à rejoindre l'attraction."))
                        
                        # Changer le statut pour ne pas le rappeler à la prochaine seconde
                        prochain.statut = "appele"
                        prochain.save()
                        
                        # Lancer ta logique de notification (WebSocket, SMS, etc.)
                        # notifier_visiteur(prochain)

            # Pause d'une seconde pour ne pas surcharger la base de données
            time.sleep(1)