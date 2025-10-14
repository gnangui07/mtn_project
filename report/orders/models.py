import os
import tempfile
import json
from django.db import models
from django.utils import timezone
from django.core.files.storage import default_storage
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import logging
logger = logging.getLogger(__name__)

# Nouvelle fonction pour arrondir les décimales
def round_decimal(value, places=2):
    """
    Arrondit une valeur décimale au nombre de décimales spécifié.
    :param value: La valeur à arrondir (Decimal, float, int ou str)
    :param places: Nombre de décimales (par défaut 2)
    :return: Decimal arrondi
    """
    if value is None:
        return Decimal('0')
    if not isinstance(value, Decimal):
        try:
            value = Decimal(str(value))
        except InvalidOperation:
            return Decimal('0')
    # Format de quantification basé sur le nombre de décimales
    quant_format = Decimal('0.' + ('0' * (places-1)) + '1') if places > 0 else Decimal('1')
    return value.quantize(quant_format, rounding=ROUND_HALF_UP)

# Fonction utilitaire pour normaliser les business_id
def normalize_business_id(business_id):
    """
    Normalise un business_id en convertissant les valeurs numériques décimales en entiers
    pour éviter les doublons (ex: 43.0 -> 43)
    """
    if not business_id:
        return business_id
    
    parts = business_id.split('|')
    normalized_parts = []
    
    for part in parts:
        if ':' in part:
            key, value = part.split(':', 1)
            try:
                # Essayer de convertir en float puis supprimer les .0 inutiles
                float_val = float(value)
                if float_val.is_integer():
                    value = str(int(float_val))
            except (ValueError, TypeError):
                # Garder la valeur originale si conversion impossible
                pass
            normalized_parts.append(f"{key}:{value}")
        else:
            normalized_parts.append(part)
    
    return '|'.join(normalized_parts)

# Utiliser le JSONField standard de Django au lieu de celui spécifique à PostgreSQL
# Ce champ est disponible dans Django depuis la version 3.1


