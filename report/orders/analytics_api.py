from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
import logging
import traceback
from django.db.models import Sum, Count, F
from .models import ActivityLog, NumeroBonCommande, Reception

# Configuration du logger
logger = logging.getLogger(__name__)

# Fonction get_heatmap_data supprimée (carte thermique retirée)

@require_http_methods(["GET"])
def get_analytics_data(request):
    """
    Récupère les données analytiques simplifiées pour le tableau de bord:
    1. Nombre de bons avec réception
    2. Total des bons
    3. Graphique circulaire: bons avec réception vs sans réception
    """
    try:
        # 1. Nombre de bons avec réception (au moins une réception)
        bons_avec_reception = Reception.objects.filter(
            quantity_delivered__gt=0
        ).values('bon_commande').distinct()
        nb_bons_avec_reception = bons_avec_reception.count()    
        
        # 2. Récupérer le nombre total de bons de commande
        total_bons = NumeroBonCommande.objects.count()
        
        # 3. Données pour le graphique circulaire: bons avec réception vs sans réception
        nb_bons_sans_reception = total_bons - nb_bons_avec_reception
        
        # Préparer la réponse simplifiée
        response_data = {
            'status': 'success',
            'bons_avec_reception': nb_bons_avec_reception,
            'total_bons': total_bons,
            
            # Données pour le graphique circulaire
            'pie_chart': {
                'labels': ['Bons avec réception', 'Bons sans réception'],
                'values': [nb_bons_avec_reception, nb_bons_sans_reception]
            }
        }
        
        return JsonResponse(response_data)
    
    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"Erreur lors de la récupération des données analytiques: {str(e)}\n{error_trace}")
        print(f"ERREUR ANALYTICS: {str(e)}\n{error_trace}")  # Debug console
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
