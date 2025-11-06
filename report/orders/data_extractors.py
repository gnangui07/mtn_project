"""But:
- Fournir des fonctions simples pour extraire des champs utiles d'une ligne importée.

Étapes:
- Lire le contenu de la ligne.
- Rechercher la clé pertinente (tolérance sur variantes de libellés).
- Retourner la valeur normalisée ou une valeur par défaut.

Entrées:
- `ligne`: objet avec attribut `contenu` (dict de colonnes->valeurs).

Sorties:
- Valeurs extraites (str/float/Decimal) ou "N/A"/0 selon la fonction.
"""
import logging
from decimal import Decimal, InvalidOperation

# Configuration du logger
logger = logging.getLogger(__name__)


def get_price_from_ligne(ligne):
    """Extrait le prix unitaire d'une ligne de fichier"""
    if not ligne or not ligne.contenu:
        return 0.0
    
    contenu = ligne.contenu
    
    # Chercher la colonne Prix/Price dans la ligne
    for key, value in contenu.items():
        key_lower = key.lower() if key else ''
        if ('price' in key_lower or 'prix' in key_lower or 'unit price' in key_lower or 'prix unitaire' in key_lower) and value:
            try:
                # Essayer de convertir en nombre
                return float(str(value).replace(',', '.').strip())
            except (ValueError, TypeError):
                pass
    
    return 0.0


def get_supplier_from_ligne(ligne):
    """Extrait le fournisseur d'une ligne de fichier"""
    if not ligne or not ligne.contenu:
        return "N/A"
    
    contenu = ligne.contenu
    
    # Chercher la colonne Supplier/Fournisseur dans la ligne
    for key, value in contenu.items():
        key_lower = key.lower() if key else ''
        if 'supplier' in key_lower and value:
            return str(value)
    
    # Chercher d'autres colonnes qui pourraient contenir le fournisseur
    for key, value in contenu.items():
        key_lower = key.lower() if key else ''
        if ('fournisseur' in key_lower or 'vendeur' in key_lower or 'vendor' in key_lower) and value:
            return str(value)
    
    return "N/A"


def get_ordered_date_from_ligne(ligne):
    """Extrait la date de commande (Ordered) d'une ligne de fichier"""
    if not ligne or not ligne.contenu:
        return "N/A"
    
    contenu = ligne.contenu
    
    # Chercher la colonne Ordered dans la ligne
    for key, value in contenu.items():
        key_lower = key.lower() if key else ''
        if key_lower == 'ordered' and value:
            return str(value)
    
    # Chercher d'autres colonnes qui pourraient contenir la date de commande
    for key, value in contenu.items():
        key_lower = key.lower() if key else ''
        if ('date' in key_lower and 'order' in key_lower) or ('date' in key_lower and 'commande' in key_lower) and value:
            return str(value)
    
    return "N/A"


def get_project_number_from_ligne(ligne):
    """Extrait le numéro de projet d'une ligne de fichier"""
    if not ligne or not ligne.contenu:
        return "N/A"
    
    contenu = ligne.contenu
    
    # Chercher la colonne Project Number dans la ligne
    for key, value in contenu.items():
        key_lower = key.lower() if key else ''
        if ('project' in key_lower and 'number' in key_lower) or ('projet' in key_lower and 'numero' in key_lower) and value:
            return str(value)
    
    # Chercher d'autres colonnes qui pourraient contenir le numéro de projet
    for key, value in contenu.items():
        key_lower = key.lower() if key else ''
        if ('project' in key_lower or 'projet' in key_lower) and value:
            return str(value)
    
    return "N/A"


def get_task_number_from_ligne(ligne):
    """Extrait le numéro de tâche d'une ligne de fichier"""
    if not ligne or not ligne.contenu:
        return "N/A"
    
    contenu = ligne.contenu
    
    # Chercher la colonne Task Number dans la ligne
    for key, value in contenu.items():
        key_lower = key.lower() if key else ''
        if ('task' in key_lower and 'number' in key_lower) or ('tache' in key_lower and 'numero' in key_lower) and value:
            return str(value)
    
    # Chercher d'autres colonnes qui pourraient contenir le numéro de tâche
    for key, value in contenu.items():
        key_lower = key.lower() if key else ''
        if ('task' in key_lower or 'tache' in key_lower) and value:
            return str(value)
    
    return "N/A"


def get_order_description_from_ligne(ligne):
    """Extrait la description de commande d'une ligne de fichier"""
    if not ligne or not ligne.contenu:
        return "N/A"
    
    contenu = ligne.contenu
    
    # Chercher la colonne Order Description dans la ligne
    for key, value in contenu.items():
        key_lower = key.lower() if key else ''
        if ('order' in key_lower and 'description' in key_lower) or ('commande' in key_lower and 'description' in key_lower) and value:
            return str(value)
    
    # Chercher d'autres colonnes qui pourraient contenir la description de commande
    for key, value in contenu.items():
        key_lower = key.lower() if key else ''
        if 'description' in key_lower and value and 'line' not in key_lower:
            return str(value)
    
    return "N/A"


def get_schedule_from_ligne(ligne):
    """Extrait le schedule d'une ligne de fichier"""
    if not ligne or not ligne.contenu:
        return "N/A"
    
    contenu = ligne.contenu
    
    # Chercher la colonne Schedule dans la ligne
    for key, value in contenu.items():
        key_lower = key.lower() if key else ''
        if 'schedule' in key_lower and value:
            return str(value)
    
    # Chercher d'autres colonnes qui pourraient contenir le schedule
    for key, value in contenu.items():
        key_lower = key.lower() if key else ''
        if ('planning' in key_lower or 'calendrier' in key_lower or 'echeance' in key_lower) and value:
            return str(value)
    
    return "N/A"


def get_line_from_ligne(ligne):
    """Extrait le numéro de ligne d'une ligne de fichier"""
    if not ligne or not ligne.contenu:
        return "N/A"
    
    contenu = ligne.contenu
    
    # Chercher la colonne Line/Ligne dans la ligne
    for key, value in contenu.items():
        key_lower = key.lower() if key else ''
        if 'line' in key_lower and 'description' not in key_lower and value:
            return str(value)
    
    # Si non trouvé, essayer d'autres noms de colonnes
    for key, value in contenu.items():
        key_lower = key.lower() if key else ''
        if ('ligne' in key_lower and 'description' not in key_lower) and value:
            return str(value)
    
    return "N/A"


def calculate_quantity_payable(ligne):
    """Calcule la quantité payable (quantity_delivered * unit_price) pour une ligne"""
    if not ligne or not ligne.contenu:
        return Decimal('0.00')
    
    try:
        # Récupérer la quantité reçue
        quantity_delivered_qty = Decimal(str(ligne.contenu.get('Quantity Delivered', 0)) or '0')
        
        # Récupérer le prix unitaire
        unit_price = Decimal('0.00')
        for key, value in ligne.contenu.items():
            key_lower = str(key).lower() if key else ''
            if any(term in key_lower for term in ['price', 'prix', 'unit price', 'prix unitaire']):
                try:
                    unit_price = Decimal(str(value).replace(',', '.').strip() or '0')
                    break
                except (InvalidOperation, TypeError):
                    continue
        
        return (quantity_delivered_qty * unit_price).quantize(Decimal('0.01'))
    except Exception as e:
        logger.error(f"Erreur lors du calcul de la quantité payable: {e}")
        return Decimal('0.00')
