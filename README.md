# SanGoKueue

Projet web file virtuelle (Groupe 3)
Adel KHALDOUN, Niels LALIN, Rabah NINI, Kévin PETIT, Mattéo RIQUE

**Application web cross-platform de gestion de file virtuelle**

## Fonctionnalités clés : 
- Scan du QR code unique du billet de l’utilisateur pour le faire intégrer la file d’attente
- Gestion des priorités QoS pour appeler dans l’ordre : Super Saiyan quoi qu’il arrive, Saiyan pour leur garantir un temps d’attente inférieur à 30 minutes, Humain
- Envoi de notifications style push sur les smartphones des utilisateurs
- Possibilité pour les utilisateurs de quitter la file virtuelle à tout moment
- Interface staff pour mettre en pause ou vider la file en cas d’incident

## Fonctionnalités optionnelles : 
- Estimation du temps restant avant d’être appelé pour l’attraction
- Délai pour se présenter à l’entrée de l’attraction lorsque l’on est appelé (5 - 10 mn) sinon le visiteur est renvoyé au fond de la file d’attente
- Case à cocher pour certifier que le billet nominatif scanné est bien le nôtre
- Filtrage des visiteurs sur des données déclaratives : taille, âge, handicap

# Terminaisons API

## `POST /scan`

Scanne un ticket.

**Corps de la requête :**

```json
{
  "ticketId": "string"
}
```

---

## `POST /mapNewVisitor`

Associe un nouveau visiteur à un ticket.

**Corps de la requête :**

```json
{
  "ticketId": "string",
  "visitorId": "string"
}
```

---

## `POST /appendToQueue`

Ajoute un visiteur à une file d’attente.

**Corps de la requête :**

```json
{
  "visitorId": "string",
  "queue": "string"
}
```

---

## `POST /sendNotification`

Envoie une notification à un visiteur.

**Corps de la requête :**

```json
{
  "visitorPhoneNumber": "string",
  "message": "string"
}
```

---

## `DELETE /popFromQueue`

Retire le prochain visiteur d’une file d’attente.

**Paramètre :**

- `queue` : string

---

## `DELETE /clearQueue`

Vide une file d’attente.

**Paramètre :**

- `queue` : string

---

## `PATCH /pauseQueue`

Met en pause ou reprend une file d’attente.

**Corps de la requête :**

```json
{
  "queue": "string",
  "paused": true
}
```

---

## Résumé

| Méthode | Endpoint | Paramètres |
|---|---|---|
| `POST` | `/scan` | `ticketId` |
| `POST` | `/mapNewVisitor` | `ticketId`, `visitorId` |
| `POST` | `/appendToQueue` | `visitorId`, `queue` |
| `POST` | `/sendNotification` | `visitorPhoneNumber`, `message?` |
| `DELETE` | `/popFromQueue` | `queue` |
| `DELETE` | `/clearQueue` | `queue` |
| `PATCH` | `/pauseQueue` | `queue`, `paused` |


## Modèle de données : 

![Modèle de données](./modele_bdd.png)


## Pages de l’application : 

- Accueil avec scan appareil photo du QR code du billet
- Interface visiteur une fois le billet scanné avec temps estimé avant appel dans l’attraction et bouton pour pouvoir quitter la file
- Interface connexion staff avec identifiant et mot de passe sur une URL dédiée staff
- Interface gestion staff avec possibilité de mettre en pause la queue, de la vider, de supprimer certains visiteurs de la file d’attente



