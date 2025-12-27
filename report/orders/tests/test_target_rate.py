from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from decimal import Decimal
from orders.models import FichierImporte, NumeroBonCommande, Reception, LigneFichier, round_decimal

User = get_user_model()

class TestTargetRateLogic(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(email='test@example.com', password='password')
        self.user.is_active = True
        self.user.save()
        self.client.force_login(self.user)
        
        # Create common objects
        self.bon_commande = NumeroBonCommande.objects.create(numero='TEST_TARGET')
        self.fichier = FichierImporte.objects.create(fichier='test_file.xlsx')
        
    def test_vase_communiquant_symmetric(self):
        """Test simple distribution where lines are identical"""
        # Line A: 10 * 50 = 500
        bid_a = "BID_A"
        LigneFichier.objects.create(
            fichier=self.fichier, business_id=bid_a, numero_ligne=1, 
            contenu={'Unit Price': '50', 'Quantity': '10', 'Order': 'TEST_TARGET'}
        )
        Reception.objects.create(
            bon_commande=self.bon_commande, fichier=self.fichier, business_id=bid_a,
            ordered_quantity=Decimal('10'), quantity_delivered=Decimal('0'), unit_price=Decimal('50'),
            amount_delivered=Decimal('0'), quantity_payable=Decimal('0'), amount_payable=Decimal('0')
        )
        
        # Line B: 10 * 50 = 500
        bid_b = "BID_B"
        LigneFichier.objects.create(
            fichier=self.fichier, business_id=bid_b, numero_ligne=2, 
            contenu={'Unit Price': '50', 'Quantity': '10', 'Order': 'TEST_TARGET'}
        )
        Reception.objects.create(
            bon_commande=self.bon_commande, fichier=self.fichier, business_id=bid_b,
            ordered_quantity=Decimal('10'), quantity_delivered=Decimal('0'), unit_price=Decimal('50'),
            amount_delivered=Decimal('0'), quantity_payable=Decimal('0'), amount_payable=Decimal('0')
        )
        
        # Total Amount = 1000. Current = 0.
        # Target 50% -> Need 500.
        # Remaining Cap = 1000. Ratio = 0.5.
        
        data = {
            'bon_number': 'TEST_TARGET',
            'target_rate': 50,
            'business_ids': [bid_a, bid_b],
            'lines_info': [
                {'business_id': bid_a, 'ordered_quantity': 10},
                {'business_id': bid_b, 'ordered_quantity': 10}
            ]
        }
        
        response = self.client.post(
            reverse('orders:apply_target_rate', args=[self.fichier.id]),
            data,
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Check results
        rec_a = Reception.objects.get(business_id=bid_a)
        rec_b = Reception.objects.get(business_id=bid_b)
        
        # Should be 5 each
        self.assertEqual(rec_a.quantity_delivered, Decimal('5.0000'))
        self.assertEqual(rec_b.quantity_delivered, Decimal('5.0000'))
        
    def test_vase_communiquant_asymmetric(self):
        """Test distribution with different remaining capacities"""
        # Line A: Ordered 10, Delivered 8, Price 50. Remaining Cap = 2*50 = 100.
        bid_a = "BID_A"
        Reception.objects.create(
            bon_commande=self.bon_commande, fichier=self.fichier, business_id=bid_a,
            ordered_quantity=Decimal('10'), quantity_delivered=Decimal('8'), unit_price=Decimal('50'),
            amount_delivered=Decimal('400'), quantity_payable=Decimal('8'), amount_payable=Decimal('400')
        )
        
        # Line B: Ordered 10, Delivered 0, Price 50. Remaining Cap = 10*50 = 500.
        bid_b = "BID_B"
        Reception.objects.create(
            bon_commande=self.bon_commande, fichier=self.fichier, business_id=bid_b,
            ordered_quantity=Decimal('10'), quantity_delivered=Decimal('0'), unit_price=Decimal('50'),
            amount_delivered=Decimal('0'), quantity_payable=Decimal('0'), amount_payable=Decimal('0')
        )
        
        # Total Amount = 1000. Current = 400 (40%).
        # Target 70% -> Need 700 total (add 300).
        # Remaining Cap = 100 + 500 = 600.
        # Ratio = 300 / 600 = 0.5.
        
        # Line A add: 2 * 0.5 = 1. New Total = 9.
        # Line B add: 10 * 0.5 = 5. New Total = 5.
        
        data = {
            'bon_number': 'TEST_TARGET',
            'target_rate': 70,
            'business_ids': [bid_a, bid_b],
            'lines_info': [
                {'business_id': bid_a, 'ordered_quantity': 10},
                {'business_id': bid_b, 'ordered_quantity': 10}
            ]
        }
        
        response = self.client.post(
            reverse('orders:apply_target_rate', args=[self.fichier.id]),
            data,
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        rec_a = Reception.objects.get(business_id=bid_a)
        rec_b = Reception.objects.get(business_id=bid_b)
        
        self.assertEqual(rec_a.quantity_delivered, Decimal('9.0000'))
        self.assertEqual(rec_b.quantity_delivered, Decimal('5.0000'))
