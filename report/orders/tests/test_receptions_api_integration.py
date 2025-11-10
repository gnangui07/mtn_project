import pytest
from decimal import Decimal
from django.urls import reverse
from django.contrib.auth import get_user_model
from orders.models import FichierImporte, NumeroBonCommande, LigneFichier, Reception

User = get_user_model()


@pytest.mark.django_db
def test_update_quantity_delivered_get_returns_receptions_json(client):
    # Utilisateur connecté
    user = User.objects.create_user('recv@example.com', 'testpass')
    user.is_active = True
    user.save()
    client.force_login(user)

    # Données minimales
    bon = NumeroBonCommande.objects.create(numero='PO-R-001')
    fichier = FichierImporte.objects.create(fichier='test.csv', utilisateur=user)

    # Ligne pour enrichir les infos (supplier, etc.)
    LigneFichier.objects.create(
        fichier=fichier,
        numero_ligne=999,
        business_id='BIZ1',
        contenu={'Order': 'PO-R-001', 'Supplier': 'ACME'}
    )

    # Réception existante
    Reception.objects.create(
        bon_commande=bon,
        fichier=fichier,
        business_id='BIZ1',
        quantity_delivered=Decimal('10'),
        ordered_quantity=Decimal('100'),
        unit_price=Decimal('5.00')
    )

    url = reverse('orders:update_quantity_delivered', args=[fichier.id])
    resp = client.get(url, {'bon_number': 'PO-R-001'})

    assert resp.status_code == 200
    data = resp.json()
    assert data['status'] == 'success'
    assert 'receptions' in data
    assert 'BIZ1' in data['receptions']
    # Clés essentielles présentes
    expected_keys = {
        'quantity_delivered', 'ordered_quantity', 'quantity_not_delivered',
        'unit_price', 'amount_delivered', 'amount_not_delivered',
        'quantity_payable', 'amount_payable', 'supplier', 'is_complete'
    }
    assert expected_keys.issubset(set(data['receptions']['BIZ1'].keys()))


@pytest.mark.django_db
def test_update_quantity_delivered_get_missing_param_returns_400(client):
    user = User.objects.create_user('recv2@example.com', 'testpass')
    user.is_active = True
    user.save()
    client.force_login(user)

    fichier = FichierImporte.objects.create(fichier='test2.csv', utilisateur=user)

    url = reverse('orders:update_quantity_delivered', args=[fichier.id])
    resp = client.get(url)  # pas de bon_number

    assert resp.status_code == 400
    data = resp.json()
    assert data['status'] == 'error'


@pytest.mark.django_db
def test_update_quantity_delivered_get_unknown_bon_returns_404(client):
    user = User.objects.create_user('recv3@example.com', 'testpass')
    user.is_active = True
    user.save()
    client.force_login(user)

    fichier = FichierImporte.objects.create(fichier='test3.csv', utilisateur=user)

    url = reverse('orders:update_quantity_delivered', args=[fichier.id])
    resp = client.get(url, {'bon_number': 'PO-UNKNOWN'})

    assert resp.status_code == 404
    data = resp.json()
    assert data['status'] == 'error'
