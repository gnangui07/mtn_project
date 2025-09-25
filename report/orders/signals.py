from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Reception, NumeroBonCommande

@receiver([post_save, post_delete], sender=Reception)
def update_bon_commande_montants(sender, instance, **kwargs):
    """
    Met à jour les montants mis en cache dans NumeroBonCommande
    lorsqu'une réception est créée, modifiée ou supprimée.
    """
    if instance.bon_commande_id:
        try:
            bon = NumeroBonCommande.objects.get(pk=instance.bon_commande_id)
            bon._mettre_a_jour_montants()
        except NumeroBonCommande.DoesNotExist:
            pass
