# Ce fichier contient les signaux liés aux utilisateurs
# Par exemple, pour invalider automatiquement le cache lors de modifications

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from .models import User
from .models_history import PasswordHistory
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def save_password_history(sender, instance, created, **kwargs):
    """
    Sauvegarde le mot de passe dans l'historique lors d'un changement.
    """
    # Ne pas sauvegarder lors de la création initiale
    if created:
        return
    
    # Vérifier si le mot de passe a été changé
    if hasattr(instance, '_password_has_changed') and instance._password_has_changed:
        # Sauvegarder l'ancien mot de passe dans l'historique
        if hasattr(instance, '_original_password') and instance._original_password:
            PasswordHistory.objects.create(
                user=instance,
                password_hash=instance._original_password
            )
        
        # Mettre à jour la date de changement (sans déclencher le signal à nouveau)
        User.objects.filter(pk=instance.pk).update(password_changed_at=timezone.now())
        
        # Nettoyer les anciens mots de passe (garder seulement les 24 derniers)
        PasswordHistory.cleanup_old_passwords(instance, keep_count=24)
        
        # Réinitialiser le flag
        instance._password_has_changed = False


@receiver(post_save, sender=User)
def invalidate_user_cache_on_save(sender, instance, created, **kwargs):
    """
    Invalide le cache des permissions utilisateur après toute modification.
    
    Déclenché automatiquement par Django quand un User est créé ou modifié.
    Utilise Celery si disponible, sinon opère de manière synchrone.
    """
    if not created:  # Seulement pour les mises à jour, pas les créations
        try:
            from .tasks import invalidate_user_cache
            # Invalidation asynchrone via Celery
            invalidate_user_cache.delay(instance.id)
            logger.debug(f"Cache invalidation scheduled for user {instance.id}")
        except Exception as e:
            # Celery non disponible, invalidation synchrone
            try:
                from django.core.cache import cache
                cache_key = f"user_permissions_{instance.id}"
                cache.delete(cache_key)
                logger.debug(f"Cache invalidated synchronously for user {instance.id}")
            except Exception:
                pass  # Cache non disponible


@receiver(post_delete, sender=User)
def invalidate_user_cache_on_delete(sender, instance, **kwargs):
    """
    Supprime le cache des permissions quand un utilisateur est supprimé.
    """
    try:
        from django.core.cache import cache
        cache_key = f"user_permissions_{instance.id}"
        cache.delete(cache_key)
        logger.debug(f"Cache deleted for removed user {instance.id}")
    except Exception:
        pass  # Cache non disponible
