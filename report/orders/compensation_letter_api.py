"""But:
- Fournir une API pour générer le PDF de la lettre de demande de compensation.

Étapes:
- Récupérer le bon de commande.
- Collecter le contexte pénalités (dates, retards, montants).
- Générer le PDF de la lettre.
- Envoyer un email en arrière-plan.
- Renvoyer le PDF en inline.

Entrées:
- bon_id (int): identifiant du bon de commande.
- Requête GET/POST (peut contenir des champs additionnels si besoin).

Sorties:
- HttpResponse: PDF inline.
"""
from __future__ import annotations

import json
import threading
from django.http import HttpResponse, JsonResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.utils.encoding import iri_to_uri
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.core.files.base import ContentFile

from .models import NumeroBonCommande, CompensationLetterLog
from .penalty_data import collect_penalty_context
from .compensation_letter_report import generate_compensation_letter
from .emails import send_penalty_notification

# Import Celery tasks avec fallback
try:
    from .tasks import generate_compensation_letter_pdf_task
    from .task_status_api import register_user_task
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False


@csrf_exempt
@login_required
def generate_compensation_letter_api(request, bon_id: int):
    """But:
    - Générer le PDF de lettre de demande de compensation pour un bon.

    Étapes:
    - Vérifier la méthode.
    - Charger le bon de commande.
    - Construire le contexte pénalités.
    - Générer le PDF.
    - Déclencher l'email asynchrone.
    - Renvoyer le PDF (inline).

    Entrées:
    - request: objet requête Django (GET/POST).
    - bon_id: identifiant du bon.

    Sorties:
    - HttpResponse (application/pdf).
    """
    if request.method not in {"GET", "POST"}:
        return JsonResponse({"success": False, "error": "Méthode non autorisée"}, status=405)

    # Étape 1: récupération du bon (toute erreur ici doit répondre 404 d'après les tests)
    try:
        bon_commande = get_object_or_404(NumeroBonCommande, id=bon_id)
    except Exception:
        return JsonResponse({"success": False, "error": "Bon de commande non trouvé"}, status=404)

    # Mode Asynchrone (Celery)
    if CELERY_AVAILABLE:
        try:
            task = generate_compensation_letter_pdf_task.delay(bon_id, request.user.id)
            
            # Enregistrer la tâche pour le polling utilisateur
            try:
                register_user_task(request.user.id, task.id, 'generate_compensation_letter')
            except Exception:
                pass
                
            return JsonResponse({
                'success': True,
                'async': True,
                'task_id': task.id,
                'bon_id': bon_id,
                'report_number': bon_commande.numero,
                'message': f"La génération de la lettre de compensation pour {bon_commande.numero} a démarré en arrière-plan."
            })
        except Exception as e:
            # Si erreur au lancement de la tâche, on continue en mode synchrone
            pass

    # Étape 2: génération (les erreurs ici sont des 500)
    try:
        # Créer une entrée de log pour obtenir un identifiant séquentiel global
        log_entry = CompensationLetterLog.objects.create(bon_commande=bon_commande)
        sequence_number = log_entry.id

        # Construire la référence de lettre au format EPMO/ED/LDC/MM-YYYY/NNN
        now = timezone.now()
        letter_reference = f"EPMO/ED/LDC/{now:%m-%Y}/{sequence_number:03d}"

        # Collect penalty context data
        context = collect_penalty_context(bon_commande)
        context["letter_reference"] = letter_reference
        
        # Generate PDF
        pdf_buffer = generate_compensation_letter(
            bon_commande,
            context=context,
            user_email=getattr(request.user, "email", None),
        )

        # Sauvegarder le PDF dans le log
        filename = f"CompensationLetter-{bon_commande.numero}-{sequence_number}.pdf"
        try:
            pdf_bytes = pdf_buffer.getvalue()
            log_entry.file.save(filename, ContentFile(pdf_bytes), save=True)
        except Exception:
            # On évite de casser la génération de la lettre si l'enregistrement du fichier échoue
            pass
        
        # Envoyer la notification email en arrière-plan (asynchrone)
        def send_email_async():
            try:
                send_penalty_notification(
                    bon_commande=bon_commande,
                    pdf_buffer=pdf_buffer,
                    user_email=getattr(request.user, "email", None),
                    report_type='compensation_letter',
                    filename=filename
                )
            except Exception:
                pass
        
        email_thread = threading.Thread(target=send_email_async, daemon=True)
        email_thread.start()
        
        # Prepare response
        response = HttpResponse(pdf_buffer.read(), content_type="application/pdf")
        safe_filename = iri_to_uri(filename)
        response["Content-Disposition"] = f'inline; filename="{safe_filename}"'
        
        return response
    except Exception as e:
        return JsonResponse({
            "success": False,
            "error": f"Erreur lors de la génération de la lettre: {str(e)}"
        }, status=500)
