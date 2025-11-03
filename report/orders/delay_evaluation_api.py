"""API endpoints related to delay evaluation report generation."""
from __future__ import annotations

import json
import threading

from django.http import HttpResponse, JsonResponse
from django.utils.encoding import iri_to_uri
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth.decorators import login_required

from .models import NumeroBonCommande
from .delay_evaluation_data import collect_delay_evaluation_context
from .delay_evaluation_report import generate_delay_evaluation_report
from .emails import send_penalty_notification


@csrf_protect
@login_required
def generate_delay_evaluation_report_api(request, bon_id: int):
    """Return the Delivery Delay Evaluation PDF for the given PO."""
    if request.method not in {"GET", "POST"}:
        return JsonResponse({"success": False, "error": "Méthode non autorisée"}, status=405)

    try:
        bon_commande = NumeroBonCommande.objects.select_related("timeline_delay").get(id=bon_id)
    except NumeroBonCommande.DoesNotExist:
        return JsonResponse({"success": False, "error": "Bon de commande non trouvé"}, status=404)

    context = collect_delay_evaluation_context(bon_commande)

    payload = {}
    if request.method == "POST":
        if request.content_type and "application/json" in request.content_type.lower():
            try:
                payload = json.loads(request.body.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                payload = {}
        else:
            payload = request.POST
    elif request.method == "GET":
        payload = request.GET

    observation = (payload.get("observation") or "").strip()
    attachments = (payload.get("attachments") or "").strip()

    if observation:
        context["observation"] = observation
    if attachments:
        context["attachments"] = attachments

    pdf_buffer = generate_delay_evaluation_report(
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
                report_type='delay_evaluation'
            )
        except Exception as e:
            pass
    
    email_thread = threading.Thread(target=send_email_async, daemon=True)
    email_thread.start()

    filename = iri_to_uri(f"DelayEvaluation-{bon_commande.numero}.pdf")
    response = HttpResponse(pdf_buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    return response
