"""
Commande de management pour peupler le champ CPU de tous les bons de commande existants.
Usage: python manage.py populate_cpu
"""
from django.core.management.base import BaseCommand
from orders.models import NumeroBonCommande


class Command(BaseCommand):
    help = 'Peuple le champ CPU pour tous les bons de commande existants'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force la mise à jour même si le CPU est déjà rempli',
        )

    def handle(self, *args, **options):
        force = options['force']
        
        self.stdout.write(self.style.WARNING('Début du peuplement du champ CPU...'))
        
        # Récupérer tous les bons de commande
        if force:
            bons = NumeroBonCommande.objects.all()
            self.stdout.write(f'Mode FORCE activé : traitement de {bons.count()} bons')
        else:
            bons = NumeroBonCommande.objects.filter(cpu__isnull=True) | NumeroBonCommande.objects.filter(cpu='')
            self.stdout.write(f'Traitement de {bons.count()} bons sans CPU')
        
        updated_count = 0
        skipped_count = 0
        error_count = 0
        
        for bon in bons:
            try:
                # Forcer la récupération du CPU depuis les fichiers
                cpu = bon.get_cpu(force_refresh=force)
                
                if cpu and cpu != "N/A":
                    self.stdout.write(f'  ✅ {bon.numero} → CPU: {cpu}')
                    updated_count += 1
                else:
                    self.stdout.write(self.style.WARNING(f'  ⚠️  {bon.numero} → CPU non trouvé'))
                    skipped_count += 1
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ❌ {bon.numero} → Erreur: {str(e)}'))
                error_count += 1
        
        # Résumé
        self.stdout.write(self.style.SUCCESS('\n' + '='*60))
        self.stdout.write(self.style.SUCCESS(f'✅ Bons mis à jour : {updated_count}'))
        self.stdout.write(self.style.WARNING(f'⚠️  Bons sans CPU : {skipped_count}'))
        self.stdout.write(self.style.ERROR(f'❌ Erreurs : {error_count}'))
        self.stdout.write(self.style.SUCCESS('='*60))
        
        if updated_count > 0:
            self.stdout.write(self.style.SUCCESS(f'\n🎉 Peuplement terminé avec succès !'))
        else:
            self.stdout.write(self.style.WARNING(f'\n⚠️  Aucun bon n\'a été mis à jour.'))
