"""Définition des routes pour l'application `core`.

Routes principales:
- ``/`` → redirection selon l'état d'authentification.
- ``/accueil/`` → page d'accueil protégée (auth requise).
"""

from django.urls import path
from . import views

# Espace de noms d'URL pour éviter les collisions entre apps
app_name = 'core'

urlpatterns = [
    # ``GET /``: redirige vers l'accueil si authentifié, sinon vers la page de connexion
    path('', views.RedirectionAccueilView.as_view(), name='redirection_accueil'),
    # ``GET /accueil/``: page d'accueil principale (nécessite d'être connecté)
    path('accueil/', views.AccueilView.as_view(), name='accueil'),
]
