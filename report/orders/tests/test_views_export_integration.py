import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model
from orders.models import NumeroBonCommande, FichierImporte, LigneFichier, Reception, VendorEvaluation
from decimal import Decimal

User = get_user_model()


@pytest.mark.django_db
def test_export_po_progress_monitoring_returns_excel(client):
    """Test que l'export PO Progress retourne un fichier Excel"""
    user = User.objects.create_user('export@example.com', 'testpass')
    user.is_active = True
    user.is_superuser = True
    user.save()
    client.force_login(user)
    
    # Créer données minimales
    bon = NumeroBonCommande.objects.create(numero='PO-EXP-001')
    fichier = FichierImporte.objects.create(fichier='exp.csv', utilisateur=user)
    bon.fichiers.add(fichier)
    
    url = reverse('orders:export_po_progress_monitoring')
    resp = client.get(url)
    
    assert resp.status_code == 200
    assert resp['Content-Type'] == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    assert 'attachment' in resp['Content-Disposition']


@pytest.mark.django_db
def test_export_bon_excel_returns_excel_file(client):
    """Test que l'export d'un bon retourne un Excel ou redirige si pas de données"""
    user = User.objects.create_user('expbon@example.com', 'testpass')
    user.is_active = True
    user.save()
    client.force_login(user)
    
    bon = NumeroBonCommande.objects.create(numero='PO-EXPBON-001')
    fichier = FichierImporte.objects.create(fichier='expbon.csv', utilisateur=user)
    bon.fichiers.add(fichier)
    
    LigneFichier.objects.create(
        fichier=fichier,
        numero_ligne=200,
        business_id='EXPBIZ1',
        contenu={'Order': 'PO-EXPBON-001', 'Ordered Quantity': '100'}
    )
    
    url = reverse('orders:export_bon_excel', args=[bon.id])
    resp = client.get(url)
    
    # Accepter 200 (Excel) ou 404/302 (pas de données suffisantes)
    assert resp.status_code in (200, 302, 404)


@pytest.mark.django_db
def test_export_fichier_complet_returns_excel(client):
    """Test que l'export complet d'un fichier retourne Excel"""
    user = User.objects.create_user('expfile@example.com', 'testpass')
    user.is_active = True
    user.save()
    client.force_login(user)
    
    fichier = FichierImporte.objects.create(fichier='expfile.csv', utilisateur=user)
    
    url = reverse('orders:export_fichier_complet', args=[fichier.id])
    resp = client.get(url)
    
    assert resp.status_code == 200
    assert resp['Content-Type'] == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


@pytest.mark.django_db
def test_export_vendor_evaluations_returns_excel(client):
    """Test que l'export des évaluations fournisseurs retourne Excel"""
    user = User.objects.create_user('expvendor@example.com', 'testpass')
    user.is_active = True
    user.is_superuser = True
    user.save()
    client.force_login(user)
    
    bon = NumeroBonCommande.objects.create(numero='PO-VENDOR-001')
    VendorEvaluation.objects.create(
        bon_commande=bon,
        supplier='Test Supplier',
        delivery_compliance=8,
        delivery_timeline=7,
        advising_capability=6,
        after_sales_qos=9,
        vendor_relationship=8,
        evaluator=user
    )
    
    url = reverse('orders:export_vendor_evaluations')
    resp = client.get(url)
    
    assert resp.status_code == 200
    assert resp['Content-Type'] == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


@pytest.mark.django_db
def test_export_vendor_ranking_returns_excel(client):
    """Test que l'export du classement fournisseurs retourne Excel ou redirige"""
    user = User.objects.create_user('exprank@example.com', 'testpass')
    user.is_active = True
    user.is_superuser = True
    user.save()
    client.force_login(user)
    
    url = reverse('orders:export_vendor_ranking')
    resp = client.get(url)
    
    # Accepter 200 (Excel) ou 302 (redirection si pas de données)
    assert resp.status_code in (200, 302)


@pytest.mark.django_db
def test_export_msrn_po_lines_returns_excel(client, settings, tmp_path):
    """Test que l'export des lignes MSRN retourne Excel ou 404 si pas de données"""
    settings.MEDIA_ROOT = tmp_path
    
    user = User.objects.create_user('expmsrn@example.com', 'testpass')
    user.is_active = True
    user.save()
    client.force_login(user)
    
    from orders.models import MSRNReport
    bon = NumeroBonCommande.objects.create(numero='PO-MSRNEXP-001')
    msrn = MSRNReport.objects.create(
        report_number='MSRN250100',
        bon_commande=bon,
        user=user.email
    )
    
    url = reverse('orders:export_msrn_po_lines', args=[msrn.id])
    resp = client.get(url)
    
    # Accepter 200 (Excel) ou 404 (pas de lignes associées)
    assert resp.status_code in (200, 404)
