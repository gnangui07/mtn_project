"""
API endpoint léger pour récupérer uniquement le montant de la pénalité due.
Optimisé pour être rapide et ne pas générer tout le PDF.
"""

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.shortcuts import get_object_or_404
from django.utils.encoding import iri_to_uri
from .models import NumeroBonCommande
from .penalty_data import collect_penalty_context


@login_required
@require_http_methods(["GET"])
def get_penalty_amount_api(request, bon_id):
    """
    Endpoint léger pour récupérer uniquement le montant de la pénalité due.
    Retourne un JSON avec la pénalité calculée.
    """
    try:
        bon_commande = get_object_or_404(NumeroBonCommande, id=bon_id)
        
        # Collecter uniquement les données nécessaires pour le calcul
        context = collect_penalty_context(bon_commande)
        
        # Extraire la pénalité due
        penalty_due = context.get("penalties_due", 0)
        currency = context.get("currency", "")
        
        # Formater le montant
        try:
            if penalty_due:
                formatted_amount = f"{float(penalty_due):,.0f}".replace(",", " ")
            else:
                formatted_amount = "0"
        except (ValueError, TypeError):
            formatted_amount = "0"
        
        return JsonResponse({
            "penalty_due": formatted_amount,
            "currency": currency,
            "success": True
        })
        
    except Exception as e:
        return JsonResponse({
            "error": str(e),
            "success": False
        }, status=500)
