# tests/test_msrn_api.py
import json
from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from orders.models import NumeroBonCommande, MSRNReport, Reception

User = get_user_model()


class TestMSRNAPI(TestCase):
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
        
        # Créer un rapport MSRN existant
        self.msrn_report = MSRNReport.objects.create(
            report_number='MSRN250001',
            bon_commande=self.bon_commande,
            user=self.user.email,
            retention_rate=Decimal('5.0'),
            retention_cause='Test retention cause'
        )

    def test_generate_msrn_report_success(self):
        """Test la génération d'un rapport MSRN avec succès"""
        data = {
            'retention_rate': '5.0',
            'retention_cause': 'Test retention cause'
        }
        
        response = self.client.post(
            reverse('orders:generate_msrn_report_api', args=[self.bon_commande.id]),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        self.assertIn('MSRN', response_data['report_number'])
        self.assertIsNotNone(response_data['download_url'])

    def test_generate_msrn_report_invalid_method(self):
        """Test la génération avec une méthode HTTP invalide"""
        response = self.client.get(reverse('orders:generate_msrn_report_api', args=[self.bon_commande.id]))
        self.assertEqual(response.status_code, 405)
        
        data = json.loads(response.content)
        self.assertFalse(data['success'])
        self.assertEqual(data['error'], 'Méthode non autorisée')

    def test_generate_msrn_report_bon_not_found(self):
        """Test la génération avec un bon de commande inexistant"""
        data = {
            'retention_rate': '5.0',
            'retention_cause': 'Test retention cause'
        }
        
        response = self.client.post(
            reverse('orders:generate_msrn_report_api', args=[999]),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 404)
        
        data = json.loads(response.content)
        self.assertFalse(data['success'])
        self.assertEqual(data['error'], 'Bon de commande non trouvé')

    def test_generate_msrn_report_invalid_retention_rate(self):
        """Test la génération avec un taux de rétention invalide"""
        # Taux trop élevé
        data = {
            'retention_rate': '15.0',
            'retention_cause': 'Test retention cause'
        }
        
        response = self.client.post(
            reverse('orders:generate_msrn_report_api', args=[self.bon_commande.id]),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        
        data = json.loads(response.content)
        self.assertFalse(data['success'])
        self.assertIn('taux de rétention', data['error'])

        # Taux négatif
        data = {
            'retention_rate': '-5.0',
            'retention_cause': 'Test retention cause'
        }
        
        response = self.client.post(
            reverse('orders:generate_msrn_report_api', args=[self.bon_commande.id]),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        
        data = json.loads(response.content)
        self.assertFalse(data['success'])
        self.assertIn('taux de rétention', data['error'])

    def test_generate_msrn_report_missing_retention_cause(self):
        """Test la génération sans cause de rétention quand le taux > 0"""
        data = {
            'retention_rate': '5.0',
            'retention_cause': ''
        }
        
        response = self.client.post(
            reverse('orders:generate_msrn_report_api', args=[self.bon_commande.id]),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        
        data = json.loads(response.content)
        self.assertFalse(data['success'])
        self.assertIn('cause de la rétention', data['error'])

    def test_update_msrn_retention_success(self):
        """Test la mise à jour du taux de rétention avec succès"""
        data = {
            'retention_rate': '7.5',
            'retention_cause': 'Updated retention cause'
        }
        
        response = self.client.post(
            reverse('orders:update_msrn_retention', args=[self.msrn_report.id]),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        self.assertEqual(response_data['msrn_report']['retention_rate'], 7.5)
        self.assertEqual(response_data['msrn_report']['retention_cause'], 'Updated retention cause')

        # Vérifier que l'objet a été mis à jour en base
        self.msrn_report.refresh_from_db()
        self.assertEqual(self.msrn_report.retention_rate, Decimal('7.5'))
        self.assertEqual(self.msrn_report.retention_cause, 'Updated retention cause')

    def test_update_msrn_retention_invalid_method(self):
        """Test la mise à jour avec une méthode HTTP invalide"""
        response = self.client.get(reverse('orders:update_msrn_retention', args=[self.msrn_report.id]))
        self.assertEqual(response.status_code, 405)
        
        data = json.loads(response.content)
        self.assertFalse(data['success'])
        self.assertEqual(data['error'], 'Méthode non autorisée')

    def test_update_msrn_retention_report_not_found(self):
        """Test la mise à jour avec un rapport MSRN inexistant"""
        data = {
            'retention_rate': '7.5',
            'retention_cause': 'Updated retention cause'
        }
        
        response = self.client.post(
            reverse('orders:update_msrn_retention', args=[999]),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 404)
        
        data = json.loads(response.content)
        self.assertFalse(data['success'])
        self.assertEqual(data['error'], 'Rapport MSRN non trouvé')

    def test_update_msrn_retention_invalid_json(self):
        """Test la mise à jour avec un JSON invalide"""
        response = self.client.post(
            reverse('orders:update_msrn_retention', args=[self.msrn_report.id]),
            data='invalid json',
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        
        data = json.loads(response.content)
        self.assertFalse(data['success'])
        self.assertEqual(data['error'], 'Format JSON invalide')

    def test_update_msrn_retention_invalid_retention_rate(self):
        """Test la mise à jour avec un taux de rétention invalide"""
        # Taux invalide (non numérique)
        data = {
            'retention_rate': 'invalid',
            'retention_cause': 'Test cause'
        }
        
        response = self.client.post(
            reverse('orders:update_msrn_retention', args=[self.msrn_report.id]),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        
        data = json.loads(response.content)
        self.assertFalse(data['success'])
        self.assertIn('Taux de rétention invalide', data['error'])

    def test_generate_msrn_report_unauthenticated(self):
        """Test la génération de rapport MSRN sans authentification"""
        self.client.logout()
        
        data = {
            'retention_rate': '5.0',
            'retention_cause': 'Test retention cause'
        }
        
        response = self.client.post(
            reverse('orders:generate_msrn_report_api', args=[self.bon_commande.id]),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        # Redirection vers la page de login
        self.assertEqual(response.status_code, 302)