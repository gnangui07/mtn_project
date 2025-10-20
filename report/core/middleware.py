"""Middleware utilitaire pour exposer l'utilisateur courant aux couches basses.

Objectif
--------
Certains modèles ou utilitaires ont besoin de connaître l'utilisateur courant
pour tracer "qui" a modifié une donnée (ex: champs created_by / updated_by).
Ce middleware place l'utilisateur authentifié dans un stockage local au thread,
afin d'être récupérable en dehors du contexte direct de la requête.

Précautions
-----------
- Ne stockez que des références temporaires et nettoyez toujours après la
  réponse pour éviter des fuites entre requêtes.
- Assurez-vous d'ajouter ce middleware dans MIDDLEWARE si vous en dépendez.
"""

from threading import local
from django.conf import settings
from django.contrib.auth import logout
from django.contrib import messages
from django.shortcuts import redirect

# Stockage local au thread pour éviter le partage entre requêtes concurrentes
_thread_locals = local()


class UtilisateurActuelMiddleware:
    """Stocke l'utilisateur courant dans un thread local pendant la requête.

    Le modèle ou un signal peut récupérer l'utilisateur via `_thread_locals.user`
    pendant le cycle de vie de la requête HTTP en cours.
    """

    def __init__(self, get_response):
        # `get_response` est la prochaine callable dans la pile de middlewares
        self.get_response = get_response

    def __call__(self, request):
        # Injecte l'utilisateur s'il est disponible sur l'objet `request`
        _thread_locals.user = request.user if hasattr(request, 'user') else None

        # Ceinture et bretelles: si un utilisateur authentifié devient inactif,
        # on force la déconnexion et on redirige vers la page de connexion.
        try:
            if hasattr(request, 'user') and request.user.is_authenticated and not request.user.is_active:
                # Éviter la boucle sur la page de connexion
                login_path = settings.LOGIN_URL or '/connexion/'
                if request.path != login_path:
                    logout(request)
                    messages.warning(request, "Votre compte a été désactivé. Veuillez contacter l'administrateur.")
                   # Nettoyer le thread-local
                    _thread_locals.user = None
                    return redirect(login_path)
        except Exception:
            # En cas d'erreur inattendue, laisser le flux normal
            pass

        # Passe la main au reste de la pile de middlewares / vue
        response = self.get_response(request)

        # Nettoyage systématique pour ne pas polluer la requête suivante
        if hasattr(_thread_locals, 'user'):
            delattr(_thread_locals, 'user')

        return response


class NoCacheMiddleware:
    """
    Middleware qui ajoute des en-têtes anti-cache à toutes les réponses
    pour les utilisateurs authentifiés. Cela empêche le navigateur de mettre
    en cache les pages et donc empêche l'accès aux pages via le bouton retour
    après déconnexion.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        # Appliquer les en-têtes anti-cache pour toutes les pages
        # sauf les fichiers statiques et media
        if not request.path.startswith('/static/') and not request.path.startswith('/media/'):
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
        
        return response
