"""Jeu de billets pour peupler la base, en local comme en production.

Le numéro est l'identifiant UUID du billet, le même format que celui
produit par ``creer_billet`` dans ``qr_code_generation`` :

    97fd2a68-3107-4e46-8b91-87f6a8c1ee10

Il est stocké tel quel dans ``numero_de_billet``.
"""

from home.models import Billet

VALIDITE_JOURS = 365

BILLETS = (
    ("97fd2a68-3107-4e46-8b91-87f6a8c1ee10", "Son", "Goku", Billet.Priorite.HUMAN),
    ("97578c83-0bf8-4780-a7bf-3fa9ed4a8132", "Krillin", "Brief", Billet.Priorite.HUMAN),
    ("36f789d0-3725-4bed-919a-ca6585675167", "Yamcha", "Desert", Billet.Priorite.HUMAN),
    ("8ca0b5d3-770e-417e-82df-1d3fa2b89a6b", "Bulma", "Brief", Billet.Priorite.HUMAN),
    ("6df52476-02cb-43da-b0a5-bbb478a60faa", "Raditz", "Son", Billet.Priorite.SAIYAN),
    ("56dfc6da-3b7e-4d1a-b7eb-b41d3fe61602", "Nappa", "Saiyan", Billet.Priorite.SAIYAN),
    ("090c5056-ac70-464e-984a-a0335d9c6d24", "Bardock", "Son", Billet.Priorite.SAIYAN),
    ("554ff296-5db4-4be4-8fd8-dcdad12aeaf6", "Vegeta", "Prince", Billet.Priorite.SUPER_SAIYAN),
    ("0455ca63-dd85-4d25-a890-4f7150d53e84", "Gohan", "Son", Billet.Priorite.SUPER_SAIYAN),
    ("9d291d0c-40f3-40e3-b383-07de80ada70f", "Trunks", "Brief", Billet.Priorite.SUPER_SAIYAN),
)
