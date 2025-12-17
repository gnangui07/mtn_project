# Ce fichier contient les signaux liés aux utilisateurs
# Par exemple, pour invalider automatiquement le cache lors de modifications

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import User
import logging

logger = logging.getLogger(__name__)


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
