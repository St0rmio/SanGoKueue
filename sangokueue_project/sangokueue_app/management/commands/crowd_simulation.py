import time

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from home.models import (
    EnFile,
    EtatFile,
    PushSubscription,
    VisiteurEnAttraction,
)
from home.push_notifications import send_push_notification
from home.views import (
    QUEUE_NAME,
    _ordre_attente,
    envoyer_notifications_attente,
)


CAPACITE_MAX = 50

MESSAGE_APPEL = (
    "C'est à vous ! "
    "Présentez-vous maintenant à l'entrée de l'attraction."
)


class Command(BaseCommand):
    help = "Gère les sorties automatiques et l'appel de la file d'attente"

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS(
                "Démarrage du gestionnaire d'affluence..."
            )
        )

        while True:
            maintenant = timezone.now()
            appeles = []

            with transaction.atomic():
                # 1. Retirer les visiteurs dont le tour est terminé
                sortants = VisiteurEnAttraction.objects.filter(
                    heure_sortie_prevue__lte=maintenant
                )

                for visiteur in sortants:
                    self.stdout.write(
                        f"Sortie : le billet "
                        f"{visiteur.billet.id} a terminé."
                    )

                sortants.delete()

                # 2. Nombre de personnes actuellement dans l'attraction
                affluence = VisiteurEnAttraction.objects.count()

                # Personnes déjà appelées mais pas encore retirées de la file
                deja_appeles = EnFile.objects.filter(
                    nom_file=QUEUE_NAME,
                    appele=True,
                ).count()

                places_disponibles = max(
                    0,
                    CAPACITE_MAX - affluence - deja_appeles,
                )

                # 3. Vérifier si la file est en pause
                etat = EtatFile.objects.filter(
                    nom_file=QUEUE_NAME
                ).first()

                file_en_pause = (
                    etat is not None
                    and etat.en_pause
                )

                # 4. Récupérer l'ordre réel de la file
                if places_disponibles > 0 and not file_en_pause:
                    entrees = list(
                        EnFile.objects.filter(
                            nom_file=QUEUE_NAME,
                            appele=False,
                        ).select_related(
                            "numero_de_billet"
                        )
                    )

                    ordre = _ordre_attente(
                        entrees,
                        etat,
                        maintenant,
                    )

                    if ordre:
                        # Si l'attraction est totalement vide,
                        # on peut la remplir jusqu'à 50 personnes.
                        if affluence == 0 and deja_appeles == 0:
                            nombre_a_appeler = min(
                                CAPACITE_MAX,
                                len(ordre),
                            )

                        # Ensuite on fonctionne en flux continu :
                        # une place libérée = un nouvel appel.
                        else:
                            nombre_a_appeler = min(
                                1,
                                places_disponibles,
                                len(ordre),
                            )

                        prochains = ordre[:nombre_a_appeler]

                        for prochain in prochains:
                            prochain.appele = True
                            prochain.date_appel = maintenant

                            prochain.save(
                                update_fields=[
                                    "appele",
                                    "date_appel",
                                ]
                            )

                            appeles.append(prochain.pk)

                            self.stdout.write(
                                self.style.SUCCESS(
                                    "Appel du billet "
                                    f"{prochain.numero_de_billet_id}."
                                )
                            )

            # 5. Envoyer le Push "C'est à vous"
            for entree_id in appeles:
                prochain = EnFile.objects.get(
                    pk=entree_id
                )

                abonnement_existe = (
                    PushSubscription.objects.filter(
                        numero_de_billet_id=(
                            prochain.numero_de_billet_id
                        )
                    ).exists()
                )

                if (
                    abonnement_existe
                    and not prochain.notification_appel_envoyee
                ):
                    send_push_notification(
                        prochain.numero_de_billet_id,
                        MESSAGE_APPEL,
                    )

                    prochain.notification_appel_envoyee = True

                    prochain.save(
                        update_fields=[
                            "notification_appel_envoyee"
                        ]
                    )

            # 6. Les personnes derrière ont avancé :
            # vérifier les seuils 10 min / 5 min / prochain
            if appeles:
                envoyer_notifications_attente(
                    QUEUE_NAME
                )

            # Vérification régulière de l'état de l'attraction
            time.sleep(1)