class NumeroBonCommande(models.Model):
    """
    Modèle stockant de façon unique les numéros de bons de commande
    extraits des fichiers importés (colonne 'ORDER').
    """
    numero = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Numéro de bon de commande"
    )
    
    # Champs de cache pour les montants
    _montant_total = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0,
        db_column='montant_total',
        verbose_name="Montant total (cache)"
    )
    _montant_recu = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0,
        db_column='montant_recu',
        verbose_name="Montant reçu (cache)"
    )
    _taux_avancement = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0,
        db_column='taux_avancement',
        verbose_name="Taux d'avancement (cache)"
    )
    date_creation = models.DateTimeField(
        default=timezone.now,
        verbose_name="Date de création"
    )
    fichiers = models.ManyToManyField(
        'FichierImporte',
        related_name='bons_commande',
        verbose_name="Fichiers associés"
    )
    retention_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0,
        verbose_name="Taux de rétention (%)"
    )
    retention_cause = models.TextField(
        null=True,
        blank=True,
        verbose_name="Cause de la rétention"
    )
    
    class Meta:
        verbose_name = "Numéro de bon de commande"
        verbose_name_plural = "Numéros de bons de commande"
        ordering = ['-date_creation']
    
    def montant_total(self):
        receptions = Reception.objects.filter(bon_commande_id=self.id)
        montant = Decimal(0)
        print(f"[DEBUG] Calcul montant_total pour bon_commande_id={self.id}")
        for rec in receptions:
            ligne_montant = rec.ordered_quantity * rec.unit_price
            ligne_montant = round_decimal(ligne_montant, places=2)  # Arrondir à 2 décimales
            print(f"  Reception id={rec.id} : ordered_quantity={rec.ordered_quantity}, unit_price={rec.unit_price}, montant={ligne_montant}")
            montant += ligne_montant
        print(f"[DEBUG] Montant total pour bon_commande_id={self.id} : {montant}")
        return montant

    def montant_recu(self):
        receptions = Reception.objects.filter(bon_commande_id=self.id)
        montant = Decimal(0)
        print(f"[DEBUG] Calcul montant_recu pour bon_commande_id={self.id}")
        for rec in receptions:
            ligne_montant = rec.quantity_delivered * rec.unit_price
            ligne_montant = round_decimal(ligne_montant, places=2)  # Arrondir à 2 décimales
            print(f"  Reception id={rec.id} : quantity={rec.quantity_delivered}, unit_price={rec.unit_price}, montant={ligne_montant}")
            montant += ligne_montant
        print(f"[DEBUG] Montant total reçu pour bon_commande_id={self.id} : {montant}")
        return montant

    def taux_avancement(self):
        """Retourne le taux d'avancement en pourcentage (calculé ou depuis le cache)"""
        if not hasattr(self, '_taux_avancement_calculated'):
            self._mettre_a_jour_montants()
        return self._taux_avancement
        
    def _mettre_a_jour_montants(self):
        """Met à jour les montants en cache"""
        from django.db import transaction
        
        # Calculer les nouvelles valeurs
        montant_total = Decimal('0')
        montant_recu = Decimal('0')
        
        # Récupérer toutes les réceptions en une seule requête
        receptions = self.receptions.all()
        
        for rec in receptions:
            # Arrondir chaque montant partiel à 2 décimales
            montant_ligne_total = round_decimal((rec.ordered_quantity or Decimal('0')) * (rec.unit_price or Decimal('0')), places=2)
            montant_ligne_recu = round_decimal((rec.quantity_delivered or Decimal('0')) * (rec.unit_price or Decimal('0')), places=2)
            
            montant_total += montant_ligne_total
            montant_recu += montant_ligne_recu
        
        # Calculer le taux d'avancement
        taux_avancement = (montant_recu / montant_total * 100) if montant_total > 0 else Decimal('0')
        taux_avancement = round_decimal(taux_avancement, places=2)  # Arrondir le taux à 2 décimales
        
        # Mettre à jour les champs en cache
        self._montant_total = montant_total
        self._montant_recu = montant_recu
        self._taux_avancement = taux_avancement
        
        # Marquer comme calculé
        self._montant_total_calculated = True
        self._montant_recu_calculated = True
        self._taux_avancement_calculated = True
        
        # Sauvegarder en base de données
        try:
            with transaction.atomic():
                NumeroBonCommande.objects.filter(pk=self.pk).update(
                    _montant_total=montant_total,
                    _montant_recu=montant_recu,
                    _taux_avancement=taux_avancement
                )
        except Exception as e:
            print(f"[ERREUR] Impossible de mettre à jour les montants pour le bon {self.numero}: {e}")
    
    def montant_total(self):
        """Retourne le montant total (calculé ou depuis le cache)"""
        if not hasattr(self, '_montant_total_calculated'):
            self._mettre_a_jour_montants()
        return self._montant_total
    
    def montant_recu(self):
        """Retourne le montant reçu (calculé ou depuis le cache)"""
        if not hasattr(self, '_montant_recu_calculated'):
            self._mettre_a_jour_montants()
        return self._montant_recu

    def get_sponsor(self):
        """Récupère le sponsor depuis les lignes correspondant au bon de commande"""
        if not self.fichiers.exists():
            return "N/A"

        for fichier in self.fichiers.all():
            for ligne in fichier.lignes.all():
                contenu = ligne.contenu
            
                # Trouver la clé pour le numéro de commande
                order_key = None
                for key in contenu.keys():
                    key_lower = key.lower() if key else ''
                    if 'order' in key_lower or 'commande' in key_lower or 'bon' in key_lower or 'bc' in key_lower:
                        order_key = key
                        break
            
                # Vérifier si cette ligne appartient à ce bon de commande
                if order_key and str(contenu.get(order_key, '')).strip() == str(self.numero):
                    # Chercher la colonne Sponsor dans la même ligne
                    for key, value in contenu.items():
                        if not key:
                            continue
                        norm = key.strip().lower().replace('_', ' ')
                        norm = ' '.join(norm.split())
                        if 'sponsor' in norm and value:
                            return str(value)
        return "N/A"

    def get_supplier(self):
        """Récupère le fournisseur depuis les lignes correspondant au bon de commande"""
        if not self.fichiers.exists():
            return "N/A"
        # Parcourir tous les fichiers associés
        for fichier in self.fichiers.all():
            # Chercher dans toutes les lignes du fichier
            for ligne in fichier.lignes.all():
                contenu = ligne.contenu
                
                # Trouver la clé pour le numéro de commande
                order_key = None
                for key in contenu.keys():
                    key_lower = key.lower() if key else ''
                    if 'order' in key_lower or 'commande' in key_lower or 'bon' in key_lower or 'bc' in key_lower:
                        order_key = key
                        break
                
                # Vérifier si cette ligne appartient à ce bon de commande
                if order_key and str(contenu.get(order_key, '')).strip() == str(self.numero):
                    # Chercher la colonne Supplier dans la même ligne (normalisation tolérante)
                    for key, value in contenu.items():
                        if not key:
                            continue
                        norm = key.strip().lower().replace('_', ' ')
                        norm = ' '.join(norm.split())
                        if (
                            'supplier' in norm or
                            'vendor' in norm or
                            'fournisseur' in norm or
                            'vendeur' in norm
                        ) and value:
                            return str(value)
        return "N/A"

    def get_order_description(self):
        """Récupère la description de commande (Order Description) depuis les lignes du fichier importé."""
        if not self.fichiers.exists():
            return "N/A"
        for fichier in self.fichiers.all():
            for ligne in fichier.lignes.all():
                contenu = ligne.contenu
                
                # Trouver la clé pour le numéro de commande
                order_key = None
                for key in contenu.keys():
                    key_lower = key.lower() if key else ''
                    if 'order' in key_lower or 'commande' in key_lower or 'bon' in key_lower or 'bc' in key_lower:
                        order_key = key
                        break
                
                # Vérifier que la ligne correspond à ce bon de commande
                if order_key and str(contenu.get(order_key, '')).strip() == str(self.numero):
                    # Chercher la colonne Order Description (exact, tolérant espaces/underscores)
                    for key, value in contenu.items():
                        if not key:
                            continue
                        norm = key.strip().lower().replace('_', ' ')
                        norm = ' '.join(norm.split())  # compacter espaces
                        if norm == 'order description' and value:
                            return str(value)
        return "N/A"
    
    def get_currency(self):
        """Récupère la devise depuis les lignes correspondant au bon de commande"""
        if not self.fichiers.exists():
            return "XOF"  # Devise par défaut

        for fichier in self.fichiers.all():
            for ligne in fichier.lignes.all():
                contenu = ligne.contenu
            
            # Trouver la clé pour le numéro de commande
            order_key = None
            for key in contenu.keys():
                key_lower = key.lower() if key else ''
                if 'order' in key_lower or 'commande' in key_lower or 'bon' in key_lower or 'bc' in key_lower:
                    order_key = key
                    break
            
            if order_key and str(contenu.get(order_key, '')).strip() == str(self.numero):
                # Chercher la colonne Currency
                for key, value in contenu.items():
                    key_lower = key.lower() if key else ''
                    if 'currency' in key_lower and value:
                        return str(value).upper()
    
        return "XOF"
        
    def get_project_number(self):
        """Récupère le numéro de projet depuis les lignes correspondant au bon de commande"""
        if not self.fichiers.exists():
            return "N/A"

        for fichier in self.fichiers.all():
            for ligne in fichier.lignes.all():
                contenu = ligne.contenu
                
                # Trouver la clé pour le numéro de commande
                order_key = None
                for key in contenu.keys():
                    key_lower = key.lower() if key else ''
                    if 'order' in key_lower or 'commande' in key_lower or 'bon' in key_lower or 'bc' in key_lower:
                        order_key = key
                        break
                
                if order_key and str(contenu.get(order_key, '')).strip() == str(self.numero):
                    # Chercher la colonne Project Number
                    for key, value in contenu.items():
                        key_lower = key.lower() if key else ''
                        if ('project number' in key_lower or 'project_number' in key_lower or 'project' in key_lower) and value:
                            return str(value)
                    
                    # Chercher d'autres colonnes qui pourraient contenir le numéro de projet
                    for key, value in contenu.items():
                        key_lower = key.lower() if key else ''
                        if ('projet' in key_lower or 'code projet' in key_lower or 'code_projet' in key_lower or 'project id' in key_lower or 'project_id' in key_lower) and value:
                            return str(value)

        return "N/A"

    def get_cpu(self):
        """Récupère la valeur CPU depuis les lignes correspondant au bon de commande.
        Nettoie la valeur en supprimant le préfixe numérique et le tiret (ex: '02 - ITS' devient 'ITS').
        """
        if not self.fichiers.exists():
            return "N/A"

        for fichier in self.fichiers.all():
            for ligne in fichier.lignes.all():
                contenu = ligne.contenu
                
                # Trouver la clé pour le numéro de commande
                order_key = None
                for key in contenu.keys():
                    key_lower = key.lower() if key else ''
                    if 'order' in key_lower or 'commande' in key_lower or 'bon' in key_lower or 'bc' in key_lower:
                        order_key = key
                        break
                
                if order_key and str(contenu.get(order_key, '')).strip() == str(self.numero):
                    # Chercher la colonne CPU
                    for key, value in contenu.items():
                        key_lower = key.lower() if key else ''
                        if 'cpu' in key_lower and value:
                            # Nettoyer la valeur CPU (ex: '02 - ITS' -> 'ITS')
                            cpu_value = str(value).strip()
                            if ' - ' in cpu_value:
                                # Prendre la partie après le dernier tiret et supprimer les espaces
                                cpu_value = cpu_value.split('-')[-1].strip()
                            return cpu_value

        return "N/A"
    
    def get_project_manager(self):
        """Récupère le nom du Project Manager depuis les lignes correspondant au bon de commande"""
        if not self.fichiers.exists():
            return "N/A"

        import logging
        logger = logging.getLogger(__name__)

        for fichier in self.fichiers.all():
            for ligne in fichier.lignes.all():
                contenu = ligne.contenu
                
                # Trouver la clé pour le numéro de commande
                order_key = None
                for key in contenu.keys():
                    key_lower = key.lower() if key else ''
                    if 'order' in key_lower or 'commande' in key_lower or 'bon' in key_lower or 'bc' in key_lower:
                        order_key = key
                        break
                
                if order_key and str(contenu.get(order_key, '')).strip() == str(self.numero):
                    # Chercher la colonne Project Manager avec variations possibles
                    for key, value in contenu.items():
                        key_lower = key.lower() if key else ''
                        logger.debug(f"Checking key: '{key}' (lower: '{key_lower}'), value: '{value}'")
                        
                        if (('project' in key_lower and 'manager' in key_lower) or 
                            'project_manager' in key_lower) and value and str(value).strip():
                            logger.debug(f"Found Project Manager: '{value}' in key: '{key}'")
                            return str(value).strip()

        logger.debug(f"No Project Manager found for order {self.numero}")
        return "N/A"


    def get_project_coordinator(self):
        """Récupère le nom du Project Coordinator depuis les lignes correspondant au bon de commande"""
        if not self.fichiers.exists():
            return "N/A"

        import logging
        logger = logging.getLogger(__name__)

        for fichier in self.fichiers.all():
            for ligne in fichier.lignes.all():
                contenu = ligne.contenu
                
                # Trouver la clé pour le numéro de commande
                order_key = None
                for key in contenu.keys():
                    key_lower = key.lower() if key else ''
                    if 'order' in key_lower or 'commande' in key_lower or 'bon' in key_lower or 'bc' in key_lower:
                        order_key = key
                        break
                
                if order_key and str(contenu.get(order_key, '')).strip() == str(self.numero):
                    logger.debug(f"Found matching order {self.numero}, searching for Project Coordinator in keys: {list(contenu.keys())}")
                    
                    # Chercher la colonne Project Coordinator avec variations possibles
                    for key, value in contenu.items():
                        key_lower = key.lower() if key else ''
                        logger.debug(f"Checking key: '{key}' (lower: '{key_lower}'), value: '{value}'")
                        
                        if ('project coordinator' in key_lower or 
                            'project_coordinator' in key_lower or
                            'coordinator' in key_lower) and value and str(value).strip():
                            logger.debug(f"Found Project Coordinator: '{value}' in key: '{key}'")
                            return str(value).strip()

        logger.debug(f"No Project Coordinator found for order {self.numero}")
        return "N/A"
    
    
    def get_manager_portfolio(self):
        """Récupère le nom du Manager Portfolio depuis les lignes correspondant au bon de commande"""
        if not self.fichiers.exists():
            return "N/A"

        for fichier in self.fichiers.all():
            for ligne in fichier.lignes.all():
                contenu = ligne.contenu
                
                # Trouver la clé pour le numéro de commande
                order_key = None
                for key in contenu.keys():
                    key_lower = key.lower() if key else ''
                    if 'order' in key_lower or 'commande' in key_lower or 'bon' in key_lower or 'bc' in key_lower:
                        order_key = key
                        break
                
                if order_key and str(contenu.get(order_key, '')).strip() == str(self.numero):
                    # Chercher la colonne Manager Portfolio
                    for key, value in contenu.items():
                        key_lower = key.lower() if key else ''
                        if 'manager portfolio' in key_lower and value:
                            return str(value)

        return "N/A"
    
    def get_Année(self):
        if not self.fichiers.exists():
            return "N/A"

        for fichier in self.fichiers.all():
            for ligne in fichier.lignes.all():
                contenu = ligne.contenu
                
                # Trouver la clé pour le numéro de commande
                order_key = None
                for key in contenu.keys():
                    key_lower = key.lower() if key else ''
                    if 'order' in key_lower or 'commande' in key_lower or 'bon' in key_lower or 'bc' in key_lower:
                        order_key = key
                        break
                
                if order_key and str(contenu.get(order_key, '')).strip() == str(self.numero):
                    # Chercher la colonne Manager Portfolio
                    for key, value in contenu.items():
                        key_lower = key.lower() if key else ''
                        if 'annee' in key_lower and value:
                            return str(value)

        return "N/A"
    
    def get_Project_Name(self):
        if not self.fichiers.exists():
            return "N/A"
        for fichier in self.fichiers.all():
            for ligne in fichier.lignes.all():
                contenu = ligne.contenu
                
            order_key = None
            for key in contenu.keys():
                key_lower = key.lower() if key else ''
                if 'order' in key_lower or 'commande' in key_lower or 'bon' in key_lower or 'bc' in key_lower:
                    order_key = key
                    break
            
            if order_key and str(contenu.get(order_key, '')).strip() == str(self.numero):
                for key, value in contenu.items():
                    key_lower = key.lower() if key else ''
                    if 'project name' in key_lower and value:
                        return str(value)
        return "N/A"
    
    def get_Po_type(self):
        if not self.fichiers.exists():
            return "N/A"
        for fichier in self.fichiers.all():
            for ligne in fichier.lignes.all():
                contenu = ligne.contenu
                
            order_key = None
            for key in contenu.keys():
                key_lower = key.lower() if key else ''
                if 'order' in key_lower or 'commande' in key_lower or 'bon' in key_lower or 'bc' in key_lower:
                    order_key = key
                    break
            
            if order_key and str(contenu.get(order_key, '')).strip() == str(self.numero):
                for key, value in contenu.items():
                    key_lower = key.lower() if key else ''
                    if 'po type' in key_lower and value:
                        return str(value)
        return "N/A"

    def get_Replaced_Order(self):
        if not self.fichiers.exists():
            return "N/A"
        for fichier in self.fichiers.all():
            for ligne in fichier.lignes.all():
                contenu = ligne.contenu
                
            order_key = None
            for key in contenu.keys():
                key_lower = key.lower() if key else ''
                if 'order' in key_lower or 'commande' in key_lower or 'bon' in key_lower or 'bc' in key_lower:
                    order_key = key
                    break
            
            if order_key and str(contenu.get(order_key, '')).strip() == str(self.numero):
                for key, value in contenu.items():
                    key_lower = key.lower() if key else ''
                    if 'replaced order' in key_lower and value:
                        return str(value)
        return "N/A"
    
    def get_ASSET_TYPE(self):
        if not self.fichiers.exists():
            return "N/A"
        for fichier in self.fichiers.all():
            for ligne in fichier.lignes.all():
                contenu = ligne.contenu
                
            order_key = None
            for key in contenu.keys():
                key_lower = key.lower() if key else ''
                if 'order' in key_lower or 'commande' in key_lower or 'bon' in key_lower or 'bc' in key_lower:
                    order_key = key
                    break
            
            if order_key and str(contenu.get(order_key, '')).strip() == str(self.numero):
                for key, value in contenu.items():
                    key_lower = key.lower() if key else ''
                    if 'asset type' in key_lower and value:
                        return str(value)
        return "N/A"
    
    def get_PIP_END_DATE(self):
        if not self.fichiers.exists():
            return "N/A"
        for fichier in self.fichiers.all():
            for ligne in fichier.lignes.all():
                contenu = ligne.contenu
                
            order_key = None
            for key in contenu.keys():
                key_lower = key.lower() if key else ''
                if 'order' in key_lower or 'commande' in key_lower or 'bon' in key_lower or 'bc' in key_lower:
                    order_key = key
                    break
            
            if order_key and str(contenu.get(order_key, '')).strip() == str(self.numero):
                for key, value in contenu.items():
                    key_lower = key.lower() if key else ''
                    if 'pip end date' in key_lower and value:
                        return str(value)
        return "N/A"
    
    def get_REVISED_END_DATE(self):
        if not self.fichiers.exists():
            return "N/A"
        for fichier in self.fichiers.all():
            for ligne in fichier.lignes.all():
                contenu = ligne.contenu
                
            order_key = None
            for key in contenu.keys():
                key_lower = key.lower() if key else ''
                if 'order' in key_lower or 'commande' in key_lower or 'bon' in key_lower or 'bc' in key_lower:
                    order_key = key
                    break
            
            if order_key and str(contenu.get(order_key, '')).strip() == str(self.numero):
                for key, value in contenu.items():
                    key_lower = key.lower() if key else ''
                    if 'revised end date' in key_lower and value:
                        return str(value)
        return "N/A"
    
    def get_ACTUAL_END_DATE(self):
        if not self.fichiers.exists():
            return "N/A"
        for fichier in self.fichiers.all():
            for ligne in fichier.lignes.all():
                contenu = ligne.contenu
                
            order_key = None
            for key in contenu.keys():
                key_lower = key.lower() if key else ''
                if 'order' in key_lower or 'commande' in key_lower or 'bon' in key_lower or 'bc' in key_lower:
                    order_key = key
                    break
            
            if order_key and str(contenu.get(order_key, '')).strip() == str(self.numero):
                for key, value in contenu.items():
                    key_lower = key.lower() if key else ''
                    if 'actual end date' in key_lower and value:
                        return str(value)
        return "N/A"

    def get_Line_Type(self):
        if not self.fichiers.exists():
            return "N/A"
        for fichier in self.fichiers.all():
            for ligne in fichier.lignes.all():
                contenu = ligne.contenu
                
            order_key = None
            for key in contenu.keys():
                key_lower = key.lower() if key else ''
                if 'order' in key_lower or 'commande' in key_lower or 'bon' in key_lower or 'bc' in key_lower:
                    order_key = key
                    break
            
            if order_key and str(contenu.get(order_key, '')).strip() == str(self.numero):
                for key, value in contenu.items():
                    key_lower = key.lower() if key else ''
                    if 'line type' in key_lower and value:
                        return str(value)
        return "N/A"
 

    def get_gm_epmo(self):
        """Récupère le nom du GM EPMO depuis les lignes correspondant au bon de commande"""
        if not self.fichiers.exists():
            return "N/A"

        for fichier in self.fichiers.all():
            for ligne in fichier.lignes.all():
                contenu = ligne.contenu
                
                # Trouver la clé pour le numéro de commande
                order_key = None
                for key in contenu.keys():
                    key_lower = key.lower() if key else ''
                    if 'order' in key_lower or 'commande' in key_lower or 'bon' in key_lower or 'bc' in key_lower:
                        order_key = key
                        break
                
                if order_key and str(contenu.get(order_key, '')).strip() == str(self.numero):
                    # Chercher la colonne GM EPMO
                    for key, value in contenu.items():
                        key_lower = key.lower() if key else ''
                        if 'gm epmo' in key_lower and value:
                            return str(value)

        return "N/A"
    
    def get_senior_pm(self):
        """Récupère le nom du Senior PM depuis les lignes correspondant au bon de commande"""
        if not self.fichiers.exists():
            return "N/A"

        for fichier in self.fichiers.all():
            for ligne in fichier.lignes.all():
                contenu = ligne.contenu
                
                # Trouver la clé pour le numéro de commande
                order_key = None
                for key in contenu.keys():
                    key_lower = key.lower() if key else ''
                    if 'order' in key_lower or 'commande' in key_lower or 'bon' in key_lower or 'bc' in key_lower:
                        order_key = key
                        break
                
                if order_key and str(contenu.get(order_key, '')).strip() == str(self.numero):
                    # Chercher la colonne Senior PM
                    for key, value in contenu.items():
                        key_lower = key.lower() if key else ''
                        if 'senior pm' in key_lower and value:
                            return str(value)

        return "N/A"
    
    def get_senior_technical_lead(self):
        """Récupère le nom du Senior Technical Lead depuis les lignes correspondant au bon de commande"""
        if not self.fichiers.exists():
            return "N/A"

        for fichier in self.fichiers.all():
            for ligne in fichier.lignes.all():
                contenu = ligne.contenu
                
                # Trouver la clé pour le numéro de commande
                order_key = None
                for key in contenu.keys():
                    key_lower = key.lower() if key else ''
                    if 'order' in key_lower or 'commande' in key_lower or 'bon' in key_lower or 'bc' in key_lower:
                        order_key = key
                        break
                
                if order_key and str(contenu.get(order_key, '')).strip() == str(self.numero):
                    # Chercher la colonne Senior Technical Lead
                    for key, value in contenu.items():
                        key_lower = key.lower() if key else ''
                        if 'senior technical lead' in key_lower and value:
                            return str(value)

        return "N/A"

    def calculate_amount_payable(self):
        """Calcule le montant total de Amount Payable pour ce bon de commande"""
        receptions = Reception.objects.filter(bon_commande_id=self.id)
        total = Decimal(0)
        for rec in receptions:
            total += rec.amount_payable
        return total

    def calculate_quantity_payable(self):
        """Calcule le montant total de Quantity Payable pour ce bon de commande"""
        receptions = Reception.objects.filter(bon_commande_id=self.id)
        total = Decimal(0)
        for rec in receptions:
            total += rec.quantity_payable
        return total

    def save(self, *args, **kwargs):
        # Validation du taux de rétention
        if self.retention_rate < 0 or self.retention_rate > 10:
            raise ValidationError("Le taux de rétention doit être entre 0 et 10%")
            
        # Sauvegarder d'abord l'instance
        super().save(*args, **kwargs)
        
        # Recalculer toutes les réceptions après sauvegarde
        from django.db.models import Value, DecimalField
        # Construire le facteur (1 - retention_rate/100) en Decimal pour éviter les erreurs de type
        factor = Value(1, output_field=DecimalField()) - (Value(self.retention_rate, output_field=DecimalField()) / Value(100, output_field=DecimalField()))

        qs = self.receptions.all()
        qs.update(
            # Quantité monétaire reçue (sans rétention)
            amount_delivered=F('quantity_delivered') * F('unit_price'),
            # Quantité payable après rétention
            quantity_payable=F('quantity_delivered') * factor,
            # Montant  payable après rétention
            amount_payable=F('unit_price') * F('quantity_payable'),
        )
        
        logger.info(f"Recalcul des quantity_payable pour le bon {self.numero} "
                   f"après changement du taux de rétention à {self.retention_rate}%")
    
    def get_code_ifs(self):
        """Récupère le code IFS depuis les lignes correspondant au bon de commande"""
        if not self.fichiers.exists():
            return "N/A"

        for fichier in self.fichiers.all():
            for ligne in fichier.lignes.all():
                contenu = ligne.contenu
                
                # Trouver la clé pour le numéro de commande
                order_key = None
                for key in contenu.keys():
                    key_lower = key.lower() if key else ''
                    if 'order' in key_lower or 'commande' in key_lower or 'bon' in key_lower or 'bc' in key_lower:
                        order_key = key
                        break
                
                if order_key and str(contenu.get(order_key, '')).strip() == str(self.numero):
                    # Chercher la colonne Code IFS
                    for key, value in contenu.items():
                        key_lower = key.lower() if key else ''
                        if ('code' in key_lower and 'ifs' in key_lower) or ('ifs' in key_lower and 'code' in key_lower):
                            if value:
                                return str(value)
                            
                            # Si la valeur est vide, vérifier s'il y a une valeur dans la même ligne pour 'code'
                            # qui pourrait être le code IFS (certains fichiers utilisent juste 'code')
                            code_value = contenu.get('code', '')
                            if code_value and not any(x in code_value.lower() for x in ['-', ' ', '_']):
                                return str(code_value)

        return "N/A"
    
    def __str__(self):
        return self.numero


