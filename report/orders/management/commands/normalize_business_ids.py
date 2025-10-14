from django.core.management.base import BaseCommand
from django.db import transaction
from orders.models import LigneFichier, Reception, normalize_business_id
from collections import defaultdict


class Command(BaseCommand):
    help = 'Normalise les business_id existants et supprime les doublons'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Affiche les changements sans les appliquer',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Affichage détaillé des opérations',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        verbose = options['verbose']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('Mode DRY-RUN activé - Aucune modification ne sera appliquée'))
        
        self.normalize_ligne_fichier_business_ids(dry_run, verbose)
        self.normalize_reception_business_ids(dry_run, verbose)
        
        if not dry_run:
            self.stdout.write(self.style.SUCCESS('Normalisation terminée avec succès'))
        else:
            self.stdout.write(self.style.WARNING('DRY-RUN terminé - Exécutez sans --dry-run pour appliquer les changements'))

    def normalize_ligne_fichier_business_ids(self, dry_run, verbose):
        """Normalise les business_id des LigneFichier et supprime les doublons"""
        self.stdout.write('\n=== Normalisation des LigneFichier ===')
        
        # Récupérer toutes les lignes avec business_id
        lignes = LigneFichier.objects.exclude(business_id__isnull=True).exclude(business_id='')
        total_lignes = lignes.count()
        
        self.stdout.write(f'Traitement de {total_lignes} lignes de fichier...')
        
        # Grouper par business_id normalisé
        normalized_groups = defaultdict(list)
        updates_needed = []
        
        for ligne in lignes:
            original_id = ligne.business_id
            normalized_id = normalize_business_id(original_id)
            
            if original_id != normalized_id:
                updates_needed.append((ligne, original_id, normalized_id))
            
            normalized_groups[normalized_id].append(ligne)
        
        # Afficher les mises à jour nécessaires
        if updates_needed:
            self.stdout.write(f'\n{len(updates_needed)} business_id à normaliser:')
            for ligne, original, normalized in updates_needed[:10]:  # Afficher les 10 premiers
                if verbose:
                    self.stdout.write(f'  Ligne {ligne.id}: {original} -> {normalized}')
            
            if len(updates_needed) > 10:
                self.stdout.write(f'  ... et {len(updates_needed) - 10} autres')
        
        # Identifier les doublons après normalisation
        duplicates_found = 0
        for normalized_id, lignes_group in normalized_groups.items():
            if len(lignes_group) > 1:
                duplicates_found += len(lignes_group) - 1
                if verbose:
                    self.stdout.write(f'\nDoublon détecté pour {normalized_id}:')
                    for ligne in lignes_group:
                        self.stdout.write(f'  - Ligne {ligne.id} (fichier {ligne.fichier.id})')
        
        if duplicates_found > 0:
            self.stdout.write(f'\n{duplicates_found} doublons détectés après normalisation')
        
        if not dry_run and (updates_needed or duplicates_found > 0):
            with transaction.atomic():
                # Mettre à jour les business_id
                for ligne, original, normalized in updates_needed:
                    ligne.business_id = normalized
                    ligne.save(update_fields=['business_id'])
                
                # Supprimer les doublons (garder le plus récent)
                for normalized_id, lignes_group in normalized_groups.items():
                    if len(lignes_group) > 1:
                        # Trier par date de création (plus récent en premier)
                        lignes_sorted = sorted(lignes_group, key=lambda x: x.date_creation, reverse=True)
                        lignes_to_delete = lignes_sorted[1:]  # Supprimer tous sauf le plus récent
                        
                        for ligne in lignes_to_delete:
                            if verbose:
                                self.stdout.write(f'Suppression du doublon: Ligne {ligne.id}')
                            ligne.delete()
            
            self.stdout.write(self.style.SUCCESS(f'✓ {len(updates_needed)} business_id normalisés'))
            self.stdout.write(self.style.SUCCESS(f'✓ {duplicates_found} doublons supprimés'))

    def normalize_reception_business_ids(self, dry_run, verbose):
        """Normalise les business_id des Reception et supprime les doublons"""
        self.stdout.write('\n=== Normalisation des Reception ===')
        
        # Récupérer toutes les réceptions avec business_id
        receptions = Reception.objects.exclude(business_id__isnull=True).exclude(business_id='')
        total_receptions = receptions.count()
        
        self.stdout.write(f'Traitement de {total_receptions} réceptions...')
        
        # Grouper par business_id normalisé
        normalized_groups = defaultdict(list)
        updates_needed = []
        
        for reception in receptions:
            original_id = reception.business_id
            normalized_id = normalize_business_id(original_id)
            
            if original_id != normalized_id:
                updates_needed.append((reception, original_id, normalized_id))
            
            normalized_groups[normalized_id].append(reception)
        
        # Afficher les mises à jour nécessaires
        if updates_needed:
            self.stdout.write(f'\n{len(updates_needed)} business_id à normaliser:')
            for reception, original, normalized in updates_needed[:10]:  # Afficher les 10 premiers
                if verbose:
                    self.stdout.write(f'  Réception {reception.id}: {original} -> {normalized}')
            
            if len(updates_needed) > 10:
                self.stdout.write(f'  ... et {len(updates_needed) - 10} autres')
        
        # Identifier les doublons après normalisation
        duplicates_found = 0
        for normalized_id, receptions_group in normalized_groups.items():
            if len(receptions_group) > 1:
                duplicates_found += len(receptions_group) - 1
                if verbose:
                    self.stdout.write(f'\nDoublon détecté pour {normalized_id}:')
                    for reception in receptions_group:
                        self.stdout.write(f'  - Réception {reception.id} (BC: {reception.bon_commande.numero})')
        
        if duplicates_found > 0:
            self.stdout.write(f'\n{duplicates_found} doublons détectés après normalisation')
        
        if not dry_run and (updates_needed or duplicates_found > 0):
            with transaction.atomic():
                # Mettre à jour les business_id
                for reception, original, normalized in updates_needed:
                    reception.business_id = normalized
                    reception.save(update_fields=['business_id'])
                
                # Fusionner les doublons (additionner les quantités)
                for normalized_id, receptions_group in normalized_groups.items():
                    if len(receptions_group) > 1:
                        # Trier par date de modification (plus récent en premier)
                        receptions_sorted = sorted(receptions_group, key=lambda x: x.date_modification, reverse=True)
                        main_reception = receptions_sorted[0]  # Garder la plus récente
                        receptions_to_merge = receptions_sorted[1:]  # Fusionner les autres
                        
                        # Additionner les quantités
                        for reception in receptions_to_merge:
                            main_reception.quantity_delivered += reception.quantity_delivered
                            main_reception.received_quantity += reception.received_quantity
                            if verbose:
                                self.stdout.write(f'Fusion de la réception {reception.id} dans {main_reception.id}')
                            reception.delete()
                        
                        # Sauvegarder la réception principale avec les nouvelles quantités
                        main_reception.save()
            
            self.stdout.write(self.style.SUCCESS(f'✓ {len(updates_needed)} business_id normalisés'))
            self.stdout.write(self.style.SUCCESS(f'✓ {duplicates_found} doublons fusionnés'))
