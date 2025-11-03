"""
Tests de résolution d'URLs (ultra simples) pour l'app orders.
But: chaque nom défini dans orders/urls.py doit se résoudre sans erreur.
"""
import pytest
from django.urls import reverse


@pytest.mark.parametrize(
    "name,kwargs",
    [
        ("orders:accueil", {}),
        ("orders:reception", {}),
        ("orders:details_bon", {"bon_id": 1}),
        ("orders:search_bon", {}),
        ("orders:consultation", {}),
        ("orders:import_fichier", {}),
        ("orders:po_progress_monitoring", {}),
        ("orders:telecharger_fichier", {"fichier_id": 1}),
        ("orders:telecharger_fichier_format", {"fichier_id": 1, "format_export": "xlsx"}),
        ("orders:export_bon_excel", {"bon_id": 1}),
        ("orders:export_fichier_complet", {"fichier_id": 1}),
        ("orders:export_po_progress_monitoring", {}),
        ("orders:get_reception_history", {"fichier_id": 1}),
        ("orders:bulk_correction_quantity_delivered", {"fichier_id": 1}),
        ("orders:get_activity_logs", {}),
        ("orders:get_all_bons", {}),
        ("orders:download_msrn_report", {"report_id": 1}),
        ("orders:msrn_archive", {}),
        ("orders:export_msrn_po_lines", {"msrn_id": 1}),
        ("orders:generate_msrn_report_api", {"bon_id": 1}),
        ("orders:update_msrn_retention", {"msrn_id": 1}),
        ("orders:generate_penalty_report_api", {"bon_id": 1}),
        ("orders:generate_penalty_amendment_report_api", {"bon_id": 1}),
        ("orders:get_penalty_amount_api", {"bon_id": 1}),
        ("orders:generate_delay_evaluation_report_api", {"bon_id": 1}),
        ("orders:generate_compensation_letter_api", {"bon_id": 1}),
        ("orders:vendor_evaluation", {"bon_commande_id": 1}),
        ("orders:vendor_evaluation_list", {}),
        ("orders:vendor_evaluation_detail", {"evaluation_id": 1}),
        ("orders:export_vendor_evaluations", {}),
        ("orders:vendor_ranking", {}),
        ("orders:export_vendor_ranking", {}),
        ("orders:timeline_delays", {"bon_commande_id": 1}),
        ("orders:update_delays", {"timeline_id": 1}),
    ],
)
@pytest.mark.django_db
def test_url_names_resolve(name, kwargs):
    url = reverse(name, kwargs=kwargs)
    assert isinstance(url, str) and len(url) > 0