class LigneFichier(models.Model):
    """
    Stocke chaque ligne d'un fichier importé avec un ID unique
    """
    fichier = models.ForeignKey(
        'FichierImporte',
        on_delete=models.CASCADE,
        related_name='lignes',
        verbose_name="Fichier d'origine"
    )
    numero_ligne = models.IntegerField(
        verbose_name="Numéro de ligne"
    )
    contenu = models.JSONField(
        verbose_name="Contenu de la ligne"
    )
    date_creation = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de création"
    )
    
    # Nouveau champ pour l'ID métier stable
    business_id = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        verbose_name="ID métier",
        help_text="Identifiant métier basé sur Order+Line+Item+Schedule"
    )
    
    class Meta:
        verbose_name = "Ligne de fichier"
        verbose_name_plural = "Lignes de fichiers"
        ordering = ['fichier', 'numero_ligne']
        unique_together = [['fichier', 'numero_ligne']]
        indexes = [
            models.Index(fields=['fichier', 'numero_ligne']),
            models.Index(fields=['business_id']),
        ]
    
    def generate_business_id(self):
        """Génère un ID métier basé sur Order+Line+Item+Schedule avec normalisation des valeurs numériques"""
        if not self.contenu:
            return None
            
        components = []
        
        def normalize_numeric_value(value):
            """Normalise les valeurs numériques pour éviter les doublons (43.0 -> 43)"""
            if value is None:
                return None
            value_str = str(value).strip()
            try:
                # Essayer de convertir en float puis supprimer les .0 inutiles
                float_val = float(value_str)
                if float_val.is_integer():
                    return str(int(float_val))
                else:
                    return value_str
            except (ValueError, TypeError):
                return value_str
        
        # Extraire Order
        order_value = None
        for key, value in self.contenu.items():
            key_lower = key.lower() if key else ''
            if 'order' in key_lower and value:
                order_value = str(value).strip()
                break
        if order_value:
            components.append(f"ORDER:{order_value}")
            
        # Extraire Line (pas Line Description)
        line_value = None
        for key, value in self.contenu.items():
            key_lower = key.lower() if key else ''
            if 'line' in key_lower and 'description' not in key_lower and value:
                line_value = normalize_numeric_value(value)
                break
        if line_value:
            components.append(f"LINE:{line_value}")
            
        # Extraire Item (pas Item Description)
        item_value = None
        for key, value in self.contenu.items():
            key_lower = key.lower() if key else ''
            if 'item' in key_lower and 'description' not in key_lower and value:
                item_value = normalize_numeric_value(value)
                break
        if item_value:
            components.append(f"ITEM:{item_value}")
            
        # Extraire Schedule
        schedule_value = None
        for key, value in self.contenu.items():
            key_lower = key.lower() if key else ''
            if 'schedule' in key_lower and value:
                schedule_value = normalize_numeric_value(value)
                break
        if schedule_value:
            components.append(f"SCHEDULE:{schedule_value}")
            
        # Utiliser la fonction globale de normalisation pour s'assurer de la cohérence
        raw_business_id = "|".join(components) if components else None
        return normalize_business_id(raw_business_id) if raw_business_id else None
    
    def save(self, *args, **kwargs):
        # Générer l'ID métier avant sauvegarde
        if not self.business_id:
            self.business_id = self.generate_business_id()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Ligne {self.numero_ligne} du fichier {self.fichier.id}"

    def get_key_columns(self):
        if not self.contenu:
            return {}
            
        # Fonction pour obtenir une valeur décimale arrondie
        def get_decimal_value(key, default=0):
            value = self.contenu.get(key)
            if value in (None, ''):
                return Decimal(default)
            try:
                return round_decimal(Decimal(str(value)))
            except (TypeError, ValueError, InvalidOperation):
                return Decimal(default)
        
        key_columns = {
            'id': self.numero_ligne,
            'original_id': self.id,
            'ordered_quantity': get_decimal_value('Ordered Quantity'),
            'quantity_delivered': get_decimal_value('Quantity Delivered'),
            'quantity_not_delivered': get_decimal_value('Quantity Not Delivered'),
            'unit_price': get_decimal_value('Price')
        }
        
        return key_columns


