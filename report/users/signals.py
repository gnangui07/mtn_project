# Ce fichier contiendra les signaux liés aux utilisateurs
# Par exemple, pour créer automatiquement un profil utilisateur lors de la création d'un compte

from django.db.models.signals import post_save
from django.dispatch import receiver

# Les signaux seront implémentés lors de la migration des modèles
