FROM python:3.12-slim

# Dossier de travail du conteneur
WORKDIR /app

# Installation dépendances système
RUN apt-get update
COPY requirements.txt /app/
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

# Copie du projet dans le conteneur
COPY . /app/

# Exposition du port 8000
EXPOSE 8000

# Commande par défaut pour lancer l'application avec ASGI (nécessaire pour les WebSockets/Redis)
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "sangokueue_app.asgi:application"]