class FichierImporte(models.Model):
    """
    Modèle pour stocker les métadonnées des fichiers importés.
    Les données brutes sont stockées dans le modèle LigneFichier.
    """

    fichier = models.FileField(
        upload_to='uploads/',
        verbose_name="File"
    )
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Utilisateur"
    )
    extension = models.CharField(
        max_length=10,
        verbose_name="Extension",
        editable=False
    )
    date_importation = models.DateTimeField(
        default=timezone.now,
        verbose_name="Import Date",
        editable=False
    )
    nombre_lignes = models.IntegerField(
        default=0,
        verbose_name="Number of Rows",
        editable=False
    )
    
    def get_raw_data(self):
        """Récupère les données brutes du fichier"""
        return [ligne.contenu for ligne in self.lignes.order_by('numero_ligne')]
    
    def get_recipe_quantities(self):
        """Récupère les quantités de recette"""
        # Cette méthode est conservée pour la compatibilité
        # Les quantités de recette devraient maintenant être gérées par le modèle Reception
        return {}
        
    def extraire_et_enregistrer_bons_commande(self):
        """
        Extrait les numéros de bons de commande depuis la colonne 'ORDER' du fichier importé
        et les enregistre dans la table NumeroBonCommande.
        """
        lignes = list(self.lignes.all())
        if not lignes:
            print("Aucune ligne de contenu pour extraire les bons de commande")
            return
            
        # Trouver la colonne 'ORDER' (ou variante) dans les données
        colonne_order = None
        if lignes and lignes[0].contenu:
            # Vérifier la première ligne pour trouver le nom de la colonne (cas insensible)
            for cle in lignes[0].contenu.keys():
                if cle.upper() in ['ORDER', 'ORDRE', 'BON', 'BON_COMMANDE', 'COMMANDE', 'BC', 'NUM_BC']:
                    colonne_order = cle
                    break
                    
        if not colonne_order:
            print("Colonne ORDER non trouvée dans les données")
            return
            
        # Définir les valeurs invalides
        valeurs_invalides = ('', 'false', 'true', 'none', 'null', 'nan', '0')
        
        # Extraire les numéros uniques de bons de commande
        numeros_bons = set()
        for ligne in lignes:
            contenu = ligne.contenu
            if contenu and colonne_order in contenu and contenu[colonne_order]:
                # Convertir en string et nettoyer le numéro
                numero = str(contenu[colonne_order]).strip()
                # Filtrer les valeurs invalides
                if numero and numero.lower() not in valeurs_invalides:
                    numeros_bons.add(numero)
                    
        print(f"Extraction de {len(numeros_bons)} numéros de bons de commande uniques")
        
        # Enregistrer chaque numéro dans la table NumeroBonCommande s'il n'existe pas déjà
        for numero in numeros_bons:
            bon_commande, created = NumeroBonCommande.objects.get_or_create(numero=numero)
            # Associer ce fichier au bon de commande
            bon_commande.fichiers.add(self)
            
            if created:
                print(f"Nouveau bon de commande créé: {numero}")
            else:
                print(f"Bon de commande existant associé: {numero}")

    class Meta:
        verbose_name = "Imported File"
        verbose_name_plural = "Imported Files"

    def __str__(self):
        return f"{self.fichier.name} ({self.date_importation:%Y-%m-%d %H:%M})"

    def save(self, *args, **kwargs):
        """
        1) On appelle super().save() pour que FileField écrive le fichier sur disque.
        2) On détermine automatiquement l'extension (sans le point).
        3) On appelle utils.extraire_depuis_fichier_relatif() pour obtenir :
           - contenu_extrait : soit une liste de dicts (pour données tabulaires),
           - soit un dict {"lines": [...]}, soit {"raw_bytes_hex": "..."} ou {"error": "..."}.
           - nb_lignes : le nombre de lignes/entrées extraites.
        4) On met à jour en base les champs extension, nombre_lignes.
        5) On crée les entrées LigneFichier pour chaque ligne de données.
        """
        is_new = self.pk is None
        super().save(*args, **kwargs)  # 1) Sauvegarde le fichier

        if not self.fichier:
            return  # Si pas de fichier, on s'arrête là

        # 2) Détection de l'extension
        chemin_relatif = self.fichier.name  # ex : 'uploads/monfichier.xlsb'
        _, ext = os.path.splitext(chemin_relatif)
        ext = ext.lstrip('.').lower()
        self.extension = ext

        # 3) Extraction du contenu - avec debug en cas d'erreur
        try:
            from .utils import extraire_depuis_fichier_relatif
            import json
            print(f"Extraction à partir du fichier: {chemin_relatif} (ext: {ext})")
            contenu_extrait, nb_lignes = extraire_depuis_fichier_relatif(chemin_relatif, ext)
            print(f"Extraction réussie. Type de données: {type(contenu_extrait)}")
            
            # 4) Mise à jour des attributs
            self.nombre_lignes = nb_lignes
            
            # 5) Sauvegarder les métadonnées mises à jour
            super().save(update_fields=['extension', 'nombre_lignes'])
            
            # 6) Créer les entrées LigneFichier et gérer les quantités reçues
            if isinstance(contenu_extrait, list) and contenu_extrait:
                # Initialiser les en-têtes
                headers = []
                # Déterminer un offset d'en-tête: si données tabulaires (liste de dicts) => +1 (ligne 1 = en-tête)
                is_tabular = isinstance(contenu_extrait[0], dict)
                header_offset = 1 if is_tabular else 0
                
                # Récupérer les lignes existantes pour mise à jour incrémentielle
                existing_lines = {ligne.numero_ligne: ligne for ligne in self.lignes.all()}
                lignes_a_creer = []
                
                # Mapping explicite selon les instructions de l'utilisateur
                order_key = 'Order'
                ordered_qty_key = 'Ordered Quantity'
                received_qty_key = 'Received Quantity'
                unit_price_key = 'Price'
                print(f"Colonnes utilisées : order_key={order_key}, ordered_qty_key={ordered_qty_key}, received_qty_key={received_qty_key}, unit_price_key={unit_price_key}")
                
                print(f"Colonnes détectées : order_key={order_key}, ordered_qty_key={ordered_qty_key}, received_qty_key={received_qty_key}, unit_price_key={unit_price_key}")
                
                # Traiter chaque ligne du fichier
                for i, ligne in enumerate(contenu_extrait, 1):
                    # Calculer le numéro de ligne aligné avec la ligne visible Excel
                    ligne_numero = i + header_offset
                    if not isinstance(ligne, dict):
                        continue
                    
                    # Préparer les données pour la table Reception si on a les clés nécessaires
                    if order_key and order_key in ligne:
                        try:
                            # Récupérer les valeurs
                            order_number = str(ligne[order_key]).strip()
                            valeurs_invalides = ('', 'false', 'true', 'none', 'null', 'nan', '0')
                            if order_number.lower() in valeurs_invalides:
                                print(f"Ligne {i} ignorée : numéro de bon invalide ('{order_number}')")
                                continue
                            from decimal import Decimal
                            # Détection robuste des valeurs pour cette ligne
                            def scan_value(d, must_include):
                                for k, v in d.items():
                                    if not k:
                                        continue
                                    kl = k.lower()
                                    if all(m in kl for m in must_include):
                                        return v
                                return None

                            # Received Quantity
                            rv = None
                            if 'Received Quantity' in ligne:
                                rv = ligne.get('Received Quantity')
                            if rv in (None, ''):
                                rv = scan_value(ligne, ['received', 'quantity'])
                            received_qty_dec = round_decimal(Decimal(str(rv))) if rv not in (None, '') else Decimal('0')

                            # Ordered Quantity
                            ov = None
                            if 'Ordered Quantity' in ligne:
                                ov = ligne.get('Ordered Quantity')
                            if ov in (None, ''):
                                ov = scan_value(ligne, ['ordered', 'quantity'])
                            ordered_qty_dec = round_decimal(Decimal(str(ov))) if ov not in (None, '') else Decimal('0')
                            
                            # Récupérer ou créer le bon de commande
                            bon_commande, _ = NumeroBonCommande.objects.get_or_create(numero=order_number)
                            
                            # Détecter le prix unitaire
                            from decimal import Decimal
                            unit_price = Decimal(0)
                            pv = None
                            if 'Price' in ligne and ligne['Price'] not in (None, ''):
                                pv = ligne.get('Price')
                            if pv in (None, ''):
                                pv = scan_value(ligne, ['price'])
                            try:
                                unit_price = round_decimal(Decimal(str(pv))) if pv not in (None, '') else Decimal(0)
                            except:
                                unit_price = Decimal(0)
                            
                            # DEBUG: Afficher les valeurs extraites pour chaque ligne
                            print(f"Reception: bon_commande={order_number}, ordered_quantity={ordered_qty_dec}, quantity_delivered={received_qty_dec}, unit_price={unit_price}")
                            
                            # Générer l'ID métier en réutilisant exactement la même logique que LigneFichier.generate_business_id
                            temp_lf = LigneFichier(fichier=self, numero_ligne=i, contenu=ligne)
                            business_id = temp_lf.generate_business_id()
                            if not business_id:
                                print(f"ERREUR: Impossible de générer un ID métier pour la ligne {i} (order={order_number}). Vérifier les colonnes 'Line'/'Item'/'Schedule'.")
                                continue
                            print(f"ID métier généré: {business_id}")
                            
                            try:
                                # Vérifier d'abord si une réception existe avec cet ID (exact)
                                reception = Reception.objects.filter(business_id=business_id).first()
                                
                                # Si pas trouvé, chercher avec normalisation
                                if not reception:
                                    normalized_business_id = normalize_business_id(business_id)
                                    if normalized_business_id != business_id:
                                        reception = Reception.objects.filter(business_id=normalized_business_id).first()
                                        if reception:
                                            print(f"Réception trouvée avec ID normalisé: {normalized_business_id}")
                                    
                                    # Si toujours pas trouvé, chercher parmi tous les business_id normalisés
                                    if not reception:
                                        all_receptions = Reception.objects.filter(bon_commande=bon_commande)
                                        for existing_reception in all_receptions:
                                            if normalize_business_id(existing_reception.business_id) == normalized_business_id:
                                                reception = existing_reception
                                                print(f"Réception trouvée après normalisation: {existing_reception.business_id} -> {normalized_business_id}")
                                                break
                                
                                # Debug: Vérifier les réceptions existantes
                                existing_receptions = list(Reception.objects.filter(bon_commande=bon_commande).values_list('business_id', flat=True))
                                print(f"Réceptions existantes pour ce bon de commande: {existing_receptions}")
                                print(f"Recherche de l'ID: {business_id} (existe: {reception is not None})")
                                
                                if reception:
                                    print(f"Réception existante trouvée (ID: {business_id}) - mise à jour du received_quantity seulement")
                                    print(f"Détails actuels - commandé: {reception.ordered_quantity}, livré: {reception.quantity_delivered}")
                                    
                                    # Mettre à jour SEULEMENT le received_quantity (dans le contexte de ce fichier)
                                    # Ne pas modifier quantity_delivered qui est la valeur cumulative
                                    reception.ordered_quantity = ordered_qty_dec
                                    reception.unit_price = unit_price
                                    reception.received_quantity = received_qty_dec
                                    reception.quantity_not_delivered = max(Decimal('0'), ordered_qty_dec - reception.quantity_delivered)
                                    reception.date_modification = timezone.now()
                                    reception.save()
                                    created = False
                                else:
                                    # Créer nouvelle réception avec ID métier
                                    quantity_not_delivered_val = max(Decimal('0'), ordered_qty_dec - received_qty_dec)
                                    reception = Reception.objects.create(
                                        bon_commande=bon_commande,
                                        fichier=self,
                                        business_id=business_id,
                                        ordered_quantity=ordered_qty_dec,
                                        received_quantity=received_qty_dec,
                                        quantity_delivered=received_qty_dec,
                                        quantity_not_delivered=quantity_not_delivered_val,
                                        user=self.utilisateur.username if self.utilisateur else 'system_import',
                                        date_modification=timezone.now(),
                                        unit_price=unit_price
                                    )
                                    created = True
                                    print(f"Nouvelle réception ajoutée : BC={bon_commande.numero}, ID={business_id}")

                                # Mettre à jour/Créer la valeur initiale par business_id (indépendante des réceptions)
                                try:
                                    from decimal import Decimal as _D
                                    mt_total = round_decimal(ordered_qty_dec * unit_price)
                                    mt_recu = round_decimal(received_qty_dec * unit_price)
                                    taux = _D('0')
                                    if mt_total > 0:
                                        taux = round_decimal((mt_recu / mt_total) * _D('100'))

                                    irv_bi, _ = InitialReceptionBusiness.objects.get_or_create(
                                        business_id=business_id,
                                        defaults={'bon_commande': bon_commande}
                                    )
                                    irv_bi.bon_commande = bon_commande
                                    irv_bi.source_file = self
                                    irv_bi.received_quantity = received_qty_dec
                                    irv_bi.montant_total_initial = mt_total
                                    irv_bi.montant_recu_initial = mt_recu
                                    irv_bi.taux_avancement_initial = taux
                                    irv_bi.save()
                                except Exception as e:
                                    print(f"[IRV-BI][ERROR] {business_id}: {e}")
                                    
                            except Exception as e:
                                print(f"ERREUR lors de la création/mise à jour de la réception {business_id}: {str(e)}")
                                print(f"Détails: order={order_number}, line={line_num}, item={item_num}, schedule={schedule_num}")
                                continue
                            
                            # Ajouter la quantité reçue à la ligne pour l'affichage (toujours, même si la réception existe déjà)
                            # On stocke en float dans la ligne JSON pour compatibilité UI, mais on calcule en Decimal
                            ligne['Quantity Delivered'] = float(received_qty_dec)
                            # Ajouter le calcul du quantity_not_delivered (calcul en Decimal puis conversion float)
                            ligne['Quantity Not Delivered'] = float(max(Decimal('0'), ordered_qty_dec - received_qty_dec))
                            
                        except (ValueError, TypeError) as e:
                            print(f"Erreur de conversion des quantités pour la ligne {i}: {e}")
                    
                    # S'assurer que les en-têtes Quantity Delivered et Quantity Not Delivered sont présents
                    if 'Quantity Delivered' not in headers:
                        headers.append('Quantity Delivered')
                    if 'Quantity Not Delivered' not in headers:
                        headers.append('Quantity Not Delivered')
                    
                    # Générer l'ID métier pour cette ligne
                    ligne_temp = LigneFichier(fichier=self, numero_ligne=i, contenu=ligne)
                    business_id = ligne_temp.generate_business_id()
                    
                    # Vérifier si une ligne avec le même ID métier existe déjà
                    existing_business_line = None
                    if business_id:
                        # Recherche exacte d'abord
                        existing_business_line = LigneFichier.objects.filter(business_id=business_id).first()
                        
                        # Si pas trouvé, recherche avec normalisation
                        if not existing_business_line:
                            normalized_bid = normalize_business_id(business_id)
                            if normalized_bid != business_id:
                                existing_business_line = LigneFichier.objects.filter(business_id=normalized_bid).first()
                            
                            # Si toujours pas trouvé, chercher parmi toutes les lignes normalisées
                            if not existing_business_line:
                                all_lines = LigneFichier.objects.all()
                                for line in all_lines:
                                    if normalize_business_id(line.business_id) == normalized_bid:
                                        existing_business_line = line
                                        print(f"Ligne existante trouvée après normalisation: {line.business_id} -> {normalized_bid}")
                                        break
                    
                    if existing_business_line:
                        # Ligne métier identique trouvée - mise à jour avec les nouvelles données
                        print(f"Ligne métier identique trouvée (ID: {business_id}) - mise à jour")
                        existing_business_line.contenu = ligne
                        existing_business_line.save()
                        
                        # Associer cette ligne au fichier actuel pour traçabilité
                        # (mais ne pas créer de doublon)
                        
                    elif i in existing_lines:
                        # Mise à jour de la ligne existante dans ce fichier
                        lf = existing_lines[i]
                        lf.contenu = ligne
                        lf.business_id = business_id
                        lf.save()
                    else:
                        # Création d'une nouvelle ligne
                        lignes_a_creer.append(LigneFichier(
                            fichier=self,
                            numero_ligne=i,
                            contenu=ligne,
                            business_id=business_id
                        ))
                
                # Créer les nouvelles lignes en une seule requête
                if lignes_a_creer:
                    LigneFichier.objects.bulk_create(lignes_a_creer)
                    print(f"{len(lignes_a_creer)} nouvelles lignes ajoutées à la base de données")
                
                # Afficher un message récapitulatif
                if received_qty_key:
                    print(f"Colonnes détectées - Quantité reçue: '{received_qty_key}', "
                          f"Quantité commandée: '{ordered_qty_key or 'Non trouvée'}', "
                          f"N° commande: '{order_key or 'Non trouvé'}'")
                    print(f"Les quantités reçues ont été enregistrées dans la table Reception.")
            
            # Appeler la méthode d'extraction des bons de commande
            self.extraire_et_enregistrer_bons_commande()
            
            
        except Exception as e:
            import traceback
            print(f"ERREUR d'extraction: {str(e)}")
            print(traceback.format_exc())
            
            # Créer une entrée d'erreur dans la table des lignes
            LigneFichier.objects.create(
                fichier=self,
                numero_ligne=1,
                contenu={"error": f"Erreur d'extraction: {str(e)}"}
            )

        # Mise à jour des champs sans appeler la méthode save() pour éviter les boucles infinies
        FichierImporte.objects.filter(pk=self.pk).update(
            extension=self.extension,
            nombre_lignes=self.nombre_lignes
        )
        
        # Debug après sauvegarde
        print(f"Après sauvegarde - Extension: {self.extension}, Lignes: {self.nombre_lignes}")
        
        # Vérification des lignes importées
        nb_lignes_importees = self.lignes.count()
        if nb_lignes_importees == 0:
            print("ATTENTION: Aucune ligne n'a été importée dans la table LigneFichier")
            
        # 6) Extraction des numéros de bons de commande
        try:
            self.extraire_et_enregistrer_bons_commande()
        except Exception as e:
            print(f"Erreur lors de l'extraction des bons de commande: {str(e)}")
        

