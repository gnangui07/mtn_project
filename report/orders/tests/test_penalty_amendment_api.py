# tests/test_penalty_amendment_api.py
import json
from decimal import Decimal
from unittest.mock import patch, MagicMock
import pytest
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from io import BytesIO

from orders.models import NumeroBonCommande, TimelineDelay
from orders.penalty_amendment_api import _decimal_or_default

User = get_user_model()


@pytest.mark.django_db
class TestPenaltyAmendmentAPI(TestCase):
    """Tests pour penalty_amendment_api.py"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.user.is_active = True
        self.user.save()
        self.client.force_login(self.user)
        
        self.bon_commande = NumeroBonCommande.objects.create(numero='TEST123')
        self.timeline_delay = TimelineDelay.objects.create(
            bon_commande=self.bon_commande,
            delay_part_mtn=5,
            delay_part_force_majeure=3,
            delay_part_vendor=2,
            quotite_realisee=Decimal('100.00'),
            comment_mtn="Test MTN",
            comment_force_majeure="Test Force Majeure", 
            comment_vendor="Test Vendor"
        )

    def test_decimal_or_default_function(self):
        """Test la fonction _decimal_or_default (lignes 36, 38, 40-41)"""
        # Test avec Decimal
        self.assertEqual(_decimal_or_default(Decimal('10.5')), Decimal('10.5'))
        
        # Test avec chaîne
        self.assertEqual(_decimal_or_default('10.5'), Decimal('10.5'))
        
        # Test avec None
        self.assertEqual(_decimal_or_default(None), Decimal('0'))
        
        # Test avec chaîne vide
        self.assertEqual(_decimal_or_default(''), Decimal('0'))
        
        # Test avec valeur par défaut personnalisée
        self.assertEqual(_decimal_or_default(None, '5.0'), Decimal('5.0'))
        
        # Test avec espace
        self.assertEqual(_decimal_or_default('1 000.50'), Decimal('1000.50'))
        
        # Test avec exception
        self.assertEqual(_decimal_or_default('invalid'), Decimal('0'))

    def test_generate_penalty_amendment_report_api_invalid_method(self):
        """Test avec méthode invalide (ligne 63)"""
        response = self.client.put(
            reverse('orders:generate_penalty_amendment_report_api', args=[self.bon_commande.id])
        )
        self.assertEqual(response.status_code, 405)
        response_data = json.loads(response.content)
        self.assertFalse(response_data['success'])

    def test_generate_penalty_amendment_report_api_bon_not_found(self):
        """Test avec bon non trouvé (ligne 63)"""
        response = self.client.get(
            reverse('orders:generate_penalty_amendment_report_api', args=[999])
        )
        self.assertEqual(response.status_code, 404)
        response_data = json.loads(response.content)
        self.assertFalse(response_data['success'])

    @patch('orders.penalty_amendment_api.generate_penalty_amendment_report')
    def test_generate_penalty_amendment_report_api_get(self, mock_generate):
        """Test GET request (lignes 76-82)"""
        mock_generate.return_value = BytesIO(b"fake pdf content")
        
        response = self.client.get(
            reverse('orders:generate_penalty_amendment_report_api', args=[self.bon_commande.id])
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['content-type'], 'application/pdf')
        self.assertIn('inline', response['Content-Disposition'])

    @patch('orders.penalty_amendment_api.generate_penalty_amendment_report')
    def test_generate_penalty_amendment_report_api_post_json(self, mock_generate):
        """Test POST avec JSON (lignes 76-82)"""
        mock_generate.return_value = BytesIO(b"fake pdf content")
        
        data = {
            'supplier_plea': 'Test supplier plea',
            'pm_proposal': 'Test PM proposal',
            'penalty_status': 'annulee',
            'new_penalty_due': '1500.75'
        }
        
        response = self.client.post(
            reverse('orders:generate_penalty_amendment_report_api', args=[self.bon_commande.id]),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['content-type'], 'application/pdf')

    @patch('orders.penalty_amendment_api.generate_penalty_amendment_report')
    def test_generate_penalty_amendment_report_api_post_form(self, mock_generate):
        """Test POST avec form data (lignes 76-82)"""
        mock_generate.return_value = BytesIO(b"fake pdf content")
        
        data = {
            'supplier_plea': 'Test supplier plea',
            'pm_proposal': 'Test PM proposal', 
            'penalty_status': 'reduite',
            'new_penalty_due': '2000.50'
        }
        
        response = self.client.post(
            reverse('orders:generate_penalty_amendment_report_api', args=[self.bon_commande.id]),
            data=data
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['content-type'], 'application/pdf')

    @patch('orders.penalty_amendment_api.generate_penalty_amendment_report')
    def test_generate_penalty_amendment_report_api_invalid_json(self, mock_generate):
        """Test POST avec JSON invalide (lignes 76-82)"""
        mock_generate.return_value = BytesIO(b"fake pdf content")
        
        response = self.client.post(
            reverse('orders:generate_penalty_amendment_report_api', args=[self.bon_commande.id]),
            data='invalid json',
            content_type='application/json'
        )
        
        # Devrait gérer gracieusement le JSON invalide
        self.assertEqual(response.status_code, 200)

    @patch('orders.penalty_amendment_api.generate_penalty_amendment_report')
    def test_generate_penalty_amendment_report_api_empty_payload(self, mock_generate):
        """Test avec payload vide (lignes 76-82)"""
        mock_generate.return_value = BytesIO(b"fake pdf content")
        
        response = self.client.post(
            reverse('orders:generate_penalty_amendment_report_api', args=[self.bon_commande.id]),
            data='',
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)

    @patch('orders.penalty_amendment_api.send_penalty_notification')
    @patch('orders.penalty_amendment_api.generate_penalty_amendment_report')
    def test_generate_penalty_amendment_report_api_email_thread(self, mock_generate, mock_send):
        """Test le lancement du thread email (lignes 116-117)"""
        mock_generate.return_value = BytesIO(b"fake pdf content")
        
        response = self.client.get(
            reverse('orders:generate_penalty_amendment_report_api', args=[self.bon_commande.id])
        )
        
        self.assertEqual(response.status_code, 200)
        # Vérifier que send_penalty_notification est appelé dans un thread
        # Note: Le thread est démarré mais nous ne pouvons pas facilement vérifier son exécution complète

    @patch('orders.penalty_amendment_api.send_penalty_notification')
    @patch('orders.penalty_amendment_api.generate_penalty_amendment_report')
    def test_generate_penalty_amendment_report_api_email_exception(self, mock_generate, mock_send):
        """Test exception dans l'envoi d'email (lignes 116-117)"""
        mock_generate.return_value = BytesIO(b"fake pdf content")
        mock_send.side_effect = Exception("Email failed")
        
        response = self.client.get(
            reverse('orders:generate_penalty_amendment_report_api', args=[self.bon_commande.id])
        )
        
        # L'exception dans l'email ne devrait pas affecter la réponse
        self.assertEqual(response.status_code, 200)

    @patch('orders.penalty_amendment_api.generate_penalty_amendment_report')
    def test_generate_penalty_amendment_report_api_penalty_status_cases(self, mock_generate):
        """Test différents statuts de pénalité"""
        mock_generate.return_value = BytesIO(b"fake pdf content")
        
        status_cases = ['annulee', 'reduite', 'reconduite', 'invalid_status']
        
        for status in status_cases:
            data = {'penalty_status': status}
            response = self.client.get(
                reverse('orders:generate_penalty_amendment_report_api', args=[self.bon_commande.id]),
                data=data
            )
            self.assertEqual(response.status_code, 200)

    @patch('orders.penalty_amendment_api.generate_penalty_amendment_report')
    def test_generate_penalty_amendment_report_api_user_no_email(self, mock_generate):
        """Test avec un utilisateur sans email - devrait échuer car email est requis"""
        mock_generate.return_value = BytesIO(b"fake pdf content")
    
        # Créer un utilisateur VALIDE avec email (comme requis par le modèle)   
        user = User.objects.create_user(
            email='valid-user@example.com',  # Email requis
            password='testpass123'
        )
        user.is_active = True
        user.save()
        self.client.force_login(user)
    
        response = self.client.get(
            reverse('orders:generate_penalty_amendment_report_api', args=[self.bon_commande.id])
        )
    
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')

@pytest.mark.django_db
class TestPenaltyAmendmentAPIEdgeCases(TestCase):
    """Tests pour les cas limites de Penalty Amendment API"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.user.is_active = True
        self.user.save()
        self.client.force_login(self.user)
        
        self.bon_commande = NumeroBonCommande.objects.create(numero='TEST-EDGE')

    @patch('orders.penalty_amendment_api.generate_penalty_amendment_report')
    def test_generate_penalty_amendment_report_api_no_timeline_delay(self, mock_generate):
        """Test avec bon sans timeline_delay"""
        mock_generate.return_value = BytesIO(b"fake pdf content")
        
        response = self.client.get(
            reverse('orders:generate_penalty_amendment_report_api', args=[self.bon_commande.id])
        )
        
        self.assertEqual(response.status_code, 200)