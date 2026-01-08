"""
Modèle pour l'historique des mots de passe.
"""
from django.db import models
from django.conf import settings
from django.utils import timezone


class PasswordHistory(models.Model):
    """
    Stocke l'historique des mots de passe hachés pour empêcher la réutilisation.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='password_history'
    )
    password_hash = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Historique de mot de passe"
        verbose_name_plural = "Historiques des mots de passe"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
        ]
    
    def __str__(self):
        return f"Mot de passe de {self.user.email} du {self.created_at.strftime('%d/%m/%Y %H:%M')}"
    
    @classmethod
    def is_password_reused(cls, user, password_hash, history_count=24):
        """
        Vérifie si le mot de passe a été utilisé dans les N derniers changements.
        
        Args:
            user: L'utilisateur concerné
            password_hash: Le hash du nouveau mot de passe
            history_count: Nombre de mots de passe à vérifier (défaut: 24)
        
        Returns:
            bool: True si le mot de passe a déjà été utilisé
        """
        # Récupérer les N derniers mots de passe
        recent_passwords = cls.objects.filter(
            user=user
        ).order_by('-created_at')[:history_count]
        
        # Vérifier si le hash existe dans l'historique
        return any(p.password_hash == password_hash for p in recent_passwords)
    
    @classmethod
    def cleanup_old_passwords(cls, user, keep_count=24):
        """
        Nettoie les anciens mots de passe en ne gardant que les N plus récents.
        
        Args:
            user: L'utilisateur concerné
            keep_count: Nombre de mots de passe à conserver (défaut: 24)
        """
        old_passwords = cls.objects.filter(
            user=user
        ).order_by('-created_at')[keep_count:]
        
        cls.objects.filter(id__in=old_passwords.values_list('id', flat=True)).delete()