def import_or_update_fichier(fichier_upload, utilisateur=None):
    """
    Nouvelle version qui ignore les données existantes et ajoute seulement les nouvelles.
    - Chaque fichier importé est toujours sauvegardé (historique).
    - Les bons existants sont associés au fichier mais non modifiés.
    - Les nouveaux bons sont créés.
    """
    # Créer et sauvegarder le nouveau fichier
    fichier_importe = FichierImporte(
        fichier=fichier_upload,
        utilisateur=utilisateur
    )
    fichier_importe.save()  # extraction et création des lignes/réceptions

    # Extraire les numéros de bons de commande du nouveau fichier
    numeros_bons = set()
    for ligne in fichier_importe.lignes.all():
        if isinstance(ligne.contenu, dict):
            contenu = ligne.contenu
            # Détecter la clé de commande de manière insensible à la casse
            order_key = None
            for key in contenu.keys():
                key_lower = key.lower() if key else ''
                if 'order' in key_lower or 'commande' in key_lower or 'bon' in key_lower or 'bc' in key_lower:
                    order_key = key
                    break
            if order_key:
                numero = str(contenu.get(order_key, '')).strip()
                if numero and numero.lower() not in ('', 'false', 'true', 'none', 'null', 'nan', '0'):
                    numeros_bons.add(numero)

    # Associer ou créer les bons
    for numero in numeros_bons:
        bon, created = NumeroBonCommande.objects.get_or_create(numero=numero)
        bon.fichiers.add(fichier_importe)  # toujours lier le fichier au bon

    return fichier_importe, True


