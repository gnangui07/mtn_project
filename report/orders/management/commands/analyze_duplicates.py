from django.core.management.base import BaseCommand
from orders.models import LigneFichier, Reception, normalize_business_id
from collections import defaultdict, Counter


class Command(BaseCommand):
    help = 'Analyse les doublons de business_id dans la base de données'

    def add_arguments(self, parser):
        parser.add_argument(
            '--detailed',
            action='store_true',
            help='Affichage détaillé des doublons',
        )

    def handle(self, *args, **options):
        detailed = options['detailed']
        
        self.stdout.write(self.style.SUCCESS('=== Analyse des doublons de business_id ===\n'))
        
        self.analyze_ligne_fichier_duplicates(detailed)
        self.analyze_reception_duplicates(detailed)
        self.analyze_cross_table_consistency()

    def analyze_ligne_fichier_duplicates(self, detailed):
        """Analyse les doublons dans LigneFichier"""
        self.stdout.write('📄 Analyse des LigneFichier:')
        
        lignes = LigneFichier.objects.exclude(business_id__isnull=True).exclude(business_id='')
        total_lignes = lignes.count()
        
        # Grouper par business_id original
        original_groups = defaultdict(list)
        for ligne in lignes:
            original_groups[ligne.business_id].append(ligne)
        
        original_duplicates = sum(1 for group in original_groups.values() if len(group) > 1)
        original_duplicate_count = sum(len(group) - 1 for group in original_groups.values() if len(group) > 1)
        
        # Grouper par business_id normalisé
        normalized_groups = defaultdict(list)
        normalization_changes = 0
        
        for ligne in lignes:
            original_id = ligne.business_id
            normalized_id = normalize_business_id(original_id)
            normalized_groups[normalized_id].append(ligne)
            
            if original_id != normalized_id:
                normalization_changes += 1
        
        normalized_duplicates = sum(1 for group in normalized_groups.values() if len(group) > 1)
        normalized_duplicate_count = sum(len(group) - 1 for group in normalized_groups.values() if len(group) > 1)
        
        self.stdout.write(f'  • Total de lignes: {total_lignes}')
        self.stdout.write(f'  • Business_id uniques (original): {len(original_groups)}')
        self.stdout.write(f'  • Business_id uniques (normalisé): {len(normalized_groups)}')
        self.stdout.write(f'  • Changements après normalisation: {normalization_changes}')
        self.stdout.write(f'  • Groupes dupliqués (original): {original_duplicates}')
        self.stdout.write(f'  • Groupes dupliqués (normalisé): {normalized_duplicates}')
        self.stdout.write(f'  • Doublons à supprimer (original): {original_duplicate_count}')
        self.stdout.write(f'  • Doublons à supprimer (normalisé): {normalized_duplicate_count}')
        
        if detailed and normalized_duplicates > 0:
            self.stdout.write('\n  📋 Détail des doublons (après normalisation):')
            for normalized_id, lignes_group in normalized_groups.items():
                if len(lignes_group) > 1:
                    self.stdout.write(f'\n    🔸 {normalized_id} ({len(lignes_group)} occurrences):')
                    for ligne in lignes_group:
                        self.stdout.write(f'      - Ligne {ligne.id} (fichier {ligne.fichier.id}, créée le {ligne.date_creation})')

    def analyze_reception_duplicates(self, detailed):
        """Analyse les doublons dans Reception"""
        self.stdout.write('\n📦 Analyse des Reception:')
        
        receptions = Reception.objects.exclude(business_id__isnull=True).exclude(business_id='')
        total_receptions = receptions.count()
        
        # Grouper par business_id original
        original_groups = defaultdict(list)
        for reception in receptions:
            original_groups[reception.business_id].append(reception)
        
        original_duplicates = sum(1 for group in original_groups.values() if len(group) > 1)
        original_duplicate_count = sum(len(group) - 1 for group in original_groups.values() if len(group) > 1)
        
        # Grouper par business_id normalisé
        normalized_groups = defaultdict(list)
        normalization_changes = 0
        
        for reception in receptions:
            original_id = reception.business_id
            normalized_id = normalize_business_id(original_id)
            normalized_groups[normalized_id].append(reception)
            
            if original_id != normalized_id:
                normalization_changes += 1
        
        normalized_duplicates = sum(1 for group in normalized_groups.values() if len(group) > 1)
        normalized_duplicate_count = sum(len(group) - 1 for group in normalized_groups.values() if len(group) > 1)
        
        self.stdout.write(f'  • Total de réceptions: {total_receptions}')
        self.stdout.write(f'  • Business_id uniques (original): {len(original_groups)}')
        self.stdout.write(f'  • Business_id uniques (normalisé): {len(normalized_groups)}')
        self.stdout.write(f'  • Changements après normalisation: {normalization_changes}')
        self.stdout.write(f'  • Groupes dupliqués (original): {original_duplicates}')
        self.stdout.write(f'  • Groupes dupliqués (normalisé): {normalized_duplicates}')
        self.stdout.write(f'  • Doublons à fusionner (original): {original_duplicate_count}')
        self.stdout.write(f'  • Doublons à fusionner (normalisé): {normalized_duplicate_count}')
        
        if detailed and normalized_duplicates > 0:
            self.stdout.write('\n  📋 Détail des doublons (après normalisation):')
            for normalized_id, receptions_group in normalized_groups.items():
                if len(receptions_group) > 1:
                    self.stdout.write(f'\n    🔸 {normalized_id} ({len(receptions_group)} occurrences):')
                    total_qty_delivered = sum(r.quantity_delivered for r in receptions_group)
                    total_received_qty = sum(r.received_quantity for r in receptions_group)
                    
                    for reception in receptions_group:
                        self.stdout.write(f'      - Réception {reception.id} (BC: {reception.bon_commande.numero})')
                        self.stdout.write(f'        Qty delivered: {reception.quantity_delivered}, Received: {reception.received_quantity}')
                    
                    self.stdout.write(f'      → Total après fusion: Delivered={total_qty_delivered}, Received={total_received_qty}')

    def analyze_cross_table_consistency(self):
        """Analyse la cohérence entre LigneFichier et Reception"""
        self.stdout.write('\n🔗 Analyse de cohérence entre tables:')
        
        # Récupérer tous les business_id normalisés
        ligne_business_ids = set()
        for ligne in LigneFichier.objects.exclude(business_id__isnull=True).exclude(business_id=''):
            ligne_business_ids.add(normalize_business_id(ligne.business_id))
        
        reception_business_ids = set()
        for reception in Reception.objects.exclude(business_id__isnull=True).exclude(business_id=''):
            reception_business_ids.add(normalize_business_id(reception.business_id))
        
        # Analyser les différences
        only_in_lignes = ligne_business_ids - reception_business_ids
        only_in_receptions = reception_business_ids - ligne_business_ids
        in_both = ligne_business_ids & reception_business_ids
        
        self.stdout.write(f'  • Business_id dans LigneFichier: {len(ligne_business_ids)}')
        self.stdout.write(f'  • Business_id dans Reception: {len(reception_business_ids)}')
        self.stdout.write(f'  • Business_id communs: {len(in_both)}')
        self.stdout.write(f'  • Seulement dans LigneFichier: {len(only_in_lignes)}')
        self.stdout.write(f'  • Seulement dans Reception: {len(only_in_receptions)}')
        
        if only_in_lignes:
            self.stdout.write(f'\n  ⚠️  {len(only_in_lignes)} business_id présents dans LigneFichier mais pas dans Reception')
        
        if only_in_receptions:
            self.stdout.write(f'  ⚠️  {len(only_in_receptions)} business_id présents dans Reception mais pas dans LigneFichier')
        
        # Recommandations
        self.stdout.write('\n💡 Recommandations:')
        if only_in_lignes or only_in_receptions:
            self.stdout.write('  • Vérifier la cohérence des données entre les tables')
        
        total_duplicates = (
            sum(len(group) - 1 for group in defaultdict(list, {
                normalize_business_id(l.business_id): [] for l in 
                LigneFichier.objects.exclude(business_id__isnull=True).exclude(business_id='')
            }).values() if len(group) > 1) +
            sum(len(group) - 1 for group in defaultdict(list, {
                normalize_business_id(r.business_id): [] for r in 
                Reception.objects.exclude(business_id__isnull=True).exclude(business_id='')
            }).values() if len(group) > 1)
        )
        
        if total_duplicates > 0:
            self.stdout.write('  • Exécuter la commande normalize_business_ids pour corriger les doublons')
            self.stdout.write('    python manage.py normalize_business_ids --dry-run  # Pour prévisualiser')
            self.stdout.write('    python manage.py normalize_business_ids            # Pour appliquer')
        else:
            self.stdout.write('  • Aucun doublon détecté - la base de données est cohérente')
