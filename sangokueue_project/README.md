# Project Django SanGoKueue - Instructions

Pour pouvoir utiliser le projet Django de ce répertoire en local sur votre machine, il faut commencer par créer un environnement Python sur votre machine.

## Création de l'environnement Python

La commande suivante crée un environnment virtuel "env" dans le répertoire courant :
```
python -m venv env
```

Vous pouvez lancer l'environnement dans votre terminal Windows de la manière suivante : 
```
.\env\Scripts\activate
```

## Installation de Django

Il faut désormais installer le package Django dans votre environnement Python : 
```
pip install django
```

Vous pouvez ensuite vérifier la version installée : 
```
python -m django --version
```

## Lancement de l'application Django

Une fois dans le répertoire `sangokueue_app`, vous pouvez lancer le serveur de test local Django : 
```
python manage.py runserver
```

Vous pouvez accéder désormais au site en test sur votre navigateur web :
```
http://127.0.0.1:8000/
```