class Reception(models.Model):
    """
    Modèle pour stocker les quantités actuelles après réception pour chaque ligne de bon de commande.
    Utilise l'approche simplifiée où Quantity Delivered commence avec la même valeur qu'Ordered Quantity
    et diminue à chaque réception.
    """
    bon_commande = models.ForeignKey(
        NumeroBonCommande, 
        on_delete=models.CASCADE, 
        related_name='receptions',
        verbose_name="Bon de commande"
    )
    fichier = models.ForeignKey(
        'FichierImporte',
        on_delete=models.CASCADE,
        related_name='receptions',
        verbose_name="Fichier importé"
    )
    
    # ID métier stable pour identifier les lignes métier
    business_id = models.CharField(
        max_length=500,
        null=False,
        blank=False,
        unique=True,
        verbose_name="ID métier",
        help_text="Identifiant métier basé sur Order+Line+Item+schedule (doit être unique)",
        db_index=True
    )
    
    # Champs alignés avec la terminologie de l'interface et ActivityLog
    ordered_quantity = models.DecimalField(
        max_digits=20, 
        decimal_places=2,
        verbose_name="Ordered Quantity",
        null=True, 
        blank=True
    )
    quantity_delivered = models.DecimalField(
        max_digits=20, 
        decimal_places=2,
        verbose_name="Quantity Delivered",
        default=0  # Valeur par défaut pour les enregistrements existants
    )
    received_quantity = models.DecimalField(
        max_digits=20, 
        decimal_places=2,
        verbose_name="Received Quantity (current file)",
        default=0
    )
    quantity_not_delivered = models.DecimalField(
        max_digits=20, 
        decimal_places=2,
        verbose_name="Quantity Not Delivered",
        null=True, 
        blank=True
    )
    date_modification = models.DateTimeField(
        default=timezone.now,
        verbose_name="Date de modification"
    )
    user = models.CharField(
        max_length=150, 
        blank=True, 
        null=True, 
        verbose_name="Utilisateur"
    )
    unit_price = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        verbose_name="Unit Price",
        default=0
    )
    amount_delivered = models.DecimalField(
        max_digits=20, 
        decimal_places=2,
        default=0,
        verbose_name="Amount Delivered"
    )
    quantity_payable = models.DecimalField(
        max_digits=20, 
        decimal_places=2,
        default=0,
        verbose_name="Quantity Payable"
    )
    amount_payable = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Montant payable"
    )

    def verify_alignment(self, ligne_fichier):
        """Vérifie que la réception correspond bien à la ligne de fichier via business_id"""
        if self.business_id != ligne_fichier.business_id:
            return False
            
        # Vérifier que les quantités sont cohérentes
        ordered_qty = ligne_fichier.contenu.get('Ordered Quantity', 0)
        try:
            ordered_qty_dec = Decimal(str(ordered_qty)) if ordered_qty not in (None, '') else Decimal('0')
        except (InvalidOperation, ValueError, TypeError):
            ordered_qty_dec = Decimal('0')
        if (self.ordered_quantity if self.ordered_quantity is not None else Decimal('0')) != ordered_qty_dec:
            return False
        
        return True
    
    
    def save(self, *args, **kwargs):
        from decimal import Decimal, InvalidOperation

        # Normaliser le business_id avant sauvegarde pour éviter les doublons
        if self.business_id:
            self.business_id = normalize_business_id(self.business_id)

        try:
            # Convertir quantity_delivered en Decimal
            quantity_delivered_qty = Decimal(str(self.quantity_delivered)) if self.quantity_delivered is not None else Decimal('0')
            
            # Calculer amount delivered (valeur monétaire)
            unit_price_val = Decimal(str(self.unit_price)) if self.unit_price is not None else Decimal('0')
            self.amount_delivered = round_decimal(quantity_delivered_qty * unit_price_val)
            
            # Calculer quantity_payable (quantité physique après rétention)
            retention_rate = self.bon_commande.retention_rate if self.bon_commande and self.bon_commande.retention_rate is not None else 0
            retention = Decimal(str(retention_rate)) / Decimal('100')
            self.quantity_payable = round_decimal(quantity_delivered_qty * (Decimal('1') - retention))
            
            # Calculate amount_payable
            self.amount_payable = round_decimal(self.quantity_payable * unit_price_val)
            
        except (TypeError, ValueError, InvalidOperation) as e:
            # Logger l'erreur pour le débogage
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Erreur de calcul pour Reception {self.id}: {str(e)}")
            
            # Passer les calculs en cas d'erreur
            self.amount_delivered = Decimal('0')
            self.quantity_payable = Decimal('0')
            self.amount_payable = Decimal('0')
        
        # Mettre à jour update_fields pour inclure les champs calculés
        if 'update_fields' in kwargs and kwargs['update_fields'] is not None:
            update_fields = set(kwargs['update_fields'])
            update_fields.update(['amount_delivered', 'quantity_payable', 'amount_payable', 'business_id'])
            kwargs['update_fields'] = list(update_fields)
        
        # Sauvegarder l'objet
        return super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Réception"
        verbose_name_plural = "Réceptions"
        indexes = [
            models.Index(fields=['bon_commande', 'fichier']),
            models.Index(fields=['date_modification']),
        ]
        ordering = ['-date_modification']
    
    def __str__(self):
        return f"Réception pour {self.bon_commande.numero} - ID métier: {self.business_id or 'N/A'}"


class ActivityLog(models.Model):
    """
    Journal d'activité pour les modifications des quantités reçues (Quantity Delivered).
    """
    # Information sur le bon de commande
    bon_commande = models.CharField(max_length=100, verbose_name="Numéro de bon de commande")
    fichier = models.ForeignKey(
        'FichierImporte',
        on_delete=models.CASCADE,
        related_name='activity_logs',
        verbose_name="Fichier importé"
    )
    
    # Information sur la ligne modifiée via business_id
    business_id = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        verbose_name="ID métier de la ligne",
        help_text="Identifiant métier de la ligne modifiée"
    )
    item_reference = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Référence de l'article"
    )
    
    # Valeurs de quantités
    ordered_quantity = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        verbose_name="Ordered Quantity"
    )
    quantity_delivered = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        verbose_name="Quantity Delivered"
    )
    quantity_not_delivered = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        verbose_name="Quantity Not Delivered"
    )
    cumulative_recipe = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        verbose_name="Cumulative Recipe",
        null=True,
        blank=True
    )
    
    # Information sur l'utilisateur et la date/heure
    user = models.CharField(max_length=150, blank=True, null=True, verbose_name="Utilisateur")
    action_date = models.DateTimeField(
        default=timezone.now,
        verbose_name="Date et heure de l'action"
    )
    
    # Taux d'avancement au moment de la réception
    progress_rate = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        verbose_name="Taux d'avancement",
        null=True,
        blank=True
    )
    
    class Meta:
        verbose_name = "Journal d'activité"
        verbose_name_plural = "Journal d'activité"
        ordering = ['-action_date']
    
    def __str__(self):
        return f"{self.bon_commande} - ID métier: {self.business_id or 'N/A'} - {self.action_date.strftime('%Y-%m-%d %H:%M')}"


