from __future__ import annotations

import logging

from celery import shared_task
from django.core.cache import cache
from django.test import RequestFactory

import base64

logger = logging.getLogger(__name__)


@shared_task
def invalidate_bon_cache(bon_id: int):
    """Invalide les caches liés à un bon de commande."""
    try:
        cache.delete(f"bon_details_{bon_id}")
        cache.delete(f"bon_receptions_{bon_id}")
        cache.delete(f"bon_lignes_{bon_id}")
        logger.debug("Invalidated cache for bon %s", bon_id)
    except Exception as exc:
        logger.warning("Failed to invalidate bon cache (%s): %s", bon_id, exc)


@shared_task
def invalidate_service_cache(service: str):
    """Invalide les caches liés à un service (liste de bons par service)."""
    try:
        if service:
            cache.delete(f"bons_service_{service}")
            logger.debug("Invalidated service cache for %s", service)
    except Exception as exc:
        logger.warning("Failed to invalidate service cache (%s): %s", service, exc)


def _make_export_payload(response, default_filename: str):
    filename = default_filename
    try:
        cd = response.get("Content-Disposition")
        if cd and "filename=" in cd:
            filename = cd.split("filename=", 1)[1].strip().strip('"')
    except Exception:
        pass

    content = response.content
    content_type = response.get("Content-Type", "application/octet-stream")

    return {
        "filename": filename,
        "content_type": content_type,
        "content_base64": base64.b64encode(content).decode("ascii"),
    }


@shared_task
def export_po_progress_task(user_id: int, user_service: str | None = None):
    """Export async du PO progress monitoring.

    Retourne un dict contenant le fichier encodé en base64.
    """
    from django.contrib.auth import get_user_model
    from .views_export import export_po_progress_monitoring

    rf = RequestFactory()
    request = rf.get("/orders/export-po-progress-monitoring/")
    request.user = get_user_model().objects.get(pk=user_id)

    response = export_po_progress_monitoring(request)
    return _make_export_payload(response, default_filename="po_progress_monitoring.xlsx")


@shared_task
def export_vendor_evaluations_task(user_id: int, **filters):
    """Export async des vendor evaluations.

    filters peut contenir: supplier, min_score, date_from, date_to.
    """
    from django.contrib.auth import get_user_model
    from .views_export import export_vendor_evaluations

    rf = RequestFactory()
    request = rf.get("/orders/export-vendor-evaluations/", data=filters)
    request.user = get_user_model().objects.get(pk=user_id)

    response = export_vendor_evaluations(request)
    return _make_export_payload(response, default_filename="vendor_evaluations.xlsx")


@shared_task
def export_bon_excel_task(user_id: int, bon_id: int, selected_order_number: str | None = None):
    """Export async d'un bon (Excel)."""
    from django.contrib.auth import get_user_model
    from .views_export import export_bon_excel

    rf = RequestFactory()
    params = {}
    if selected_order_number:
        params["selected_order_number"] = selected_order_number

    request = rf.get(f"/orders/export-excel/{bon_id}/", data=params)
    request.user = get_user_model().objects.get(pk=user_id)

    response = export_bon_excel(request, bon_id=bon_id)
    return _make_export_payload(response, default_filename=f"bon_{bon_id}.xlsx")


@shared_task(bind=True, max_retries=1)
def import_fichier_task(self, file_path: str, user_id: int, original_filename: str | None = None, fichier_id: int | None = None):
    """Import async d'un fichier uploadé (Version optimisée pour gros fichiers).
    
    - Lit le fichier par chunks (Pandas/Openpyxl)
    - Utilise bulk_create/bulk_update
    - Gère les réceptions et les POs
    """
    import os
    from django.core.files.base import File
    from django.contrib.auth import get_user_model
    from .models import FichierImporte
    from .import_utils import import_file_optimized
    
    try:
        user = get_user_model().objects.get(pk=user_id)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        if fichier_id:
            # Cas Admin : Le fichier est déjà créé en base
            fichier_importe = FichierImporte.objects.get(pk=fichier_id)
        else:
            # Cas Upload Async (Frontend) : Créer depuis fichier temporaire
            filename = original_filename or os.path.basename(file_path)
            
            # 1. Créer FichierImporte sans déclencher l'extraction auto
            with open(file_path, "rb") as f:
                django_file = File(f, name=filename)
                fichier_importe = FichierImporte(fichier=django_file, utilisateur=user)
                fichier_importe._skip_extraction = True
                fichier_importe.save()
                
            # Déterminer extension
            ext = os.path.splitext(filename)[1].lower().lstrip('.')
            fichier_importe.extension = ext
            fichier_importe.save(update_fields=['extension'])

        # Appel de la logique partagée
        total_rows, po_count = import_file_optimized(fichier_importe, file_path)

        # Cleanup temp file (seulement si c'est un fichier temporaire)
        try:
            from django.conf import settings
            temp_root = os.path.abspath(os.path.join(settings.MEDIA_ROOT, "imports", "temp"))
            abs_path = os.path.abspath(file_path)
            # On ne supprime que si le fichier est dans le dossier temporaire
            if abs_path.startswith(temp_root + os.sep):
                os.remove(abs_path)
        except Exception:
            pass

        return {
            "fichier_id": fichier_importe.id,
            "nombre_lignes": total_rows,
            "bons_count": po_count
        }
        
    except Exception as exc:
        raise self.retry(exc=exc, countdown=2)


