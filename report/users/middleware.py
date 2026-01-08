"""
Middleware pour la gestion de l'expiration des mots de passe.
"""
from django.shortcuts import redirect
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta


class PasswordExpirationMiddleware:
    """
    Vérifie si le mot de passe de l'utilisateur a expiré (90 jours).
    Si expiré, force la redirection vers la page de changement.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Ne pas vérifier pour les utilisateurs non connectés
        if not request.user.is_authenticated:
            return self.get_response(request)
        
        # Ne pas vérifier pour les superusers sur les pages admin
        if request.path.startswith('/admin/'):
            return self.get_response(request)
        
        # Ne pas vérifier si déjà sur la page de changement de mot de passe ou déconnexion
        excluded_paths = [
            '/users/changement-password/',
            '/users/deconnexion/',
            '/users/activate/',
            '/users/confirm-password/',
        ]
        if any(request.path.startswith(path) for path in excluded_paths):
            return self.get_response(request)
        
        # Vérifier l'expiration du mot de passe (90 jours)
        if hasattr(request.user, 'password_changed_at') and request.user.password_changed_at:
            max_age = timedelta(days=90)
            time_since_change = timezone.now() - request.user.password_changed_at
            
            if time_since_change > max_age:
                messages.warning(
                    request,
                    "Votre mot de passe a expiré. Veuillez le changer."
                )
                return redirect('users:change_password')
        elif hasattr(request.user, 'password_changed_at') and not request.user.password_changed_at:
            # Nouvel utilisateur sans date de changement - forcer à changer
            messages.info(
                request,
                "Veuillez définir votre mot de passe."
            )
            return redirect('users:change_password')
        
        return self.get_response(request)