class MSRNReport(models.Model):
    """
    Modèle pour stocker les rapports MSRN (Material Shipping and Receiving Note) générés
    """
    report_number = models.CharField(
        max_length=10, 
        unique=True, 
        verbose_name="Report Number"
    )
    bon_commande = models.ForeignKey(
        NumeroBonCommande, 
        on_delete=models.CASCADE,
        related_name='msrn_reports',
        verbose_name="Bon de commande"
    )
    pdf_file = models.FileField(
        upload_to='msrn_reports/',
        verbose_name="Fichier PDF"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de création"
    )
    retention_rate = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0,
        verbose_name="Taux de rétention (%)",
        help_text="Taux de rétention appliqué (0-100%)"
    )
    retention_cause = models.TextField(
        null=True,
        blank=True,
        verbose_name="Cause de la rétention",
        help_text="Raison de la rétention appliquée"
    )
    retention_amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0,
        verbose_name="Montant de la rétention",
        help_text="Montant retenu (calculé automatiquement)"
    )
    payable_amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0,
        verbose_name="Montant payable après rétention",
        help_text="Montant total à payer après déduction de la rétention"
    )
    
    # Snapshots pour préserver les valeurs au moment de la création du rapport
    montant_total_snapshot = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Snapshot - Montant total",
        help_text="Montant total au moment de la création du rapport"
    )
    montant_recu_snapshot = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Snapshot - Montant reçu",
        help_text="Montant reçu au moment de la création du rapport"
    )
    progress_rate_snapshot = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Snapshot - Taux d'avancement",
        help_text="Taux d'avancement au moment de la création du rapport"
    )
    retention_rate_snapshot = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Snapshot - Taux de rétention",
        help_text="Taux de rétention au moment de la création du rapport"
    )
    retention_amount_snapshot = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Snapshot - Montant de rétention",
        help_text="Montant de rétention au moment de la création du rapport"
    )
    payable_amount_snapshot = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Snapshot - Montant payable",
        help_text="Montant payable au moment de la création du rapport"
    )
    receptions_data_snapshot = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Snapshot - Données des réceptions",
        help_text="Snapshot complet des réceptions au moment de la création du rapport"
    )
    user = models.CharField(
        max_length=150, 
        blank=True, 
        null=True, 
        verbose_name="Utilisateur"
    )
    
    class Meta:
        verbose_name = "Rapport MSRN"
        verbose_name_plural = "Rapports MSRN"
        ordering = ['-created_at']
    
    def save(self, *args, **kwargs):
        # Si le report_number n'est pas défini, on le génère
        if not self.report_number:
            # Générer un numéro au format MSRN250353 (MSRN + année + séquence)
            from datetime import datetime
            current_year = datetime.now().year
            year_suffix = str(current_year)[-2:]  # Prendre les 2 derniers chiffres de l'année
            
            # Trouver le prochain numéro séquentiel pour cette année
            year_prefix = f"MSRN{year_suffix}"
            existing_reports = MSRNReport.objects.filter(
                report_number__startswith=year_prefix
            ).order_by('-report_number')
            
            if existing_reports.exists():
                # Extraire le numéro séquentiel du rapport le plus récent
                latest_number = existing_reports.first().report_number
                sequence_part = latest_number[6:]  # Prendre les 4 derniers chiffres après "MSRN25"
                next_sequence = int(sequence_part) + 1
            else:
                # Premier rapport de l'année
                next_sequence = 1
            
            # Formater le numéro séquentiel sur 4 chiffres
            sequence_formatted = f"{next_sequence:04d}"
            self.report_number = f"{year_prefix}{sequence_formatted}"
            
            # Capturer les snapshots au moment de la création du rapport
            self.montant_total_snapshot = self.bon_commande.montant_total() or Decimal('0')
            self.montant_recu_snapshot = self.bon_commande.montant_recu() or Decimal('0')
            self.progress_rate_snapshot = Decimal(self.bon_commande.taux_avancement())
            self.retention_rate_snapshot = self.retention_rate or Decimal('0')
            self.retention_amount_snapshot = self.retention_amount or Decimal('0')
            self.payable_amount_snapshot = self.payable_amount or Decimal('0')
            
            # Capturer le snapshot des données des réceptions si pas déjà défini
            if not self.receptions_data_snapshot:
                from .models import Reception
                receptions = Reception.objects.filter(bon_commande=self.bon_commande)
                receptions_snapshot = []
                retention_rate = self.retention_rate or Decimal('0')
                
                for reception in receptions:
                    # Calculer les valeurs avec le taux de rétention
                    factor = Decimal('1') - (retention_rate / Decimal('100'))
                    quantity_payable = reception.quantity_delivered * factor
                    amount_payable = reception.amount_delivered * factor
                    
                    # Récupérer line_description et line depuis les fichiers
                    line_description = "N/A"
                    line = "N/A"
                    schedule = "N/A"
                                        
                    for fichier in self.bon_commande.fichiers.all():
                        for ligne in fichier.lignes.filter(business_id=reception.business_id):
                            contenu = ligne.contenu or {}

                            # 1) Essayer les clés exactes utilisées à l'import
                            if 'Line Description' in contenu and contenu['Line Description']:
                                ld_val = str(contenu['Line Description']).strip()
                                if ld_val:
                                    line_description = ld_val[:50] + "..." if len(ld_val) > 50 else ld_val
                            if 'Line' in contenu and contenu['Line'] not in (None, ''):
                                line = str(contenu['Line']).strip()
                            if 'Schedule' in contenu and contenu['Schedule'] not in (None, ''):
                                schedule = str(contenu['Schedule']).strip()   

                            # 2) Fallback tolérant si non trouvées
                            if line_description == "N/A":
                                for key, value in contenu.items():
                                    if not key:
                                        continue
                                    norm = key.strip().lower().replace('_', ' ')
                                    norm = ' '.join(norm.split())
                                    if value and (norm == 'line description' or ('description' in norm and 'line' in norm)):
                                        v = str(value).strip()
                                        if v:
                                            line_description = v[:50] + "..." if len(v) > 50 else v
                                            break
                            if line == "N/A":
                                for key, value in contenu.items():
                                    if not key:
                                        continue
                                    norm = key.strip().lower().replace('_', ' ')
                                    norm = ' '.join(norm.split())
                                    # Eviter 'line type' et 'line description'
                                    if value and norm == 'line':
                                        line = str(value).strip()
                                        break
                                    if value and ('line' in norm and 'description' not in norm and 'type' not in norm):
                                        line = str(value).strip()
                                        break
                            if line == "N/A":
                                for key, value in contenu.items():
                                    if not key:
                                        continue
                                    norm = key.strip().lower().replace('_', ' ')
                                    norm = ' '.join(norm.split())
                                    # Eviter 'line type' et 'line description'
                                    if value and norm == 'line':
                                        line = str(value).strip()
                                        break
                                    if value and ('line' in norm and 'description' not in norm and 'type' not in norm):
                                        line = str(value).strip()
                                        break

                            if line_description != "N/A" or line != "N/A" or schedule != "N/A":
                                break
                        if line_description != "N/A" or line != "N/A" or schedule != "N/A":
                            break    
                    
                    receptions_snapshot.append({
                        'id': reception.id,
                        'line_description': line_description,
                        'ordered_quantity': str(reception.ordered_quantity if reception.ordered_quantity is not None else Decimal('0')),
                        'received_quantity': str(reception.received_quantity if reception.received_quantity is not None else Decimal('0')),
                        'quantity_delivered': str(reception.quantity_delivered if reception.quantity_delivered is not None else Decimal('0')),
                        'quantity_not_delivered': str(reception.quantity_not_delivered if reception.quantity_not_delivered is not None else Decimal('0')),
                        'amount_delivered': str(reception.amount_delivered if reception.amount_delivered is not None else Decimal('0')),
                        'quantity_payable': str(quantity_payable),
                        'amount_payable': str(amount_payable),
                        'line': line,
                        'schedule': schedule
                    })
                
                self.receptions_data_snapshot = receptions_snapshot
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"MSRN-{self.report_number} for {self.bon_commande.numero}"

    @property
    def progress_rate(self):
        """
        Taux d'avancement du PO au moment de la création de CE MSRN.
        Logique:
        - Cherche dans `ActivityLog` la dernière entrée du même bon dont `action_date <= created_at`.
          Utilise son `progress_rate` (snapshot stocké lors de la réception).
        - Si aucune entrée pertinente, fallback sur `NumeroBonCommande.taux_avancement()` (dynamique actuel).
        Remarque: ce taux est indépendant de la rétention.
        """
        try:
            from decimal import Decimal
            # 1) Essayer de récupérer le snapshot depuis ActivityLog (même bon, avant ou à la création du MSRN)
            log = (
                ActivityLog.objects
                .filter(
                    bon_commande=self.bon_commande.numero,
                    action_date__lte=self.created_at,
                    progress_rate__isnull=False,
                )
                .order_by('-action_date', '-id')
                .first()
            )
            if log and log.progress_rate is not None:
                return Decimal(log.progress_rate)

            # 2) Fallback sur le taux d'avancement dynamique du bon
            return Decimal(self.bon_commande.taux_avancement())
        except Exception:
            try:
                from decimal import Decimal
                return Decimal('0')
            except Exception:
                return 0


class InitialReceptionBusiness(models.Model):
    """
    Valeurs initiales calculées PAR business_id, indépendantes des réceptions.
    Calculées EXCLUSIVEMENT depuis le fichier importé (ligne courante):
    - received_quantity
    - montant_total_initial = Ordered Quantity × Price
    - montant_recu_initial = Received Quantity × Price
    - taux_avancement_initial = (montant_recu_initial / montant_total_initial) × 100
    """
    business_id = models.CharField(
        max_length=500,
        unique=True,
        db_index=True,
        verbose_name="ID métier"
    )
    bon_commande = models.ForeignKey(
        NumeroBonCommande,
        on_delete=models.CASCADE,
        related_name='initial_reception_lines',
        verbose_name="Bon de commande"
    )
    source_file = models.ForeignKey(
        'FichierImporte',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='initial_reception_lines',
        verbose_name="Fichier source"
    )
    received_quantity = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Received Quantity"
    )
    montant_total_initial = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Montant total initial"
    )
    montant_recu_initial = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Montant reçu initial"
    )
    taux_avancement_initial = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Taux d'avancement initial (%)"
    )
    date_mise_a_jour = models.DateTimeField(
        auto_now=True,
        verbose_name="Date de mise à jour"
    )

    class Meta:
        verbose_name = "Valeur initiale (business)"
        verbose_name_plural = "Valeurs initiales (business)"
        ordering = ['-date_mise_a_jour']

    def save(self, *args, **kwargs):
        # Normaliser le business_id avant sauvegarde pour éviter les doublons
        if self.business_id:
            self.business_id = normalize_business_id(self.business_id)
        
        # Mettre à jour update_fields pour inclure business_id si spécifié
        if 'update_fields' in kwargs and kwargs['update_fields'] is not None:
            update_fields = set(kwargs['update_fields'])
            update_fields.add('business_id')
            kwargs['update_fields'] = list(update_fields)
        
        super().save(*args, **kwargs)

    def __str__(self):
        return f"IRV-BI {self.business_id} ({self.bon_commande.numero})"

 

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.models import F, Sum, Case, When, Value, FloatField