@shared_task
def generate_msrn_pdf_task(report_id: int, user_id: int, send_email: bool = True):
    """Génère le PDF MSRN de manière asynchrone."""
    from django.contrib.auth import get_user_model
    from django.core.files.base import ContentFile
    from .models import MSRNReport
    from .reports import generate_msrn_report
    from .emails import send_msrn_notification
    import time

    logger.info(f"Début de la tâche generate_msrn_pdf_task pour report_id={report_id} (email={send_email})")
    start_time = time.time()

    try:
        user = get_user_model().objects.get(pk=user_id)
        report = MSRNReport.objects.get(pk=report_id)
        bon_commande = report.bon_commande

        # Générer le PDF
        pdf_buffer = generate_msrn_report(bon_commande, report.report_number, user_email=user.email)
        
        # Sauvegarder le PDF
        filename = f"{report.report_number}-{bon_commande.numero}.pdf"
        report.pdf_file.save(filename, ContentFile(pdf_buffer.getvalue()), save=True)
        
        logger.info(f"PDF MSRN généré en {time.time() - start_time:.2f}s")

        # Envoyer la notification email
        if send_email:
            try:
                send_msrn_notification(report)
                logger.info(f"Notification email envoyée pour {report.report_number}")
            except Exception as e:
                logger.error(f"Erreur envoi email MSRN: {e}")

        return {
            "report_id": report.id,
            "report_number": report.report_number,
            "filename": filename
        }

    except Exception as exc:
        logger.exception(f"Erreur tâche generate_msrn_pdf_task: {exc}")
        raise exc


@shared_task
def generate_penalty_pdf_task(bon_id: int, user_id: int, observation: str = "", send_email: bool = True):
    """Génère le PDF de la fiche de pénalité de manière asynchrone."""
    from django.contrib.auth import get_user_model
    from django.core.files.base import ContentFile
    from django.utils.encoding import iri_to_uri
    from .models import NumeroBonCommande, PenaltyReportLog
    from .penalty_data import collect_penalty_context
    from .penalty_report import generate_penalty_report
    from .emails import send_penalty_notification
    import time

    logger.info(f"Début de la tâche generate_penalty_pdf_task pour bon_id={bon_id}")
    start_time = time.time()

    try:
        user = get_user_model().objects.get(pk=user_id)
        bon_commande = NumeroBonCommande.objects.select_related("timeline_delay").get(id=bon_id)
        
        context = collect_penalty_context(bon_commande)
        if observation:
            context["observation"] = observation

        # Générer le PDF
        pdf_buffer = generate_penalty_report(
            bon_commande,
            context=context,
            user_email=user.email,
        )

        # Sauvegarder le PDF dans le log
        log_entry = PenaltyReportLog.objects.create(bon_commande=bon_commande)
        filename = f"PenaltySheet-{bon_commande.numero}-{log_entry.id}.pdf"
        pdf_bytes = pdf_buffer.getvalue()
        log_entry.file.save(filename, ContentFile(pdf_bytes), save=True)

        logger.info(f"PDF Penalty généré en {time.time() - start_time:.2f}s")

        # Envoyer la notification email
        if send_email:
            try:
                send_penalty_notification(
                    bon_commande=bon_commande,
                    pdf_buffer=pdf_buffer,
                    user_email=user.email,
                    report_type='penalty',
                    filename=filename
                )
            except Exception as e:
                logger.error(f"Erreur envoi email Penalty: {e}")

        # Encodage base64 pour le retour (car le fichier n'est pas accessible via URL publique comme MSRN)
        # Mais pour être cohérent avec l'approche "download link" ou "direct download",
        # ici on va retourner l'ID du log pour permettre un téléchargement via une vue dédiée si besoin,
        # ou le contenu en base64 si on veut l'afficher directement.
        # Pour simplifier, on renvoie le nom de fichier et on suppose que le frontend gère.
        # Note: Contrairement au MSRN, ces PDFs sont souvent générés à la volée.
        # Ici on les a stockés dans PenaltyReportLog.
        
        return {
            "bon_id": bon_id,
            "filename": filename,
            "log_id": log_entry.id,
            "download_url": log_entry.file.url if log_entry.file else None
        }

    except Exception as exc:
        logger.exception(f"Erreur tâche generate_penalty_pdf_task: {exc}")
        raise exc


