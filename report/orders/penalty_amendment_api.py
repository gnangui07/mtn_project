"""API endpoint for the penalty amendment sheet."""
from __future__ import annotations

import json
import threading
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.utils.encoding import iri_to_uri
from django.views.decorators.csrf import csrf_protect

from .models import NumeroBonCommande
from .penalty_amendment_data import collect_penalty_amendment_context
from .penalty_amendment_report import generate_penalty_amendment_report
from .emails import send_penalty_notification


def _decimal_or_default(value, default: str = "0") -> Decimal:
    try:
        if isinstance(value, Decimal):
            return value
        if value in (None, ""):
            return Decimal(default)
        return Decimal(str(value).replace(" ", ""))
    except Exception:
        return Decimal(default)


@csrf_protect
@login_required
def generate_penalty_amendment_report_api(request, bon_id: int):
    """Return the penalty amendment sheet for the given PO."""
    if request.method not in {"GET", "POST"}:
        return JsonResponse({"success": False, "error": "Méthode non autorisée"}, status=405)

    try:
        bon_commande = NumeroBonCommande.objects.select_related("timeline_delay").get(id=bon_id)
    except NumeroBonCommande.DoesNotExist:
        return JsonResponse({"success": False, "error": "Bon de commande non trouvé"}, status=404)

    context = collect_penalty_amendment_context(bon_commande)

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

    context["supplier_plea"] = (payload.get("supplier_plea") or "").strip()
    context["pm_proposal"] = (payload.get("pm_proposal") or "").strip()

    status = (payload.get("penalty_status") or "").strip().lower()
    if status in {"annulee", "reduite", "reconduite"}:
        context["penalty_status"] = status

    requested_new_penalty = payload.get("new_penalty_due")
    if requested_new_penalty not in (None, ""):
        context["new_penalty_due"] = _decimal_or_default(requested_new_penalty)

    pdf_buffer = generate_penalty_amendment_report(
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
                report_type='penalty_amendment'
            )
        except Exception as e:
            pass
    
    email_thread = threading.Thread(target=send_email_async, daemon=True)
    email_thread.start()

    filename = iri_to_uri(f"PenaltyAmendment-{bon_commande.numero}.pdf")
    response = HttpResponse(pdf_buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    return response
