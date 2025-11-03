"""
Tests simples pour views_export (toutes les vues déclarées):
- Les routes d'export demandent la connexion (redirigent sinon).
- Les names d'URL se résolvent.
"""
import pytest
from django.urls import reverse


@pytest.mark.parametrize(
    "name,kwargs",
    [
        ("orders:export_bon_excel", {"bon_id": 1}),
        ("orders:export_fichier_complet", {"fichier_id": 1}),
        ("orders:export_po_progress_monitoring", {}),
        ("orders:export_msrn_po_lines", {"msrn_id": 1}),
        ("orders:export_msrn_po_lines", {"msrn_id": 9999}),
        ("orders:export_vendor_evaluations", {}),
        ("orders:export_vendor_ranking", {}),
    ],
)
@pytest.mark.django_db
def test_views_export_require_login(client, name, kwargs):
    url = reverse(name, kwargs=kwargs)
    resp = client.get(url)
    assert resp.status_code in (301, 302)
