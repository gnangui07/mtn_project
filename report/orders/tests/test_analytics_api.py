import pytest
from django.urls import reverse


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
