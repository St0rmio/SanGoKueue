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

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["numero_de_billet", "nom_file"],
                name="unique_billet_dans_file",
            )
        ]