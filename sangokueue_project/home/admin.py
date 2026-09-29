from django.contrib import admin
from .models import Billet, EnFile, EtatFile

# Register your models here.
admin.site.register(Billet)
admin.site.register(EnFile)
admin.site.register(EtatFile)