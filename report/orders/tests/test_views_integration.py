import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model
from orders.models import NumeroBonCommande, FichierImporte, MSRNReport
from decimal import Decimal

User = get_user_model()


@pytest.mark.django_db
def test_accueil_view_requires_login_and_shows_bons(client):
    """Test que la page d'accueil nécessite login et affiche les bons"""
    user = User.objects.create_user('view@example.com', 'testpass')
    user.is_active = True
    user.is_superuser = True
    user.save()
    
    # Créer des bons
    bon1 = NumeroBonCommande.objects.create(numero='PO-VIEW-001')
    bon2 = NumeroBonCommande.objects.create(numero='PO-VIEW-002')
    
    # Sans login: redirection
    url = reverse('orders:accueil')
    resp = client.get(url, follow=False)
    assert resp.status_code in (302, 401, 403)
    
    # Avec login: 200 + contexte
    client.force_login(user)
    resp = client.get(url)
    assert resp.status_code == 200
    assert 'numeros_bons' in resp.context
    assert resp.context['numeros_bons'].count() >= 2


@pytest.mark.django_db
def test_consultation_view_accessible(client):
    """Test que la page de consultation est accessible"""
    user = User.objects.create_user('consult@example.com', 'testpass')
    user.is_active = True
    user.save()
    client.force_login(user)
    
    url = reverse('orders:consultation')
    resp = client.get(url)
    assert resp.status_code == 200
    assert b'consultation' in resp.content.lower()


@pytest.mark.django_db
def test_msrn_archive_view_shows_reports(client, settings, tmp_path):
    """Test que l'archive MSRN affiche les rapports"""
    settings.MEDIA_ROOT = tmp_path
    
    user = User.objects.create_user('archive@example.com', 'testpass')
    user.is_active = True
    user.is_superuser = True
    user.save()
    client.force_login(user)
    
    # Créer un rapport MSRN
    bon = NumeroBonCommande.objects.create(numero='PO-ARCH-001')
    msrn = MSRNReport.objects.create(
        report_number='MSRN250001',
        bon_commande=bon,
        user=user.email,
        retention_rate=Decimal('0')
    )
    
    url = reverse('orders:msrn_archive')
    resp = client.get(url)
    assert resp.status_code == 200
    assert 'reports' in resp.context
    assert resp.context['reports'].paginator.count >= 1


@pytest.mark.django_db
def test_msrn_archive_search_by_number(client, settings, tmp_path):
    """Test la recherche dans l'archive MSRN"""
    settings.MEDIA_ROOT = tmp_path
    
    user = User.objects.create_user('search@example.com', 'testpass')
    user.is_active = True
    user.is_superuser = True
    user.save()
    client.force_login(user)
    
    bon = NumeroBonCommande.objects.create(numero='PO-SEARCH-001')
    msrn = MSRNReport.objects.create(
        report_number='MSRN250099',
        bon_commande=bon,
        user=user.email
    )
    
    url = reverse('orders:msrn_archive')
    resp = client.get(url, {'q': 'MSRN250099'})
    assert resp.status_code == 200
    assert resp.context['reports'].paginator.count == 1


@pytest.mark.django_db
def test_details_bon_view_shows_file_data(client):
    """Test que la vue détails affiche les données du fichier"""
    user = User.objects.create_user('details@example.com', 'testpass')
    user.is_active = True
    user.save()
    client.force_login(user)
    
    fichier = FichierImporte.objects.create(fichier='detail.csv', utilisateur=user)
    bon = NumeroBonCommande.objects.create(numero='PO-DET-001')
    bon.fichiers.add(fichier)
    
    url = reverse('orders:details_bon', args=[fichier.id])
    resp = client.get(url)
    assert resp.status_code == 200
    assert 'raw_data' in resp.context or 'headers' in resp.context


@pytest.mark.django_db
def test_search_bon_autocomplete_returns_json(client):
    """Test que l'autocomplétion de recherche retourne du JSON"""
    user = User.objects.create_user('auto@example.com', 'testpass')
    user.is_active = True
    user.is_superuser = True
    user.save()
    client.force_login(user)
    
    bon = NumeroBonCommande.objects.create(numero='PO-AUTO-001')
    
    url = reverse('orders:search_bon')
    resp = client.get(url, {'q': 'PO-AUTO', 'limit': '10'})
    assert resp.status_code == 200
    data = resp.json()
    assert data['status'] == 'success'
    assert 'data' in data


@pytest.mark.django_db
def test_po_progress_monitoring_view_accessible(client):
    """Test que la vue de suivi des PO est accessible"""
    user = User.objects.create_user('progress@example.com', 'testpass')
    user.is_active = True
    user.save()
    client.force_login(user)
    
    url = reverse('orders:po_progress_monitoring')
    resp = client.get(url)
    assert resp.status_code == 200
    assert b'progress' in resp.content.lower() or b'suivi' in resp.content.lower()
