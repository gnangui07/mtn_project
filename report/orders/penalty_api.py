"""API endpoints related to penalty sheet generation."""
from __future__ import annotations

import json
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth.decorators import login_required
from django.utils.encoding import iri_to_uri
from django.core.mail import send_mail
from django.conf import settings
import threading

from .models import NumeroBonCommande
from .penalty_data import collect_penalty_context
from .penalty_report import generate_penalty_report
from .emails import send_penalty_notification


@csrf_protect
@login_required
def generate_penalty_report_api(request, bon_id: int):
    """Return the Penalty Sheet PDF for the given PO."""
    if request.method not in {"GET", "POST"}:
        return JsonResponse({"success": False, "error": "Méthode non autorisée"}, status=405)

    try:
        bon_commande = NumeroBonCommande.objects.select_related("timeline_delay").get(id=bon_id)
    except NumeroBonCommande.DoesNotExist:
        return JsonResponse({"success": False, "error": "Bon de commande non trouvé"}, status=404)
    context = collect_penalty_context(bon_commande)

    # Optional payload (JSON body or form data)
    observation = ""
    if request.method == "POST":
        if request.content_type and "application/json" in request.content_type.lower():
            try:
                payload = json.loads(request.body.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                payload = {}
        else:
            payload = request.POST
        observation = (payload.get("observation") or "").strip()
    elif request.method == "GET":
        observation = (request.GET.get("observation") or "").strip()

    if observation:
        context["observation"] = observation

    pdf_buffer = generate_penalty_report(
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
                report_type='penalty'
            )
        except Exception as e:
            pass
    
    email_thread = threading.Thread(target=send_email_async, daemon=True)
    email_thread.start()

    filename = iri_to_uri(f"PenaltySheet-{bon_commande.numero}.pdf")
    response = HttpResponse(pdf_buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    response["X-Penalty-Due"] = str(context.get("penalties_due", "0"))
    return response
