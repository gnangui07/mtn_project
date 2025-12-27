"""But:
- Exposer un endpoint API pour générer la fiche d'amendement de pénalité d’un bon.

Étapes:
- Vérifier la méthode et récupérer le bon.
- Construire le contexte d'amendement (base + champs saisis: doléance, proposition, statut, nouvelle pénalité).
- Générer le PDF et lancer l'email en arrière-plan.
- Retourner le PDF (inline).

Entrées:
- Requête HTTP (GET/POST), `bon_id` (int), champs facultatifs: `supplier_plea`, `pm_proposal`, `penalty_status`, `new_penalty_due`.

Sorties:
- HttpResponse PDF (Content-Type: application/pdf).
"""
from __future__ import annotations

import json
import threading
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.utils.encoding import iri_to_uri
from django.views.decorators.csrf import csrf_protect
from django.core.files.base import ContentFile

from .models import NumeroBonCommande, PenaltyAmendmentReportLog
from .penalty_amendment_data import collect_penalty_amendment_context
from .penalty_amendment_report import generate_penalty_amendment_report
from .emails import send_penalty_notification

# Import Celery tasks avec fallback
try:
    from .tasks import generate_penalty_amendment_pdf_task
    from .task_status_api import register_user_task
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False


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
    """But:
    - Générer et retourner le PDF d'amendement de pénalité pour un bon donné.

    Étapes:
    - Vérifier la méthode, trouver le bon.
    - Appliquer les champs saisis (texte libre et montants) au contexte.
    - Générer le PDF, envoyer l'email en arrière-plan.

    Entrées:
    - `request` (GET/POST), `bon_id` (int), champs `supplier_plea`, `pm_proposal`, `penalty_status`, `new_penalty_due`.

    Sorties:
    - HttpResponse PDF (inline).
    """
    # 1) Autoriser seulement GET/POST pour éviter des erreurs
    if request.method not in {"GET", "POST"}:
        return JsonResponse({"success": False, "error": "Méthode non autorisée"}, status=405)

    # 2) Récupérer le bon (404 si introuvable)
    try:
        bon_commande = NumeroBonCommande.objects.select_related("timeline_delay").get(id=bon_id)
    except NumeroBonCommande.DoesNotExist:
        return JsonResponse({"success": False, "error": "Bon de commande non trouvé"}, status=404)
    # Base de contexte calculée automatiquement (montants, dates, etc.)
    context = collect_penalty_amendment_context(bon_commande)

    # 3) Lire les champs envoyés par l'utilisateur (JSON ou formulaire)
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

    # 4) Champs libres: doléance du fournisseur et proposition du PM
    supplier_plea = (payload.get("supplier_plea") or "").strip()
    pm_proposal = (payload.get("pm_proposal") or "").strip()
    context["supplier_plea"] = supplier_plea
    context["pm_proposal"] = pm_proposal

    # 5) Statut de la pénalité (trois valeurs autorisées)
    status = (payload.get("penalty_status") or "").strip().lower()
    if status in {"annulee", "reduite", "reconduite"}:
        context["penalty_status"] = status
    else:
        status = ""

    # 6) Nouvelle pénalité demandée (montant optionnel)
    requested_new_penalty = payload.get("new_penalty_due")
    new_penalty_due = None
    if requested_new_penalty not in (None, ""):
        new_penalty_due = _decimal_or_default(requested_new_penalty)
        context["new_penalty_due"] = new_penalty_due

    # Mode Asynchrone (Celery)
    if CELERY_AVAILABLE:
        # Convertir new_penalty_due en str pour sérialisation JSON si nécessaire
        new_penalty_str = str(new_penalty_due) if new_penalty_due is not None else None
        
        task = generate_penalty_amendment_pdf_task.delay(
            bon_id, 
            request.user.id, 
            supplier_plea, 
            pm_proposal, 
            status, 
            new_penalty_str
        )
        
        # Enregistrer la tâche pour le polling utilisateur
        try:
            register_user_task(request.user.id, task.id, 'generate_penalty_amendment')
        except Exception:
            pass
            
        return JsonResponse({
            'success': True,
            'async': True,
            'task_id': task.id,
            'bon_id': bon_id,
            'report_number': bon_commande.numero,
            'message': f"La génération de l'amendement pour {bon_commande.numero} a démarré en arrière-plan."
        })

    # Mode Synchrone (Fallback)
    # 7) Générer le PDF en mémoire
    pdf_buffer = generate_penalty_amendment_report(
        bon_commande,
        context=context,
        user_email=getattr(request.user, "email", None),
    )

    # Sauvegarder le PDF dans le log
    filename = f"PenaltyAmendment-{bon_commande.numero}.pdf" # Fallback
    try:
        pdf_bytes = pdf_buffer.getvalue()
        log_entry = PenaltyAmendmentReportLog.objects.create(bon_commande=bon_commande)
        filename = f"PenaltyAmendment-{bon_commande.numero}-{log_entry.id}.pdf"
        log_entry.file.save(filename, ContentFile(pdf_bytes), save=True)
    except Exception:
        # Ne pas perturber la génération en cas d'erreur de log
        pass

    # 8) Envoyer la notification email en arrière-plan (asynchrone)
    def send_email_async():
        try:
            send_penalty_notification(
                bon_commande=bon_commande,
                pdf_buffer=pdf_buffer,
                user_email=getattr(request.user, "email", None),
                report_type='penalty_amendment',
                filename=filename
            )
        except Exception as e:
            pass
    
    email_thread = threading.Thread(target=send_email_async, daemon=True)
    email_thread.start()

    # 9) Retourner le PDF inline
    safe_filename = iri_to_uri(filename)
    response = HttpResponse(pdf_buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{safe_filename}"'
    return response
