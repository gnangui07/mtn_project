import pytest
import json
from django.urls import reverse
from django.contrib.auth import get_user_model
from orders.models import NumeroBonCommande

User = get_user_model()


@pytest.mark.django_db
def test_msrn_generate_success_minimal_post(client, settings, tmp_path):
    # Éviter d'écrire dans le vrai disque pour le FileField
    settings.MEDIA_ROOT = tmp_path

    user = User.objects.create_user('msrn@example.com', 'testpass')
    user.is_active = True
    user.save()
    client.force_login(user)

    bon = NumeroBonCommande.objects.create(numero='PO-MSRN-001')

    url = reverse('orders:generate_msrn_report_api', args=[bon.id])
    payload = {
        'retention_rate': 0
    }
    resp = client.post(url, data=json.dumps(payload), content_type='application/json')

    assert resp.status_code == 200
    data = resp.json()
    assert data['success'] is True
    assert 'download_url' in data
    assert 'msrn-report' in data.get('download_url', '').lower()


@pytest.mark.django_db
def test_msrn_generate_404_when_bon_not_found(client, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path

    user = User.objects.create_user('msrn2@example.com', 'testpass')
    user.is_active = True
    user.save()
    client.force_login(user)

    url = reverse('orders:generate_msrn_report_api', args=[999999])
    resp = client.post(url, data=json.dumps({'retention_rate': 0}), content_type='application/json')

    assert resp.status_code == 404
    data = resp.json()
    assert data['success'] is False


@pytest.mark.django_db
def test_msrn_generate_invalid_retention_rate_returns_400(client, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path

    user = User.objects.create_user('msrn3@example.com', 'testpass')
    user.is_active = True
    user.save()
    client.force_login(user)

    bon = NumeroBonCommande.objects.create(numero='PO-MSRN-003')

    url = reverse('orders:generate_msrn_report_api', args=[bon.id])
    resp = client.post(url, data=json.dumps({'retention_rate': 11}), content_type='application/json')

    assert resp.status_code == 400
    data = resp.json()
    assert data['success'] is False
    assert 'rétention' in data.get('error', '').lower()


@pytest.mark.django_db
def test_msrn_generate_missing_cause_when_rate_positive_returns_400(client, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path

    user = User.objects.create_user('msrn4@example.com', 'testpass')
    user.is_active = True
    user.save()
    client.force_login(user)

    bon = NumeroBonCommande.objects.create(numero='PO-MSRN-004')

    url = reverse('orders:generate_msrn_report_api', args=[bon.id])
    resp = client.post(url, data=json.dumps({'retention_rate': 5}), content_type='application/json')

    assert resp.status_code == 400
    data = resp.json()
    assert data['success'] is False


@pytest.mark.django_db
def test_msrn_generate_method_not_allowed_on_get(client):
    user = User.objects.create_user('msrn5@example.com', 'testpass')
    user.is_active = True
    user.save()
    client.force_login(user)

    bon = NumeroBonCommande.objects.create(numero='PO-MSRN-005')

    url = reverse('orders:generate_msrn_report_api', args=[bon.id])
    resp = client.get(url)

    assert resp.status_code == 405
    assert resp['Content-Type'].startswith('application/json')
