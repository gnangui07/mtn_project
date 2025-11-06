"""
But:
- Fournir des endpoints analytiques simplifiés pour le tableau de bord.

Étapes:
- Calculer le nombre de bons avec réception et le total des bons.
- Déduire le nombre sans réception et renvoyer une structure JSON prête pour les graphiques.

Entrées:
- Requête HTTP GET.

Sorties:
- JsonResponse avec les clés: status, bons_avec_reception, total_bons, pie_chart.
"""
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
    """But:
    - Récupérer des métriques synthétiques pour alimenter le dashboard.

    Étapes:
    - Compter les bons ayant au moins une réception.
    - Compter le total des bons.
    - Calculer les bons sans réception et structurer la réponse.

    Entrées:
    - HttpRequest GET.

    Sorties:
    - JsonResponse(status='success', ...), ou 'error' en cas d'exception.
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
