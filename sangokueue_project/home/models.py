from django.db import models

# Create your models here.
class Billet(models.Model):

    class Priorite(models.IntegerChoices):
        HUMAN = 0, "Human"
        SAIYAN = 1, "Saiyan"
        SUPER_SAIYAN = 2, "Super Saiyan"

    numero_de_billet = models.CharField(max_length=32, primary_key=True)
    date = models.DateField()
    prenom = models.CharField(max_length=30)
    nom = models.CharField(max_length=30)

    priorite = models.IntegerField(
        choices=Priorite.choices,
        default=Priorite.HUMAN
    )

class EnFile(models.Model):
    numero_de_billet = models.ForeignKey(Billet, on_delete=models.CASCADE)
    nom_file = models.CharField(max_length=64)
    date_entree = models.DateTimeField(auto_now_add=True)
    appele = models.BooleanField(default=False)
    deja_appele = models.BooleanField(default=False)
    date_appel = models.DateTimeField(null=True, blank=True)
    secondes_pause = models.PositiveIntegerField(default=0)
    secondes_pause_appel = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["numero_de_billet", "nom_file"],
                name="unique_billet_dans_file",
            )
        ]


class EtatFile(models.Model):
    nom_file = models.CharField(max_length=64, primary_key=True)
    en_pause = models.BooleanField(default=False)
    mise_en_pause_le = models.DateTimeField(null=True, blank=True)