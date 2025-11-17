import pytest
from django.urls import reverse
from unittest.mock import patch


@pytest.mark.django_db
def test_get_analytics_data_success(client):
    url = reverse('orders:get_analytics_data')
    resp = client.get(url)
    assert resp.status_code == 200
    data = resp.json()
    assert data.get('status') == 'success'
    assert 'bons_avec_reception' in data
    assert 'total_bons' in data
    assert 'pie_chart' in data and 'labels' in data['pie_chart'] and 'values' in data['pie_chart']


@pytest.mark.django_db
def test_get_analytics_data_error(client):
    """Force une exception interne pour couvrir la branche d'erreur (500)."""
    url = reverse('orders:get_analytics_data')
    with patch('orders.analytics_api.NumeroBonCommande.objects.count') as mock_count:
        mock_count.side_effect = Exception('db down')
        resp = client.get(url)
    assert resp.status_code == 500
    data = resp.json()
    assert data.get('status') == 'error'
