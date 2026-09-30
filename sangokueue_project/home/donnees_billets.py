"""Jeu de billets pour peupler la base, en local comme en production.

Le numéro n'est pas généré. C'est la clé primaire ``numero_de_billet`` :
le visiteur le saisit tel quel sur l'accueil (``?billet=``) ou via
``/visiteur/<numero>/``. Les espaces autour sont ignorés, la casse est
conservée : ``H1`` et ``h1`` sont deux billets différents.

Le préfixe indique la priorité, puis un rang qui commence à 1 sans trou :

- ``Hn``  Humain (0)
- ``Sn``  Saiyan (1)
- ``SSn`` Super Saiyan (2)
"""

from home.models import Billet

VALIDITE_JOURS = 365

BILLETS = (
    ("H1", "Son", "Goku", Billet.Priorite.HUMAN),
    ("H2", "Krillin", "Brief", Billet.Priorite.HUMAN),
    ("H3", "Yamcha", "Desert", Billet.Priorite.HUMAN),
    ("H4", "Bulma", "Brief", Billet.Priorite.HUMAN),
    ("S1", "Raditz", "Son", Billet.Priorite.SAIYAN),
    ("S2", "Nappa", "Saiyan", Billet.Priorite.SAIYAN),
    ("S3", "Bardock", "Son", Billet.Priorite.SAIYAN),
    ("SS1", "Vegeta", "Prince", Billet.Priorite.SUPER_SAIYAN),
    ("SS2", "Gohan", "Son", Billet.Priorite.SUPER_SAIYAN),
    ("SS3", "Trunks", "Brief", Billet.Priorite.SUPER_SAIYAN),
)
