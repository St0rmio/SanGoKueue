# Project Django SanGoKueue - Instructions

Ce README liste la marche à suivre pour tester le projet Django en local sur votre PC.

## Installation et mise à jour de Python

Python est nécessaire au fonctionnement de Django, suivez les instructions du site officiel : 

[https://www.python.org/downloads/](https://www.python.org/downloads/)

Vous pouvez vérifier la version installée avec la commande suivante dans le terminal :
```
python3 --version
```

## Mise à jour de pip

Windows : 
```
python -m pip install --upgrade pip
```

Mac :
```
pip3 install --upgrade pip
```

## Création de l'environnement Python

Pour pouvoir utiliser le projet Django de ce répertoire en local sur votre machine, il faut commencer par créer un environnement Python sur votre machine.

La commande suivante crée un environnment virtuel "env" dans le répertoire courant :
```
python3 -m venv env
```

Vous pouvez lancer l'environnement dans votre terminal Windows de la manière suivante : 
```
.\env\Scripts\activate
```

Sur Linux/Mac : 
```
source env/bin/activate
```

## Installation de Django

Il faut désormais installer le package Django dans votre environnement Python : 
```
pip install Django==6.1.1
```

Vous pouvez ensuite vérifier la version installée : 
```
python3 -m django --version
```

## Lancement de l'application Django

Une fois dans le répertoire `sangokueue_app`, vous pouvez lancer le serveur de test local Django : 
```
python3 manage.py runserver
```

Vous pouvez accéder désormais au site en test sur votre navigateur web :
```
http://127.0.0.1:8000/
```

## Installation du reste des packages nécessaires

Toujours en restant dans votre environnement Python, installez le reste des dépendances du projet :
```
pip install -r requirements.txt
```

## Sortir de l'environnement virtuel

```
deactivate
```
