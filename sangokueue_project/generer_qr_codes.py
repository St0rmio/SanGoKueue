import os
from datetime import date

# 1. Initialisation de Django (obligatoire pour lire Billet.Priorite.HUMAN sans erreur)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sangokueue_app.settings")
import django
django.setup()

# 2. Importation de tes données et de ta fonction de génération
# (Ajuste les chemins d'import si tes fichiers sont dans d'autres dossiers)
from home.donnees_billets import BILLETS
from sangokueue_app.qr_code_generation import generer_qr_code, STATUT_PAR_PRIORITE

def main():
    print(f"Génération de {len(BILLETS)} QR codes en cours...\n")

    erreurs = 0
    for uid, nom, prenom, priorite in BILLETS:
        try:
            # On forge le dictionnaire manuellement, sans requête à la base de données
            billet_dict = {
                "id": uid,
                "nom": nom,
                "prenom": prenom,
                "date_validite": date.today().isoformat(),
                "statut": STATUT_PAR_PRIORITE.get(priorite, "Humain")
            }
            
            # Génération directe de l'image
            chemin = generer_qr_code(billet_dict)
            print(f"{prenom} {nom} -> {chemin}")
        except Exception as e:
            print(f"Erreur pour {prenom} {nom} ({uid}) : {e}")
            erreurs += 1

    print(f"\nTerminé ! {len(BILLETS) - erreurs} QR codes générés avec succès.")

if __name__ == "__main__":
    main()