@receiver(post_save, sender=NumeroBonCommande)
def update_receptions_on_retention_rate_change(sender, instance, created, **kwargs):
    """
    Signal pour recalculer quantity_payable de toutes les réceptions
    lorsque le taux de rétention change
    """
    if created:
        return

    try:
        old_instance = NumeroBonCommande.objects.get(pk=instance.pk)
        if old_instance.retention_rate == instance.retention_rate:
            return
    except NumeroBonCommande.DoesNotExist:
        return

    from decimal import Decimal
    receptions = Reception.objects.filter(bon_commande=instance)
    
    for reception in receptions:
        # Recalculer quantity_payable avec le nouveau taux
        retention_rate = instance.retention_rate if instance.retention_rate is not None else Decimal('0')
        retention = Decimal(str(retention_rate)) / Decimal('100')
        reception.quantity_payable = reception.quantity_delivered * (Decimal('1') - retention)
        
        # Sauvegarder sans déclencher les signaux pour éviter les boucles
        reception.save(update_fields=['quantity_payable'])


class TimelineDelay(models.Model):
    """
    Modèle pour gérer la répartition des retards indépendamment de l'évaluation fournisseur
    """
    bon_commande = models.OneToOneField(
        NumeroBonCommande,
        on_delete=models.CASCADE,
        related_name='timeline_delay',
        verbose_name="Bon de commande"
    )
    delay_part_mtn = models.IntegerField(default=0, verbose_name="Part MTN (jours)")
    delay_part_force_majeure = models.IntegerField(default=0, verbose_name="Part Force Majeure (jours)")
    delay_part_vendor = models.IntegerField(default=0, verbose_name="Part Fournisseur (jours)")
    
    # Montants calculés pour la timeline
    retention_amount_timeline = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Montant Rétention Timeline"
    )
    retention_rate_timeline = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Taux Rétention Timeline (%)"
    )
    
    date_creation = models.DateTimeField(auto_now_add=True, verbose_name="Date de création")
    date_modification = models.DateTimeField(auto_now=True, verbose_name="Date de modification")
    
    class Meta:
        verbose_name = "Timeline Delay"
        verbose_name_plural = "Timeline Delays"
    
    def calculate_retention_timeline(self):
        """Calcule le montant et le taux de rétention timeline"""
        # Récupérer le PO Amount depuis le bon de commande
        po_amount = self.bon_commande.montant_total()
        
        # Montant rétention timeline = PO Amount * 0.3% * Part Fournisseur
        retention_amount_timeline = po_amount * Decimal('0.003') * Decimal(str(self.delay_part_vendor))
        
        # Taux rétention timeline = (Montant rétention / PO Amount) si <= 10%, sinon 10%
        if po_amount > 0:
            retention_rate_timeline = (retention_amount_timeline / po_amount) * Decimal('100')
            if retention_rate_timeline > Decimal('10'):
                # Recalculer le montant à 10% du PO Amount
                retention_amount_timeline = po_amount * Decimal('0.10')
                # Le taux est directement 10%
                retention_rate_timeline = Decimal('10')
        else:
            retention_rate_timeline = Decimal('0')
            retention_amount_timeline = Decimal('0')
        
        return retention_amount_timeline, retention_rate_timeline
    
    def save(self, *args, **kwargs):
        """Calcule automatiquement les montants avant sauvegarde"""
        self.retention_amount_timeline, self.retention_rate_timeline = self.calculate_retention_timeline()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Timeline Delays - {self.bon_commande.numero}"


class VendorEvaluation(models.Model):
    """
    Modèle pour stocker les évaluations des fournisseurs
    """
    CRITERIA_CHOICES = {
        'delivery_compliance': {
            0: 'Non conforme',
            1: 'Non conforme',
            2: 'Conformité : 25% par rapport au besoin exprimé',
            3: 'Conformité : 25% par rapport au besoin exprimé',
            4: 'Conformité : 25% par rapport au besoin exprimé',
            5: 'Conformité : 50% par rapport au besoin exprimé',
            6: 'Conformité : 50% par rapport au besoin exprimé',
            7: 'Conforme au besoin',
            8: 'Conforme au besoin',
            9: 'Conforme au besoin',
            10: 'Supérieure / Meilleur que le besoin exprimé par MTN CI mais au même coût'
        },
        'delivery_timeline': {
            0: 'Aucune livraison effectuée',
            1: 'Aucune livraison effectuée',
            2: 'Retard dans la livraison sans le notifier à MTN CI',
            3: 'Retard dans la livraison sans le notifier à MTN CI',
            4: 'Retard négocié avec MTN CI et non respect du nouveau planning avec explication donné à MTN',
            5: 'Retard négocié avec MTN CI et non respect du nouveau planning avec explication donné à MTN',
            6: 'Retard négocié avec MTN CI et non respect du nouveau planning avec explication donné à MTN',
            7: 'Respect des délais',
            8: 'Respect des délais',
            9: 'Respect des délais',
            10: 'En avance sur le délai de livraison prévue'
        },
        'advising_capability': {
            0: 'Conseil inexistant',
            1: 'Conseil inexistant',
            2: 'Sur demande de MTN CI - Conseil donné mais pas utile',
            3: 'Sur demande de MTN CI - Conseil donné mais pas utile',
            4: 'Sur demande de MTN CI - Conseil donné utile mais incomplet',
            5: 'Sur demande de MTN CI - Conseil donné utile mais incomplet',
            6: 'Sur demande de MTN CI - Conseil donné utile mais incomplet',
            7: 'Capacité à conseiller répond à nos attentes',
            8: 'Capacité à conseiller répond à nos attentes',
            9: 'Capacité à conseiller répond à nos attentes',
            10: 'Transfert de compétence & formation régulière du client'
        },
        'after_sales_qos': {
            0: 'SAV inexistant',
            1: 'SAV inexistant',
            2: 'Pas adapté à nos attentes',
            3: 'Pas adapté à nos attentes',
            4: 'Adapté à 50% à nos attentes sans respecter les délais',
            5: 'Adapté à 50% à nos attentes sans respecter les délais',
            6: 'Adapté à 50% à nos attentes sans respecter les délais',
            7: '100% des requêtes et des plaintes résolues dans les délais',
            8: '100% des requêtes et des plaintes résolues dans les délais',
            9: '100% des requêtes et des plaintes résolues dans les délais',
            10: 'Anticipation des problèmes / Aucun incident n\'est à signaler'
        },
        'vendor_relationship': {
            0: 'Aucun contact',
            1: 'Aucun contact',
            2: 'Injoignable en dehors des visites / événements / pendant l\'exécution d\'une commande',
            3: 'Injoignable en dehors des visites / événements / pendant l\'exécution d\'une commande',
            4: 'Joignable après 2 ou 3 jours de relance, rappels …',
            5: 'Joignable après 2 ou 3 jours de relance, rappels …',
            6: 'Joignable après 2 ou 3 jours de relance, rappels …',
            7: 'Bon contact / Prestataire réactif',
            8: 'Bon contact / Prestataire réactif',
            9: 'Bon contact / Prestataire réactif',
            10: 'Bon contact / Prestataire très réactif'
        }
    }

    bon_commande = models.ForeignKey(
        NumeroBonCommande,
        on_delete=models.CASCADE,
        related_name='vendor_evaluations',
        verbose_name="Bon de commande"
    )
    supplier = models.CharField(
        max_length=255,
        verbose_name="Fournisseur"
    )
    
    # Critères d'évaluation (notes de 0 à 10)
    delivery_compliance = models.IntegerField(
        choices=[(i, f"{i}") for i in range(11)],
        verbose_name="Delivery Compliance to Order (Quantity & Quality)",
        help_text="Note de 0 à 10"
    )
    delivery_timeline = models.IntegerField(
        choices=[(i, f"{i}") for i in range(11)],
        verbose_name="Delivery Execution Timeline",
        help_text="Note de 0 à 10"
    )
    advising_capability = models.IntegerField(
        choices=[(i, f"{i}") for i in range(11)],
        verbose_name="Vendor Advising Capability",
        help_text="Note de 0 à 10"
    )
    after_sales_qos = models.IntegerField(
        choices=[(i, f"{i}") for i in range(11)],
        verbose_name="After Sales Services QOS",
        help_text="Note de 0 à 10"
    )
    vendor_relationship = models.IntegerField(
        choices=[(i, f"{i}") for i in range(11)],
        verbose_name="Vendor Relationship",
        help_text="Note de 0 à 10"
    )
    
    # Note finale calculée automatiquement
    vendor_final_rating = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Vendor Final Rating",
        help_text="Moyenne des 5 critères (calculée automatiquement)"
    )
    
    # Métadonnées
    evaluator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Évaluateur"
    )
    date_evaluation = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date d'évaluation"
    )
    date_modification = models.DateTimeField(
        auto_now=True,
        verbose_name="Date de modification"
    )

    class Meta:
        verbose_name = "Évaluation fournisseur"
        verbose_name_plural = "Évaluations fournisseurs"
        ordering = ['-date_evaluation']
        unique_together = ['bon_commande', 'supplier']

    def __str__(self):
        return f"Évaluation {self.supplier} - {self.bon_commande.numero}"

    def save(self, *args, **kwargs):
        """Calcule automatiquement la moyenne avant la sauvegarde"""
        scores = [
            self.delivery_compliance,
            self.delivery_timeline,
            self.advising_capability,
            self.after_sales_qos,
            self.vendor_relationship
        ]
        self.vendor_final_rating = Decimal(str(sum(scores) / len(scores))) if scores else Decimal('0.00')
        super().save(*args, **kwargs)

    def get_criteria_description(self, criteria_name, score):
        """Retourne la description du critère pour une note donnée"""
        if criteria_name in self.CRITERIA_CHOICES:
            return self.CRITERIA_CHOICES[criteria_name].get(score, f"Score: {score}")
        return f"Score: {score}"

    def get_total_score(self):
        """Calcule le score total sur 50"""
        return (
            self.delivery_compliance +
            self.delivery_timeline +
            self.advising_capability +
            self.after_sales_qos +
            self.vendor_relationship
        )
