from django.core.management.base import BaseCommand
from django.db.models import Count, Min
from orders.models import ActivityLog, NumeroBonCommande
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Met à jour les taux d\'avancement historiques pour les logs d\'activité existants'

    def handle(self, *args, **options):
        self.stdout.write('Mise à jour des taux d\'avancement historiques...')
        
        # Récupérer tous les bons de commande qui ont des logs d'activité
        bon_commandes = set(ActivityLog.objects.values_list('bon_commande', flat=True).distinct())
        
        total_updated = 0
        
        for bon_number in bon_commandes:
            try:
                # Récupérer tous les logs pour ce bon de commande, triés par date
                logs = ActivityLog.objects.filter(bon_commande=bon_number).order_by('action_date')
                
                if not logs.exists():
                    continue
                
                # Récupérer le bon de commande
                try:
                    bon_commande = NumeroBonCommande.objects.get(numero=bon_number)
                except NumeroBonCommande.DoesNotExist:
                    self.stdout.write(self.style.WARNING(f'Bon de commande {bon_number} non trouvé'))
                    continue
                
                # Calculer le taux d'avancement actuel
                taux_final = bon_commande.taux_avancement()
                
                # Nombre total de logs pour ce bon de commande
                total_logs = logs.count()
                
                if total_logs == 0:
                    continue
                
                # Calculer un taux progressif pour chaque log
                for i, log in enumerate(logs):
                    # Le taux est proportionnel à la position du log dans la chronologie
                    progress_rate = (i + 1) / total_logs * taux_final
                    
                    # Mettre à jour le log avec ce taux
                    log.progress_rate = progress_rate
                    log.save(update_fields=['progress_rate'])
                    total_updated += 1
                
                self.stdout.write(f'Mis à jour {total_logs} logs pour le bon {bon_number}')
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Erreur lors de la mise à jour du bon {bon_number}: {str(e)}'))
        
        self.stdout.write(self.style.SUCCESS(f'Mise à jour terminée. {total_updated} logs mis à jour.'))
