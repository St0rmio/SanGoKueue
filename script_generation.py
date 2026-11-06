import uuid
import random

def generer_1000_billets():
    prenoms = [
        "Goku", "Vegeta", "Piccolo", "Bulma", "Krillin", "Gohan", "Trunks", 
        "Frieza", "Cell", "Buu", "Tenshinhan", "Yamcha", "Videl", "Satan", 
        "Goten", "Pan", "Uub", "Broly", "Beerus", "Whis", "Champa", "Vados",
        "Zeno", "Jiren", "Toppo", "Dyspo", "Hit", "Cabba", "Caulifla", "Kale"
    ]
    
    noms = [
        "Son", "Brief", "Demon", "Alien", "Cyborg", "Majin", "Earthling", 
        "Saiyan", "God", "Angel", "Oozaru", "Namekian", "Capsule", "RedRibbon",
        "Universe7", "Universe6", "Universe11", "PrideTrooper", "Destroyer"
    ]
    
    priorites = [
        "Billet.Priorite.HUMAN", 
        "Billet.Priorite.SAIYAN", 
        "Billet.Priorite.SUPER_SAIYAN"
    ]

    lignes_billets = []
    
    for _ in range(1000):
        nouvel_uuid = str(uuid.uuid4())
        prenom = random.choice(prenoms)
        nom = random.choice(noms)
        
        # Ajustement logique optionnel : un "Saiyan" a plus de chance d'avoir une priorité Saiyan
        if nom == "Saiyan":
            priorite = random.choice(["Billet.Priorite.SAIYAN", "Billet.Priorite.SUPER_SAIYAN"])
        elif nom in ["Earthling", "Brief"]:
            priorite = "Billet.Priorite.HUMAN"
        else:
            priorite = random.choice(priorites)

        lignes_billets.append(f'    ("{nouvel_uuid}", "{prenom}", "{nom}", {priorite}),')

    # Écriture dans un fichier texte
    with open("1000_billets_supp.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(lignes_billets))
        
    print("Fichier '1000_billets_supp.txt' généré avec succès !")

if __name__ == "__main__":
    generer_1000_billets()