"""
Configuration de l'application `users` (AppConfig).

Déclare le nom lisible et connecte les signaux à l'initialisation.
"""
 
from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'users'
    verbose_name = 'Gestion des Utilisateurs'
    
    def ready(self):
        # Import des signaux si nécessaire
        import users.signals
