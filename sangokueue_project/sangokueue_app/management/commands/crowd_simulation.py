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
            with transaction.atomic():
                maintenant = timezone.now()
            
                # 1. Faire sortir ceux dont le temps est écoulé
                sortants = VisiteurEnAttraction.objects.filter(heure_sortie_prevue__lte=maintenant)
                            
                # Affichage optionnel dans le terminal
                for visiteur in sortants:
                    self.stdout.write(f"Sortie : Billet {visiteur.billet.numero_de_billet}")
                            
                # On les supprime du manège (les places redeviennent libres)
                sortants.delete()
            
                # 2. Appeler les prochains de la file
                # Calculer les places libres et passer "appele = True" aux X suivants
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