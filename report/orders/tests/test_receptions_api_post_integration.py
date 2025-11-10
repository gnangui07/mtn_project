import pytest
import json
from decimal import Decimal
from django.urls import reverse
from django.contrib.auth import get_user_model
from orders.models import FichierImporte, NumeroBonCommande, LigneFichier, Reception

User = get_user_model()


@pytest.mark.django_db
def test_update_quantity_delivered_post_success(client):
    user = User.objects.create_user('recvpost@example.com', 'testpass')
    user.is_active = True
    user.save()
    client.force_login(user)

    bon = NumeroBonCommande.objects.create(numero='PO-P-001')
    fichier = FichierImporte.objects.create(fichier='post.csv', utilisateur=user)

    # Ligne avec prix unitaire pour récupérer unit_price
    LigneFichier.objects.create(
        fichier=fichier,
        numero_ligne=100,
        business_id='BIZP1',
        contenu={'Order': 'PO-P-001', 'Price': '5.00'}
    )

    # Réception existante (0 par défaut)
    Reception.objects.create(
        bon_commande=bon,
        fichier=fichier,
        business_id='BIZP1',
        quantity_delivered=Decimal('0'),
        ordered_quantity=Decimal('100'),
        unit_price=Decimal('5.00')
    )

    url = reverse('orders:update_quantity_delivered', args=[fichier.id])
    payload = {
        'bon_number': 'PO-P-001',
        'business_id': 'BIZP1',
        'quantity_delivered': '10',  # incrément
        'original_quantity': '100'
    }
    resp = client.post(url, data=json.dumps(payload), content_type='application/json')

    assert resp.status_code == 200
    data = resp.json()
    assert data['status'] == 'success'
    assert data['quantity_delivered'] == 10.0
    assert data['ordered_quantity'] == 100.0
    assert 'amount_delivered' in data and 'amount_payable' in data


@pytest.mark.django_db
def test_update_quantity_delivered_post_exceeds_ordered_returns_400(client):
    user = User.objects.create_user('recvpost2@example.com', 'testpass')
    user.is_active = True
    user.save()
    client.force_login(user)

    bon = NumeroBonCommande.objects.create(numero='PO-P-002')
    fichier = FichierImporte.objects.create(fichier='post2.csv', utilisateur=user)

    LigneFichier.objects.create(
        fichier=fichier,
        numero_ligne=101,
        business_id='BIZP2',
        contenu={'Order': 'PO-P-002', 'Price': '5.00'}
    )

    # Déjà 95 reçus
    Reception.objects.create(
        bon_commande=bon,
        fichier=fichier,
        business_id='BIZP2',
        quantity_delivered=Decimal('95'),
        ordered_quantity=Decimal('100'),
        unit_price=Decimal('5.00')
    )

    url = reverse('orders:update_quantity_delivered', args=[fichier.id])
    payload = {
        'bon_number': 'PO-P-002',
        'business_id': 'BIZP2',
        'quantity_delivered': '10',  # porterait le total à 105 > 100
        'original_quantity': '100'
    }
    resp = client.post(url, data=json.dumps(payload), content_type='application/json')

    assert resp.status_code == 400
    data = resp.json()
    assert data['status'] == 'error'
    assert 'dépasse' in data.get('message', '').lower()


@pytest.mark.django_db
def test_update_quantity_delivered_post_negative_correction_below_zero_400(client):
    user = User.objects.create_user('recvpost3@example.com', 'testpass')
    user.is_active = True
    user.save()
    client.force_login(user)

    bon = NumeroBonCommande.objects.create(numero='PO-P-003')
    fichier = FichierImporte.objects.create(fichier='post3.csv', utilisateur=user)

    LigneFichier.objects.create(
        fichier=fichier,
        numero_ligne=102,
        business_id='BIZP3',
        contenu={'Order': 'PO-P-003', 'Price': '5.00'}
    )

    # Déjà 5 reçus
    Reception.objects.create(
        bon_commande=bon,
        fichier=fichier,
        business_id='BIZP3',
        quantity_delivered=Decimal('5'),
        ordered_quantity=Decimal('100'),
        unit_price=Decimal('5.00')
    )

    url = reverse('orders:update_quantity_delivered', args=[fichier.id])
    payload = {
        'bon_number': 'PO-P-003',
        'business_id': 'BIZP3',
        'quantity_delivered': '-10',  # final total -5 < 0
        'original_quantity': '100'
    }
    resp = client.post(url, data=json.dumps(payload), content_type='application/json')

    assert resp.status_code == 400
    data = resp.json()
    assert data['status'] == 'error'
    assert 'négatif' in data.get('message', '').lower()
