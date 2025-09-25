"""Configuration de l'application `core`.

Ce module déclare la configuration de l'app pour Django. C'est ici que l'on peut
initialiser des signaux, des vérifications ou tout bootstrap spécifique à l'app.
"""

from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Config de l'app `core`.

    - default_auto_field: utilise par défaut des BigAutoField pour les PK.
    - verbose_name: nom lisible dans l'admin.
    - ready(): point d'entrée d'initialisation (ex: import des signaux).
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    verbose_name = 'Fonctionnalités de Base'
    
    def ready(self):
        """Méthode appelée au démarrage du projet.

        Utilisez cette méthode pour connecter des signaux si besoin :
        ```python
        from . import signals  # noqa: F401
        ```
        L'import évite les import circulaires en ne chargeant les signaux
        qu'au démarrage de l'app.
        """
        # Import des signaux si nécessaire (laisser commenté si non utilisé)
        # from . import signals  # noqa: F401
        pass
