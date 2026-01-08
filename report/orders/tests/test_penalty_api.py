# tests/test_penalty_api.py
import json
from decimal import Decimal
from unittest.mock import patch
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from orders.models import NumeroBonCommande, TimelineDelay

User = get_user_model()


class TestPenaltyAPI(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.user.is_active = True
        self.user.save()
        self.client.force_login(self.user)
        
        # Créer un bon de commande avec timeline delay
        self.bon_commande = NumeroBonCommande.objects.create(numero='TEST123')
        self.timeline_delay = TimelineDelay.objects.create(
            bon_commande=self.bon_commande,
            delay_part_mtn=5,
            delay_part_force_majeure=3,
            delay_part_vendor=2,
            quotite_realisee=Decimal('100.00')
        )

    @patch('orders.penalty_api.CELERY_AVAILABLE', False)
    def test_generate_penalty_report_get_success(self):
        """Test la génération de rapport de pénalité avec GET (mode synchrone)"""
        response = self.client.get(reverse('orders:generate_penalty_report_api', args=[self.bon_commande.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('PenaltySheet', response['Content-Disposition'])

    @patch('orders.penalty_api.CELERY_AVAILABLE', False)
    def test_generate_penalty_report_post_success(self):
        """Test la génération de rapport de pénalité avec POST et observation (mode synchrone)"""
        data = {
            'observation': 'Test observation text'
        }
        
        response = self.client.post(
            reverse('orders:generate_penalty_report_api', args=[self.bon_commande.id]),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')

    @patch('orders.penalty_api.CELERY_AVAILABLE', False)
    def test_generate_penalty_report_post_form_data(self):
        """Test la génération avec données de formulaire (mode synchrone)"""
        data = {
            'observation': 'Test observation text'
        }
        
        response = self.client.post(
            reverse('orders:generate_penalty_report_api', args=[self.bon_commande.id]),
            data=data
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')

    def test_generate_penalty_report_bon_not_found(self):
        """Test avec un bon de commande inexistant"""
        response = self.client.get(reverse('orders:generate_penalty_report_api', args=[999]))
        self.assertEqual(response.status_code, 404)
        
        data = json.loads(response.content)
        self.assertFalse(data['success'])
        self.assertEqual(data['error'], 'Bon de commande non trouvé')

    def test_generate_penalty_report_invalid_method(self):
        """Test avec une méthode HTTP invalide"""
        response = self.client.put(reverse('orders:generate_penalty_report_api', args=[self.bon_commande.id]))
        self.assertEqual(response.status_code, 405)
        
        data = json.loads(response.content)
        self.assertFalse(data['success'])
        self.assertEqual(data['error'], 'Méthode non autorisée')

    def test_generate_penalty_report_unauthenticated(self):
        """Test l'accès non authentifié"""
        self.client.logout()
        response = self.client.get(reverse('orders:generate_penalty_report_api', args=[self.bon_commande.id]))
        # Redirection vers la page de login
        self.assertEqual(response.status_code, 302)