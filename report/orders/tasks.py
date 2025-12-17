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
def import_fichier_task(self, file_path: str, user_id: int, original_filename: str | None = None):
    """Import async d'un fichier uploadé.

    - Lit le fichier temporaire sur disque (créé par la vue).
    - Réutilise la logique sync `import_or_update_fichier`.
    - Supprime le fichier temporaire.

    Retourne un résumé (id fichier importé, nb lignes, nb bons associés).
    """
    import os
    from django.core.files.base import File
    from django.contrib.auth import get_user_model

    try:
        from .models import import_or_update_fichier
        user = get_user_model().objects.get(pk=user_id)

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Temp file not found: {file_path}")

        filename = original_filename or os.path.basename(file_path)
        with open(file_path, "rb") as f:
            django_file = File(f, name=filename)
            fichier_importe, _created = import_or_update_fichier(django_file, utilisateur=user)

        # Ne supprimer que les fichiers temporaires créés par la vue (MEDIA_ROOT/imports/temp)
        try:
            from django.conf import settings

            temp_root = os.path.abspath(os.path.join(settings.MEDIA_ROOT, "imports", "temp"))
            abs_path = os.path.abspath(file_path)
            if abs_path.startswith(temp_root + os.sep):
                os.remove(abs_path)
        except Exception:
            pass

        return {
            "fichier_id": fichier_importe.id,
            "nombre_lignes": getattr(fichier_importe, "nombre_lignes", 0),
            "bons_count": fichier_importe.bons_commande.count() if hasattr(fichier_importe, "bons_commande") else 0,
        }
    except Exception as exc:
        # un retry léger au cas où la base ou le filesystem est temporairement indisponible
        raise self.retry(exc=exc, countdown=2)
