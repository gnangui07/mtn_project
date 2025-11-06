"""
But:
- Mettre à jour automatiquement les montants d'un bon quand une Reception change.

Étapes:
1) Écouter post_save et post_delete sur Reception.
2) Retrouver le NumeroBonCommande et appeler son recalcul.

Entrées:
- Signal Django (post_save/post_delete) avec instance Reception.

Sorties:
- Aucune réponse: met à jour les champs du bon (effet de bord).
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Reception, NumeroBonCommande

@receiver([post_save, post_delete], sender=Reception)
def update_bon_commande_montants(sender, instance, **kwargs):
    """
    But:
    - Recalculer les montants du bon lié après création/modification/suppression d'une Reception.

    Étapes:
    1) Si la Reception a un bon_commande_id, charger le bon.
    2) Appeler _mettre_a_jour_montants() sur le bon.

    Entrées:
    - sender: modèle émetteur (Reception)
    - instance: instance de Reception sauvegardée/supprimée

    Sorties:
    - None (effet de bord sur le bon en base)
    """
    if instance.bon_commande_id:
        try:
            bon = NumeroBonCommande.objects.get(pk=instance.bon_commande_id)
            bon._mettre_a_jour_montants()
        except NumeroBonCommande.DoesNotExist:
            pass
