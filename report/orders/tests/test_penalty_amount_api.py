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

    def test_get_penalty_amount_formats_none_to_zero(self):
        """penalties_due None doit être formaté en '0'"""
        from unittest.mock import patch
        url = reverse('orders:get_penalty_amount_api', args=[self.bon_commande.id])
        with patch('orders.penalty_amount_api.collect_penalty_context') as mock_collect:
            mock_collect.return_value = {"penalties_due": None, "currency": "XOF"}
            resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertTrue(data.get('success'))
        self.assertEqual(data.get('penalty_due'), '0')
        self.assertEqual(data.get('currency'), 'XOF')

    def test_get_penalty_amount_invalid_penalty_value(self):
        """penalties_due non numérique doit retourner '0' (gestion d'exception)"""
        from unittest.mock import patch
        url = reverse('orders:get_penalty_amount_api', args=[self.bon_commande.id])
        with patch('orders.penalty_amount_api.collect_penalty_context') as mock_collect:
            mock_collect.return_value = {"penalties_due": "abc", "currency": "XOF"}
            resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertTrue(data.get('success'))
        self.assertEqual(data.get('penalty_due'), '0')

    def test_get_penalty_amount_internal_error(self):
        """Erreur interne lors du calcul doit renvoyer 500 et success False"""
        from unittest.mock import patch
        url = reverse('orders:get_penalty_amount_api', args=[self.bon_commande.id])
        with patch('orders.penalty_amount_api.collect_penalty_context') as mock_collect:
            mock_collect.side_effect = Exception('boom')
            resp = self.client.get(url)
        self.assertEqual(resp.status_code, 500)
        data = json.loads(resp.content)
        self.assertFalse(data.get('success'))