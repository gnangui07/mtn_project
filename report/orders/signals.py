"""
Signaux Django pour l'application orders.

But:
- Mettre à jour automatiquement les montants d'un bon quand une Reception change.
- Invalider le cache Redis quand les données changent.

Étapes:
1) Écouter post_save et post_delete sur Reception et NumeroBonCommande.
2) Retrouver le NumeroBonCommande et appeler son recalcul.
3) Invalider le cache correspondant via Celery (async).

Entrées:
- Signal Django (post_save/post_delete) avec instance.

Sorties:
- Aucune réponse: met à jour les champs du bon et invalide le cache (effet de bord).
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Reception, NumeroBonCommande
import logging

logger = logging.getLogger(__name__)


@receiver([post_save, post_delete], sender=Reception)
def update_bon_commande_montants(sender, instance, **kwargs):
    """
    Recalcule les montants du bon lié après création/modification/suppression d'une Reception.
    Invalide également le cache Redis du bon.
    """
    if instance.bon_commande_id:
        try:
            bon = NumeroBonCommande.objects.get(pk=instance.bon_commande_id)
            bon._mettre_a_jour_montants()
            
            # Invalider le cache via Celery (async, non-bloquant)
            try:
                from .tasks import invalidate_bon_cache
                invalidate_bon_cache.delay(instance.bon_commande_id)
            except Exception:
                # Celery non disponible, invalider de façon synchrone
                try:
                    from django.core.cache import cache
                    cache.delete(f"bon_details_{instance.bon_commande_id}")
                    cache.delete(f"bon_receptions_{instance.bon_commande_id}")
                except Exception:
                    pass
                    
        except NumeroBonCommande.DoesNotExist:
            pass


@receiver(post_save, sender=NumeroBonCommande)
def invalidate_bon_cache_on_save(sender, instance, created, **kwargs):
    """
    Invalide le cache du bon de commande après modification.
    """
    if not created:  # Seulement pour les mises à jour
        try:
            from .tasks import invalidate_bon_cache, invalidate_service_cache
            invalidate_bon_cache.delay(instance.id)
            
            # Invalider aussi le cache du service
            if instance.service:
                invalidate_service_cache.delay(instance.service)
        except Exception:
            # Fallback synchrone
            try:
                from django.core.cache import cache
                cache.delete(f"bon_details_{instance.id}")
                if instance.service:
                    cache.delete(f"bons_service_{instance.service}")
            except Exception:
                pass


@receiver(post_delete, sender=NumeroBonCommande)
def invalidate_bon_cache_on_delete(sender, instance, **kwargs):
    """
    Supprime le cache du bon de commande quand il est supprimé.
    """
    try:
        from django.core.cache import cache
        cache.delete(f"bon_details_{instance.id}")
        cache.delete(f"bon_receptions_{instance.id}")
        cache.delete(f"bon_lignes_{instance.id}")
        
        if instance.service:
            cache.delete(f"bons_service_{instance.service}")
    except Exception:
        pass
