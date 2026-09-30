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
    ("2b565b72-7766-4cf7-ac99-b700a26f1a34", "ChiChi", "Ox", Billet.Priorite.HUMAN),
    ("ceb6a026-6a0c-4637-b686-46e4e0462418", "Master", "Roshi", Billet.Priorite.HUMAN),
    ("fefbd032-4015-4f46-abd8-45ce99194056", "Tien", "Shinhan", Billet.Priorite.HUMAN),
    ("c83b9ab7-6778-4ea1-9801-487393643eca", "Chiaotzu", "Crane", Billet.Priorite.HUMAN),
    ("7efd3bfc-b23d-4915-b0a5-f2163e118e32", "Yajirobe", "Forest", Billet.Priorite.HUMAN),
    ("a373a21c-dd7b-4425-be8a-635a4f985b1a", "Oolong", "Shape", Billet.Priorite.HUMAN),
    ("91b609dc-adc7-4f52-b4b2-1d3ceee72bb6", "Puar", "Cat", Billet.Priorite.HUMAN),
    ("04556490-02c5-4d9b-9a9c-2cb83620a426", "Launch", "Blonde", Billet.Priorite.HUMAN),
    ("2bdd665e-3dd5-4fed-a6e5-9d2f3409b01b", "Videl", "Satan", Billet.Priorite.HUMAN),
    ("5f3033b9-c562-4092-ab3a-bdbcc2dcc4ae", "Hercule", "Satan", Billet.Priorite.HUMAN),
    ("72aa4a8c-1c02-440e-ad2f-21f1156de329", "Pan", "Son", Billet.Priorite.HUMAN),
    ("0f4d14e5-a842-43f7-a770-8c64edca2b7b", "Uub", "Earth", Billet.Priorite.HUMAN),
    ("9f0d6406-6a4c-4314-bebe-6744353d2247", "Android", "Lapis", Billet.Priorite.HUMAN),
    ("c981448f-5c15-4a3d-94c2-5504cdf6316a", "Android", "Lazuli", Billet.Priorite.HUMAN),
    ("70c6f0ee-81c0-4013-a0cf-692dd4af6f20", "Dr", "Briefs", Billet.Priorite.HUMAN),
    ("8c920206-783b-4bea-af12-9f5bd2f62873", "Panchy", "Brief", Billet.Priorite.HUMAN),
    ("a854bccf-a66f-40dd-9b99-03a7eb81208e", "Marron", "Lapis", Billet.Priorite.HUMAN),
    ("17645626-904e-49d1-be87-6994576362e9", "Bulla", "Brief", Billet.Priorite.HUMAN),
    ("6fabe74a-49c8-4229-9e53-9603be76cfc7", "Mai", "Pilaf", Billet.Priorite.HUMAN),
    ("b25261e4-2153-4a9b-9bd4-4d42008ced31", "Shu", "Pilaf", Billet.Priorite.HUMAN),
    ("bc00e36e-acc8-403e-911b-336790fdefd9", "Emperor", "Pilaf", Billet.Priorite.HUMAN),
    ("94ff6993-9b45-4356-a28c-3ca7d688984a", "Korin", "Tower", Billet.Priorite.HUMAN),
    ("137fa5e3-0a47-4d8e-8d37-56b109cf1143", "Yurin", "Crane", Billet.Priorite.HUMAN),
    ("4c59adc5-4895-4156-b172-5e56d501ec58", "Nam", "Tournament", Billet.Priorite.HUMAN),
    ("7e85e5e5-f197-4cd3-8201-81d394229eb1", "Bacterian", "Ring", Billet.Priorite.HUMAN),
    ("6c6d8b7a-040e-44ae-a00d-628f0ae398c5", "Ranfan", "Ring", Billet.Priorite.HUMAN),
    ("7b10e43a-5033-42f5-b62e-ec23eb37c25b", "Giran", "Earth", Billet.Priorite.HUMAN),
    ("d711e752-b092-4351-9c82-e22b932f3f41", "King", "Chappa", Billet.Priorite.HUMAN),
    ("554b7a7c-5fb6-4a10-a983-0762a01bc6c2", "Suno", "Jingle", Billet.Priorite.HUMAN),
    ("e784bafd-3fdb-4004-8e16-ce0cf0165fad", "Ox", "King", Billet.Priorite.HUMAN),
    ("2b4ad01f-4121-42b9-880d-19ac5c31b19d", "Grandpa", "Gohan", Billet.Priorite.HUMAN),
    ("c25bd34c-b00c-448a-9da6-b5f75a40966a", "Baba", "Fortuneteller", Billet.Priorite.HUMAN),
    ("78fed1b5-d1be-441d-86c8-1fa4ad1f0438", "Tarble", "Vegeta", Billet.Priorite.SAIYAN),
    ("c171a939-def4-4360-8748-fcb99e7238a5", "Gine", "Bardock", Billet.Priorite.SAIYAN),
    ("851ea0ff-83d8-4278-a980-55349f66e166", "Fasha", "Team", Billet.Priorite.SAIYAN),
    ("e8b1a190-5e41-4fbf-aa9e-19c2344137b4", "Tora", "Team", Billet.Priorite.SAIYAN),
    ("5d89dd96-e67c-4ce2-99a3-9dd4892e5229", "Borgos", "Team", Billet.Priorite.SAIYAN),
    ("87e4d18c-4840-4f32-acdf-6d4226be3640", "Shugesh", "Team", Billet.Priorite.SAIYAN),
    ("ff10a62a-1ffa-4431-a499-8240a2a663fc", "King", "Vegeta", Billet.Priorite.SAIYAN),
    ("6e23bb40-b65f-46e6-87f8-d49f44d12c22", "Paragus", "Broly", Billet.Priorite.SAIYAN),
    ("e4c78cda-8a91-46b7-8f86-dec02673f125", "Turles", "Tree", Billet.Priorite.SAIYAN),
    ("9198946e-c0df-4619-801f-dc2780871760", "Cabba", "Sadala", Billet.Priorite.SAIYAN),
    ("dffff6c4-c861-461c-a1d7-3bdaf5865c4e", "Renso", "Sadala", Billet.Priorite.SAIYAN),
    ("d910cb4b-964d-42ca-927d-cb3110a2d553", "Nion", "Sadala", Billet.Priorite.SAIYAN),
    ("616b74f1-6118-44cd-9854-9255d0e20b62", "Goten", "Son", Billet.Priorite.SUPER_SAIYAN),
    ("c03f4ed8-30e8-499c-a4c3-6d324b6e675d", "Broly", "Legendary", Billet.Priorite.SUPER_SAIYAN),
    ("8032a61a-f43d-42cd-99cb-0ef0a13f11eb", "Caulifla", "Sadala", Billet.Priorite.SUPER_SAIYAN),
    ("5c78aa44-dd5e-4c69-b141-aaaf21abec0c", "Kale", "Sadala", Billet.Priorite.SUPER_SAIYAN),
    ("5b01c54d-c05d-4e66-9b01-cd4cb53eaad4", "Kefla", "Fusion", Billet.Priorite.SUPER_SAIYAN),
    ("691ececd-42a5-4200-b4b2-3b31a6316bb0", "Gogeta", "Fusion", Billet.Priorite.SUPER_SAIYAN),
)
