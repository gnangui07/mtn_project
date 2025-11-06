import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_generate_penalty_amendment_report_requires_login(client):
    url = reverse('orders:generate_penalty_amendment_report_api', kwargs={'bon_id': 1})
    resp = client.get(url)
    assert resp.status_code in (302, 301)


@pytest.mark.django_db
def test_generate_penalty_amendment_report_404(client, user_active):
    client.force_login(user_active)
    url = reverse('orders:generate_penalty_amendment_report_api', kwargs={'bon_id': 999999})
    resp = client.get(url)
    assert resp.status_code == 404


@pytest.mark.django_db
def test_generate_penalty_amendment_report_happy_path(client, user_active, monkeypatch):
    client.force_login(user_active)

    from orders.models import NumeroBonCommande
    po = NumeroBonCommande.objects.create(numero='PO-PEN-AMD-1')

    # mock email sending
    monkeypatch.setattr('orders.penalty_amendment_api.send_penalty_notification', lambda **kwargs: None)

    url = reverse('orders:generate_penalty_amendment_report_api', kwargs={'bon_id': po.id})
    payload = {
        'supplier_plea': 'Delays due to customs',
        'pm_proposal': 'Reduce by 50%',
        'penalty_status': 'reduite',
        'new_penalty_due': '1234',
    }
    resp = client.get(url, data=payload)
    assert resp.status_code == 200
    assert resp['Content-Type'] == 'application/pdf'
    assert resp['Content-Disposition'].startswith('inline; filename=')
    content = resp.content
    assert isinstance(content, (bytes, bytearray))
    assert content[:4] == b'%PDF'
    assert len(content) > 1024
