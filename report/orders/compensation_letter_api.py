"""API endpoint for generating compensation request letter."""
from __future__ import annotations

import json
import threading
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth.decorators import login_required
from django.utils.encoding import iri_to_uri
from django.shortcuts import get_object_or_404

from .models import NumeroBonCommande
from .penalty_data import collect_penalty_context
from .compensation_letter_report import generate_compensation_letter
from .emails import send_penalty_notification


@csrf_protect
@login_required
def generate_compensation_letter_api(request, bon_id: int):
    """Return the Compensation Request Letter PDF for the given PO."""
    if request.method not in {"GET", "POST"}:
        return JsonResponse({"success": False, "error": "Méthode non autorisée"}, status=405)

    try:
        bon_commande = get_object_or_404(NumeroBonCommande, id=bon_id)
        
        # Collect penalty context data
        context = collect_penalty_context(bon_commande)
        
        # Generate PDF
        pdf_buffer = generate_compensation_letter(
            bon_commande,
            context=context,
            user_email=getattr(request.user, "email", None),
        )
        
        # Envoyer la notification email en arrière-plan (asynchrone)
        def send_email_async():
            try:
                send_penalty_notification(
                    bon_commande=bon_commande,
                    pdf_buffer=pdf_buffer,
                    user_email=getattr(request.user, "email", None),
                    report_type='compensation_letter'
                )
            except Exception as e:
                pass
        
        email_thread = threading.Thread(target=send_email_async, daemon=True)
        email_thread.start()
        
        # Prepare response
        response = HttpResponse(pdf_buffer.read(), content_type="application/pdf")
        filename = f"Lettre_Compensation_{bon_commande.numero}.pdf"
        safe_filename = iri_to_uri(filename)
        response["Content-Disposition"] = f'inline; filename="{safe_filename}"'
        
        return response
        
    except Exception as e:
        return JsonResponse({
            "success": False,
            "error": f"Erreur lors de la génération de la lettre: {str(e)}"
        }, status=500)
