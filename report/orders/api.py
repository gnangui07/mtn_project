"""
Point d'entrée principal pour toutes les APIs
Ce fichier importe et expose les fonctions des modules spécialisés
"""

# Import des fonctions utilitaires d'extraction de données
from .data_extractors import (
    get_price_from_ligne,
    get_supplier_from_ligne, 
    get_ordered_date_from_ligne,
    get_project_number_from_ligne,
    get_task_number_from_ligne,
    get_order_description_from_ligne,
    get_schedule_from_ligne,
    get_line_from_ligne
)

# Import des APIs de réception
from .reception_api import (
    update_quantity_delivered,
    reset_quantity_delivered,
    
)

# Import des APIs d'activité
from .activity_api import (
    get_activity_logs,
    get_all_bons,
    get_additional_data_for_reception
)

# Toutes les fonctions sont maintenant disponibles via ce module
# Exemple d'utilisation :
# from orders.api import update_quantity_delivered, get_activity_logs

__all__ = [
    # Extracteurs de données
    'get_price_from_ligne',
    'get_supplier_from_ligne',
    'get_ordered_date_from_ligne', 
    'get_project_number_from_ligne',
    'get_task_number_from_ligne',
    'get_order_description_from_ligne',
    'get_schedule_from_ligne',
    'get_line_from_ligne',
    
    # APIs de réception
    'update_quantity_delivered',
    'reset_quantity_delivered',
    
    # APIs d'activité
    'get_activity_logs',
    'get_all_bons',
    'get_additional_data_for_reception'
]
