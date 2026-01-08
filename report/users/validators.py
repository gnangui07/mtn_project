"""
Validateurs personnalisés pour la sécurité des mots de passe.
"""
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.contrib.auth.hashers import make_password
import re
from .models_history import PasswordHistory


class ComplexityValidator:
    """
    Valide la complexité d'un mot de passe selon les exigences de sécurité:
    - Au moins une lettre majuscule
    - Au moins une lettre minuscule
    - Au moins un chiffre
    - Au moins un caractère spécial parmi (* @ ! - _ /)
    """
    
    def validate(self, password, user=None):
        """Valide que le mot de passe respecte les critères de complexité."""
        errors = []
        
        # Vérifier la présence d'au moins une majuscule
        if not re.search(r'[A-Z]', password):
            errors.append(_("Le mot de passe doit contenir au moins une lettre majuscule."))
        
        # Vérifier la présence d'au moins une minuscule
        if not re.search(r'[a-z]', password):
            errors.append(_("Le mot de passe doit contenir au moins une lettre minuscule."))
        
        # Vérifier la présence d'au moins un chiffre
        if not re.search(r'\d', password):
            errors.append(_("Le mot de passe doit contenir au moins un chiffre."))
        
        # Vérifier la présence d'au moins un caractère spécial
        if not re.search(r'[*@!\-_\/]', password):
            errors.append(_("Le mot de passe doit contenir au moins un caractère spécial (* @ ! - _ /)."))
        
        if errors:
            raise ValidationError(errors)
    
    def get_help_text(self):
        """Retourne le texte d'aide affiché à l'utilisateur."""
        return _(
            "Le mot de passe doit contenir au moins une lettre majuscule, "
            "une lettre minuscule, un chiffre et un caractère spécial (* @ ! - _ /)."
        )


class AdminPasswordValidator:
    """
    Valide que les mots de passe des administrateurs ont au moins 14 caractères.
    """
    
    def validate(self, password, user=None):
        """Valide la longueur minimale pour les administrateurs."""
        if user and user.is_superuser and len(password) < 14:
            raise ValidationError(
                _("Les administrateurs doivent avoir un mot d'au moins 14 caractères.")
            )
    
    def get_help_text(self):
        """Retourne le texte d'aide pour les administrateurs."""
        return _("Les administrateurs doivent utiliser un mot de passe d'au moins 14 caractères.")


class PasswordHistoryValidator:
    """
    Valide que le mot de passe n'a pas été utilisé dans les 24 derniers changements.
    """
    
    def validate(self, password, user=None):
        """Valide que le mot de passe n'est pas réutilisé."""
        if user and user.pk:
            # Créer le hash du mot de passe avec le format actuel
            password_hash = make_password(password)
            
            # Vérifier si le mot de passe a été utilisé récemment
            if PasswordHistory.is_password_reused(user, password_hash, history_count=24):
                raise ValidationError(
                    _("Le mot de passe doit être différent des 24 derniers mots de passe utilisés.")
                )
    
    def get_help_text(self):
        """Retourne le texte d'aide pour l'historique."""
        return _("Le mot de passe ne doit pas avoir été utilisé dans les 24 derniers changements.")


class PasswordAgeValidator:
    """
    Valide qu'il s'est écoulé au moins 1 jour depuis le dernier changement.
    """
    
    def validate(self, password, user=None):
        """Valide l'âge minimum du mot de passe."""
        # Ne pas appliquer lors de la première activation (pas de password_changed_at)
        if user and user.pk and hasattr(user, 'password_changed_at') and user.password_changed_at:
            from datetime import timedelta
            min_age = timedelta(days=1)
            time_since_change = timezone.now() - user.password_changed_at
            
            if time_since_change < min_age:
                raise ValidationError(
                    _("Vous devez attendre au moins 1 jour avant de changer à nouveau votre mot de passe.")
                )
    
    def get_help_text(self):
        """Retourne le texte d'aide pour l'âge minimum."""
        return _("Un délai d'au moins 1 jour est requis entre les changements de mot de passe.")
