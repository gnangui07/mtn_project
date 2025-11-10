import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model
from orders.models import NumeroBonCommande

User = get_user_model()


@pytest.mark.django_db
def test_delay_evaluation_pdf_inline_headers(client):
    user = User.objects.create_user('delay@example.com', 'testpass')
    user.is_active = True
    user.save()
    client.force_login(user)

    bon = NumeroBonCommande.objects.create(numero='PO-DELAY-001')

    url = reverse('orders:generate_delay_evaluation_report_api', args=[bon.id])
    resp = client.get(url)

    assert resp.status_code == 200
    assert resp['Content-Type'] == 'application/pdf'
    assert 'inline' in resp['Content-Disposition']


@pytest.mark.django_db
def test_delay_evaluation_requires_authentication(client):
    bon = NumeroBonCommande.objects.create(numero='PO-DELAY-002')
    url = reverse('orders:generate_delay_evaluation_report_api', args=[bon.id])
    resp = client.get(url, follow=False)
    assert resp.status_code in (302, 401, 403)


@pytest.mark.django_db
def test_delay_evaluation_404_when_bon_not_found(client):
    user = User.objects.create_user('delay2@example.com', 'testpass')
    user.is_active = True
    user.save()
    client.force_login(user)

    url = reverse('orders:generate_delay_evaluation_report_api', args=[999999])
    resp = client.get(url)

    assert resp.status_code == 404
    assert resp['Content-Type'].startswith('application/json')


@pytest.mark.django_db
def test_delay_evaluation_method_not_allowed(client):
    user = User.objects.create_user('delay3@example.com', 'testpass')
    user.is_active = True
    user.save()
    client.force_login(user)

    bon = NumeroBonCommande.objects.create(numero='PO-DELAY-003')
    url = reverse('orders:generate_delay_evaluation_report_api', args=[bon.id])

    resp = client.put(url)
    assert resp.status_code == 405
    assert resp['Content-Type'].startswith('application/json')