@shared_task
def generate_delay_evaluation_pdf_task(bon_id: int, user_id: int, observation: str = "", attachments: str = "", send_email: bool = True):
    """Génère le PDF d'évaluation des délais de manière asynchrone."""
    from django.contrib.auth import get_user_model
    from django.core.files.base import ContentFile
    from .models import NumeroBonCommande, DelayEvaluationReportLog
    from .delay_evaluation_data import collect_delay_evaluation_context
    from .delay_evaluation_report import generate_delay_evaluation_report
    from .emails import send_penalty_notification
    import time

    logger.info(f"Début de la tâche generate_delay_evaluation_pdf_task pour bon_id={bon_id}")
    start_time = time.time()

    try:
        user = get_user_model().objects.get(pk=user_id)
        bon_commande = NumeroBonCommande.objects.select_related("timeline_delay").get(id=bon_id)
        
        context = collect_delay_evaluation_context(bon_commande)
        if observation:
            context["observation"] = observation
        if attachments:
            context["attachments"] = attachments

        # Générer le PDF
        pdf_buffer = generate_delay_evaluation_report(
            bon_commande,
            context=context,
            user_email=user.email,
        )

        # Sauvegarder le PDF dans le log
        log_entry = DelayEvaluationReportLog.objects.create(bon_commande=bon_commande)
        filename = f"DelayEvaluation-{bon_commande.numero}-{log_entry.id}.pdf"
        pdf_bytes = pdf_buffer.getvalue()
        log_entry.file.save(filename, ContentFile(pdf_bytes), save=True)

        logger.info(f"PDF Delay Evaluation généré en {time.time() - start_time:.2f}s")

        # Envoyer la notification email
        if send_email:
            try:
                send_penalty_notification(
                    bon_commande=bon_commande,
                    pdf_buffer=pdf_buffer,
                    user_email=user.email,
                    report_type='delay_evaluation'
                )
            except Exception as e:
                logger.error(f"Erreur envoi email Delay Evaluation: {e}")

        return {
            "bon_id": bon_id,
            "filename": f"DelayEvaluation-{bon_commande.numero}.pdf",
            "log_id": log_entry.id,
            "download_url": log_entry.file.url if log_entry.file else None
        }

    except Exception as exc:
        logger.exception(f"Erreur tâche generate_delay_evaluation_pdf_task: {exc}")
        raise exc


