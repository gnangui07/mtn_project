"""But:
- Fournir une API pour générer le PDF d'évaluation des délais de livraison.

Étapes:
- Récupérer le bon de commande.
- Collecter les données d'évaluation (délais, notes, commentaires).
- Générer le PDF.
- Envoyer l'email en arrière-plan.
- Renvoyer le PDF à l'utilisateur.

Entrées:
- bon_id (int): identifiant du bon de commande.
- observation, attachments (optionnels): données additionnelles.

Sorties:
- HttpResponse: PDF inline pour téléchargement.
"""
from __future__ import annotations

import json
import threading

from django.http import HttpResponse, JsonResponse
from django.utils.encoding import iri_to_uri
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required

from .models import NumeroBonCommande
from .delay_evaluation_data import collect_delay_evaluation_context
from .delay_evaluation_report import generate_delay_evaluation_report
from .emails import send_penalty_notification


@csrf_exempt
@login_required
def generate_delay_evaluation_report_api(request, bon_id: int):
    """But:
    - Générer le PDF d'évaluation des délais pour un bon de commande.

    Étapes:
    - Valider la méthode (GET/POST).
    - Récupérer le bon.
    - Collecter le contexte d'évaluation.
    - Lire observation/attachments si fournis.
    - Générer le PDF.
    - Envoyer email en arrière-plan.
    - Renvoyer le PDF.

    Entrées:
    - request: requête Django.
    - bon_id: ID du bon de commande.

    Sorties:
    - HttpResponse avec PDF inline.
    """
    if request.method not in {"GET", "POST"}:
        return JsonResponse({"success": False, "error": "Méthode non autorisée"}, status=405)

    # Récupérer le bon avec les délais timeline
    try:
        bon_commande = NumeroBonCommande.objects.select_related("timeline_delay").get(id=bon_id)
    except Exception:
        return JsonResponse({"success": False, "error": "Bon de commande non trouvé"}, status=404)

    # Collecter toutes les données nécessaires (dates, délais, notes)
    context = collect_delay_evaluation_context(bon_commande)

    # Lire les paramètres optionnels (observation, attachments)
    payload = {}
    if request.method == "POST":
        ct = getattr(request, "content_type", "") or ""
        if isinstance(ct, str) and "application/json" in ct.lower():
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

    # Générer le PDF avec toutes les données
    pdf_buffer = generate_delay_evaluation_report(
        bon_commande,
        context=context,
        user_email=getattr(request.user, "email", None),
    )

    # Envoyer la notification email en arrière-plan (non bloquant)
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
