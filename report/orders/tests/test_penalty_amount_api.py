# tests/test_penalty_amount_api.py
import json
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from orders.models import NumeroBonCommande

User = get_user_model()


class TestPenaltyAmountAPI(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.user.is_active = True
        self.user.save()
        self.client.force_login(self.user)
        
        # Créer un bon de commande pour les tests
        self.bon_commande = NumeroBonCommande.objects.create(numero='TEST123')

    def test_get_penalty_amount_success(self):
        """Test la récupération du montant de pénalité avec succès"""
        response = self.client.get(reverse('orders:get_penalty_amount_api', args=[self.bon_commande.id]))
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertIn('penalty_due', data)
        self.assertIn('currency', data)

    def test_get_penalty_amount_bon_not_found(self):
        """Test avec un bon de commande inexistant"""
        response = self.client.get(reverse('orders:get_penalty_amount_api', args=[999]))
        self.assertEqual(response.status_code, 404)

    def test_get_penalty_amount_unauthenticated(self):
        """Test l'accès non authentifié"""
        self.client.logout()
        response = self.client.get(reverse('orders:get_penalty_amount_api', args=[self.bon_commande.id]))
        # Redirection vers la page de login
        self.assertEqual(response.status_code, 302)

    def test_get_penalty_amount_invalid_method(self):
        """Test avec une méthode HTTP invalide"""
        response = self.client.post(reverse('orders:get_penalty_amount_api', args=[self.bon_commande.id]))
        self.assertEqual(response.status_code, 405)