@shared_task
def generate_compensation_letter_pdf_task(bon_id: int, user_id: int, send_email: bool = True):
    """Génère le PDF de la lettre de compensation de manière asynchrone."""
    from django.contrib.auth import get_user_model
    from django.core.files.base import ContentFile
    from django.utils import timezone
    from .models import NumeroBonCommande, CompensationLetterLog
    from .penalty_data import collect_penalty_context
    from .compensation_letter_report import generate_compensation_letter
    from .emails import send_penalty_notification
    import time

    logger.info(f"Début de la tâche generate_compensation_letter_pdf_task pour bon_id={bon_id}")
    start_time = time.time()

    try:
        user = get_user_model().objects.get(pk=user_id)
        bon_commande = NumeroBonCommande.objects.get(id=bon_id)
        
        # Créer une entrée de log pour obtenir un identifiant séquentiel global
        log_entry = CompensationLetterLog.objects.create(bon_commande=bon_commande)
        sequence_number = log_entry.id

        # Construire la référence de lettre
        now = timezone.now()
        letter_reference = f"EPMO/ED/LDC/{now:%m-%Y}/{sequence_number:03d}"

        # Collect penalty context data
        context = collect_penalty_context(bon_commande)
        context["letter_reference"] = letter_reference
        
        # Generate PDF
        pdf_buffer = generate_compensation_letter(
            bon_commande,
            context=context,
            user_email=user.email,
        )

        # Sauvegarder le PDF dans le log
        filename = f"CompensationLetter-{bon_commande.numero}-{sequence_number}.pdf"
        pdf_bytes = pdf_buffer.getvalue()
        log_entry.file.save(filename, ContentFile(pdf_bytes), save=True)

        logger.info(f"PDF Compensation Letter généré en {time.time() - start_time:.2f}s")

        # Envoyer la notification email
        if send_email:
            try:
                send_penalty_notification(
                    bon_commande=bon_commande,
                    pdf_buffer=pdf_buffer,
                    user_email=user.email,
                    report_type='compensation_letter',
                    filename=filename
                )
            except Exception as e:
                logger.error(f"Erreur envoi email Compensation Letter: {e}")

        return {
            "bon_id": bon_id,
            "filename": filename,
            "log_id": log_entry.id,
            "download_url": log_entry.file.url if log_entry.file else None
        }

    except Exception as exc:
        logger.exception(f"Erreur tâche generate_compensation_letter_pdf_task: {exc}")
        raise exc


@shared_task
def generate_penalty_amendment_pdf_task(bon_id: int, user_id: int, supplier_plea: str = "", pm_proposal: str = "", penalty_status: str = "", new_penalty_due: str = None, send_email: bool = True):
    """Génère le PDF de l'amendement de pénalité de manière asynchrone."""
    from django.contrib.auth import get_user_model
    from django.core.files.base import ContentFile
    from decimal import Decimal
    from .models import NumeroBonCommande, PenaltyAmendmentReportLog
    from .penalty_amendment_data import collect_penalty_amendment_context
    from .penalty_amendment_report import generate_penalty_amendment_report
    from .emails import send_penalty_notification
    import time

    logger.info(f"Début de la tâche generate_penalty_amendment_pdf_task pour bon_id={bon_id}")
    start_time = time.time()

    def _decimal_or_default(value, default: str = "0") -> Decimal:
        try:
            if isinstance(value, Decimal):
                return value
            if value in (None, ""):
                return Decimal(default)
            return Decimal(str(value).replace(" ", ""))
        except Exception:
            return Decimal(default)

    try:
        user = get_user_model().objects.get(pk=user_id)
        bon_commande = NumeroBonCommande.objects.select_related("timeline_delay").get(id=bon_id)
        
        context = collect_penalty_amendment_context(bon_commande)
        
        # Champs libres
        context["supplier_plea"] = supplier_plea
        context["pm_proposal"] = pm_proposal

        # Statut
        if penalty_status in {"annulee", "reduite", "reconduite"}:
            context["penalty_status"] = penalty_status

        # Nouvelle pénalité
        if new_penalty_due not in (None, ""):
            context["new_penalty_due"] = _decimal_or_default(new_penalty_due)

        # Générer le PDF
        pdf_buffer = generate_penalty_amendment_report(
            bon_commande,
            context=context,
            user_email=user.email,
        )

        # Sauvegarder le PDF dans le log
        log_entry = PenaltyAmendmentReportLog.objects.create(bon_commande=bon_commande)
        filename = f"PenaltyAmendment-{bon_commande.numero}-{log_entry.id}.pdf"
        pdf_bytes = pdf_buffer.getvalue()
        log_entry.file.save(filename, ContentFile(pdf_bytes), save=True)

        logger.info(f"PDF Penalty Amendment généré en {time.time() - start_time:.2f}s")

        # Envoyer la notification email
        if send_email:
            try:
                send_penalty_notification(
                    bon_commande=bon_commande,
                    pdf_buffer=pdf_buffer,
                    user_email=user.email,
                    report_type='penalty_amendment'
                )
            except Exception as e:
                logger.error(f"Erreur envoi email Penalty Amendment: {e}")

        return {
            "bon_id": bon_id,
            "filename": f"PenaltyAmendment-{bon_commande.numero}.pdf",
            "log_id": log_entry.id,
            "download_url": log_entry.file.url if log_entry.file else None
        }

    except Exception as exc:
        logger.exception(f"Erreur tâche generate_penalty_amendment_pdf_task: {exc}")
        raise exc
