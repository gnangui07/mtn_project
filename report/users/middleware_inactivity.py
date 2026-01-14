"""
Middleware pour désactiver automatiquement les comptes utilisateurs inactifs.

Règles métier:
- Les utilisateurs standards (non-superusers) sont automatiquement désactivés après une période d'inactivité définie (configurée dans settings.INACTIVITY_DAYS)
- L'inactivité est mesurée par le champ 'last_login'
- Les superusers ne sont JAMAIS désactivés automatiquement
- Un message spécifique est affiché lors de la tentative de connexion d'un compte désactivé pour inactivité
"""
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.contrib import messages
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class InactivityDeactivationMiddleware:
    """
    Middleware qui vérifie et désactive automatiquement les comptes utilisateurs standards
    inactifs depuis plus de INACTIVITY_DAYS jours.
    
    Fonctionnement:
    1. Vérifie tous les utilisateurs connectés à chaque requête
    2. Si l'utilisateur est un standard (non-superuser) ET n'a pas de last_login OU 
       last_login > INACTIVITY_DAYS jours, désactive le compte
    3. Déconnecte l'utilisateur et affiche un message approprié
    4. Les superusers sont exemptés de cette règle
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        # Récupérer la durée d'inactivité depuis settings.py
        self.inactivity_days = getattr(settings, 'INACTIVITY_DAYS', 90)
    
    def __call__(self, request):
        # Vérifier uniquement pour les utilisateurs authentifiés
        if request.user.is_authenticated:
            # Les superusers ne sont JAMAIS désactivés automatiquement
            if not request.user.is_superuser:
                # Vérifier si le compte doit être désactivé pour inactivité
                should_deactivate, days_inactive = self._check_inactivity(request.user)
                
                if should_deactivate:
                    # Marquer la raison de désactivation
                    request.user.is_active = False
                    request.user.deactivation_reason = f'Inactivité de {days_inactive} jours (désactivation automatique)'
                    request.user.deactivated_at = timezone.now()
                    request.user.save(update_fields=['is_active', 'deactivation_reason', 'deactivated_at'])
                    
                    # Logger l'action
                    logger.warning(
                        f"Compte désactivé automatiquement pour inactivité: {request.user.email} "
                        f"({days_inactive} jours sans connexion)"
                    )
                    
                    # Déconnecter l'utilisateur
                    logout(request)
                    
                    # Message spécifique pour inactivité
                    messages.error(
                        request,
                        f"Votre compte a été verrouillé pour cause d'inactivité "
                        f"({days_inactive} jours sans connexion). "
                        f"Veuillez contacter un administrateur pour le réactiver."
                    )
                    
                    # Rediriger vers la page de connexion
                    return redirect('users:login')
        
        response = self.get_response(request)
        return response
    
    def _check_inactivity(self, user):
        """
        Vérifie si un utilisateur doit être désactivé pour inactivité.
        
        Args:
            user: Instance du modèle User
            
        Returns:
            tuple: (should_deactivate: bool, days_inactive: int)
        """
        # Si l'utilisateur n'a jamais été connecté (last_login est None)
        if user.last_login is None:
            # Vérifier depuis la date de création du compte
            if user.date_joined:
                time_since_creation = timezone.now() - user.date_joined
                days_inactive = time_since_creation.days
                
                # Désactiver si le compte n'a jamais été utilisé depuis plus de X jours
                if days_inactive > self.inactivity_days:
                    return True, days_inactive
            
            return False, 0
        
        # Calculer le temps depuis la dernière connexion
        time_since_login = timezone.now() - user.last_login
        days_inactive = time_since_login.days
        
        # Désactiver si inactif depuis plus de X jours (configuré dans settings)
        if days_inactive > self.inactivity_days:
            return True, days_inactive
        
        return False, days_inactive
