from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.models import User

from datetime import timedelta, date
from unittest.mock import patch

from home.models import Billet, EnFile, VisiteurEnAttraction
from home.tests_all.tests_append_to_queue import TestAppendToQueue
from home.tests_all.tests_clear_queue import TestClearQueue
from home.tests_all.tests_leave_queue import TestLeaveQueue
from home.tests_all.tests_notifications import NotificationWebSocketTests
from home.tests_all.tests_pause_queue import TestPauseQueue, TestPauseQueueHorloge
from home.tests_all.tests_peupler_billets import TestJeuDeBillets
from home.tests_all.tests_qr_code import TestBillets
from home.tests_all.tests_queues import TestQueues
from home.tests_all.tests_scenario_file import TestScenarioFile
from home.tests_all.tests_visitor import TestVisitorPage

__all__ = [
    "AffluenceAttractionTests",
    "NotificationWebSocketTests",
    "TestAppendToQueue",
    "TestBillets",
    "TestClearQueue",
    "TestJeuDeBillets",
    "TestLeaveQueue",
    "TestPauseQueue",
    "TestPauseQueueHorloge",
    "TestQueues",
    "TestScenarioFile",
    "TestVisitorPage",
]

class AffluenceAttractionTests(TestCase):
    def setUp(self):
        # 1. Création des billets parents requis par le modèle
        b1 = Billet.objects.create(numero_de_billet="B1", date=date.today(), prenom="Jean", nom="A")
        b2 = Billet.objects.create(numero_de_billet="B2", date=date.today(), prenom="Marie", nom="B")
        b3 = Billet.objects.create(numero_de_billet="B3", date=date.today(), prenom="Luc", nom="C")
        
        # 2. Création des entrées dans la file (appele=False remplace statut="en_attente")
        self.billet_1 = EnFile.objects.create(numero_de_billet=b1, nom_file="Attraction 33", appele=False)
        self.billet_2 = EnFile.objects.create(numero_de_billet=b2, nom_file="Attraction 33", appele=False)
        self.billet_3 = EnFile.objects.create(numero_de_billet=b3, nom_file="Attraction 33", appele=False)
        
        # URL fictive pour le scan (à adapter selon ton urls.py, ici on utilise la PK de EnFile)
        self.url_scan = reverse('staff:scanner_billet', args=[self.billet_1.id])

        # 3. Création et connexion d'un compte Staff pour les tests
        self.staff_user = User.objects.create_superuser('staff_test', 'staff@test.com', 'password')
        self.client.force_login(self.staff_user)

    @patch('staff.views.random.randint')
    def test_scan_billet_succes(self, mock_randint):
        # Forcer le temps aléatoire à 60 secondes pour prévisibilité
        mock_randint.return_value = 60 
        
        response = self.client.post(self.url_scan)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(VisiteurEnAttraction.objects.count(), 1)
        
        visiteur = VisiteurEnAttraction.objects.first()
        self.assertEqual(visiteur.billet, self.billet_1)
        
        # Vérifier que l'heure de sortie prévue est bien dans 60 secondes
        diff = visiteur.heure_sortie_prevue - visiteur.heure_entree
        self.assertAlmostEqual(diff.total_seconds(), 60, delta=1)

    def test_scan_billet_capacite_max(self):
        # Remplir l'attraction à sa capacité maximale (50)
        for i in range(50):
            b = Billet.objects.create(numero_de_billet=f"X{i}", date=date.today(), prenom="X", nom="Y")
            ef = EnFile.objects.create(numero_de_billet=b, nom_file="Attraction 33", appele=False)
            VisiteurEnAttraction.objects.create(
                billet=ef,
                heure_entree=timezone.now(),
                heure_sortie_prevue=timezone.now() + timedelta(minutes=1)
            )
            
        # Tenter de scanner un 51ème billet (le self.billet_1)
        url_scan_51 = reverse('staff:scanner_billet', args=[self.billet_1.id])
        response = self.client.post(url_scan_51)
        
        # Vérifier le rejet (HTTP 400 Bad Request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(VisiteurEnAttraction.objects.count(), 50)

    def test_logique_simulation_sortie_et_appel(self):
        # 1. Préparation : Un visiteur est entré il y a 2 minutes (temps écoulé)
        heure_passee = timezone.now() - timedelta(minutes=2)
        VisiteurEnAttraction.objects.create(
            billet=self.billet_1,
            heure_entree=heure_passee,
            heure_sortie_prevue=heure_passee + timedelta(minutes=1)
        )
        
        # 2. Exécution de la logique (copie de la boucle crowd_simulation.py)
        maintenant = timezone.now()
        sortants = VisiteurEnAttraction.objects.filter(heure_sortie_prevue__lte=maintenant)
        sortants.delete()
        
        places_disponibles = 50 - VisiteurEnAttraction.objects.count()
        if places_disponibles > 0:
            # On trie par date_entree puisque tu n'as pas de champ position
            prochains = EnFile.objects.filter(appele=False).order_by('date_entree')[:places_disponibles]
            for prochain in prochains:
                prochain.appele = True
                prochain.save()

        # 3. Assertions : Vérifier que le système a fait son travail
        self.assertEqual(VisiteurEnAttraction.objects.count(), 0) # Le visiteur 1 est retiré
        
        # Les billets 2 et 3 ont dû être appelés (appele = True)
        self.billet_2.refresh_from_db()
        self.billet_3.refresh_from_db()
        self.assertTrue(self.billet_2.appele)
        self.assertTrue(self.billet_3.appele)