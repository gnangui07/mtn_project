"""But:
- Exposer des endpoints API pour générer la fiche de pénalité (PDF) d’un bon.

Étapes:
- Valider la requête et récupérer le bon.
- Construire le contexte de pénalité.
- Générer le PDF puis lancer l’envoi d’email en arrière-plan.
- Retourner le PDF en réponse (inline).

Entrées:
- Requête HTTP (GET/POST), `bon_id` (int), option `observation`.

Sorties:
- HttpResponse PDF (Content-Type: application/pdf) avec en-tête `X-Penalty-Due`.
"""
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
    """But:
    - Générer et retourner le PDF de pénalité pour un bon donné.

    Étapes:
    - Vérifier la méthode et l’existence du bon.
    - Construire le contexte et appliquer l’`observation` éventuelle.
    - Générer le PDF et déclencher l’email asynchrone.

    Entrées:
    - `request` (GET/POST), `bon_id` (int), champ `observation` facultatif.

    Sorties:
    - HttpResponse PDF (inline) avec header `X-Penalty-Due`.
    """
    # Vérifier que la requête est bien GET ou POST
    # (autres méthodes refusées pour éviter des erreurs)
    if request.method not in {"GET", "POST"}:
        return JsonResponse({"success": False, "error": "Méthode non autorisée"}, status=405)

    # Récupérer le bon de commande en base
    # (si introuvable: on renvoie 404 au lieu de crasher)
    try:
        bon_commande = NumeroBonCommande.objects.select_related("timeline_delay").get(id=bon_id)
    except NumeroBonCommande.DoesNotExist:
        return JsonResponse({"success": False, "error": "Bon de commande non trouvé"}, status=404)
    context = collect_penalty_context(bon_commande)

    # Optional payload (JSON body or form data)
    observation = ""
    # Chercher une "observation" envoyée par l'utilisateur
    # (texte libre ajouté dans le PDF)
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

    # Générer le PDF de la fiche de pénalité en mémoire (pas de fichier sur disque)
    pdf_buffer = generate_penalty_report(
        bon_commande,
        context=context,
        user_email=getattr(request.user, "email", None),
    )

    # Envoyer la notification email en arrière-plan (asynchrone)
    # (cela n'attend pas: l'utilisateur reçoit le PDF immédiatement)
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

    # Préparer la réponse HTTP avec le PDF affiché dans le navigateur (inline)
    filename = iri_to_uri(f"PenaltySheet-{bon_commande.numero}.pdf")
    response = HttpResponse(pdf_buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    # Indiquer le montant calculé dans un en-tête pour usage côté front
    response["X-Penalty-Due"] = str(context.get("penalties_due", "0"))
    return response
