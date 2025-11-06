"""But:
- Fournir un petit endpoint qui renvoie seulement le montant de pénalité due (sans générer un PDF).

Étapes:
- Vérifier l'authentification et récupérer le bon.
- Calculer le contexte de pénalité.
- Extraire et formater uniquement la pénalité due.
- Retourner un JSON simple.

Entrées:
- `bon_id` (int) dans l'URL.

Sorties:
- JsonResponse: { penalty_due, currency, success }.
"""

from django.http import JsonResponse, Http404
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
    # Récupère le bon (retourne 404 si introuvable)
    bon_commande = get_object_or_404(NumeroBonCommande, id=bon_id)

    try:
        # Collecter uniquement les données nécessaires pour le calcul
        context = collect_penalty_context(bon_commande)

        # Extraire la pénalité due
        penalty_due = context.get("penalties_due", 0)
        currency = context.get("currency", "")

        # Formater le montant pour l'affichage (espaces comme séparateurs de milliers)
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

    except Http404:
        # Laisser passer les 404 non transformés en 500
        raise
    except Exception as e:
        # En cas d'erreur imprévue, renvoyer un JSON d'erreur
        return JsonResponse({"error": str(e), "success": False}, status=500)
