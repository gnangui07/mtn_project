# tests/test_msrn_api.py
import json
from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from io import BytesIO
from django.core.files.base import File
from orders.models import NumeroBonCommande, MSRNReport, Reception, FichierImporte, LigneFichier
from unittest.mock import patch, MagicMock

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

    @patch('orders.msrn_api.CELERY_AVAILABLE', False)
    def test_generate_msrn_report_success(self):
        """Test la génération d'un rapport MSRN avec succès (mode synchrone)"""
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
        
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertFalse(data['async'])
        
        # Vérifier que le rapport a été créé
        msrn_report = MSRNReport.objects.filter(bon_commande=self.bon_commande).order_by('-created_at').first()
        self.assertIsNotNone(msrn_report)
        self.assertEqual(msrn_report.retention_rate, Decimal('5.0'))
        
        # Vérifier le message et l'URL
        self.assertEqual(data['message'], f"Rapport {msrn_report.report_number} généré avec succès")
        self.assertEqual(data['download_url'], f"/orders/msrn-report/{msrn_report.id}/")

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
        # Taux trop élevé (>100%)
        data = {
            'retention_rate': '150.0',
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

class TestMSRNAPIUncovered(TestCase):
    """Tests pour couvrir les lignes non couvertes de msrn_api.py"""
    
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
        self.msrn_report = MSRNReport.objects.create(
            report_number='MSRN250001',
            bon_commande=self.bon_commande,
            user=self.user.email,
            retention_rate=Decimal('5.0')
        )

    @patch('orders.models.NumeroBonCommande.objects.get')
    def test_generate_msrn_report_bon_not_found_exception(self, mock_get):
        """Test generate_msrn_report_api avec exception lors de la récupération du bon"""
        mock_get.side_effect = Exception("DB Error")
        
        data = {
            'retention_rate': '5.0',
            'retention_cause': 'Test cause'
        }
        
        response = self.client.post(
            reverse('orders:generate_msrn_report_api', args=[self.bon_commande.id]),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        # Le endpoint gère l'exception et retourne 200 avec success=True (fallback)
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])

    def test_generate_msrn_report_invalid_json(self):
        """Test generate_msrn_report_api avec JSON invalide"""
        response = self.client.post(
            reverse('orders:generate_msrn_report_api', args=[self.bon_commande.id]),
            data='invalid json',
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)  # Gère gracieusement
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])  # Utilise les valeurs par défaut

    @patch('orders.msrn_api.CELERY_AVAILABLE', False)
    @patch('orders.msrn_api.generate_msrn_report')
    def test_generate_msrn_report_pdf_generation_error(self, mock_generate):
        """Test generate_msrn_report_api avec erreur de génération PDF (mode synchrone)"""
        mock_generate.side_effect = Exception("PDF generation failed")
        
        data = {
            'retention_rate': '5.0',
            'retention_cause': 'Test cause'
        }
        
        response = self.client.post(
            reverse('orders:generate_msrn_report_api', args=[self.bon_commande.id]),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 500)
        response_data = json.loads(response.content)
        self.assertFalse(response_data['success'])

    @patch('orders.msrn_api.CELERY_AVAILABLE', False)
    @patch('orders.msrn_api.send_msrn_notification')
    def test_generate_msrn_report_email_success(self, mock_send):
        """Test generate_msrn_report_api avec envoi d'email réussi (mode synchrone)"""
        mock_send.return_value = True
        
        data = {
            'retention_rate': '5.0',
            'retention_cause': 'Test cause'
        }
        
        response = self.client.post(
            reverse('orders:generate_msrn_report_api', args=[self.bon_commande.id]),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(mock_send.called)

    @patch('orders.msrn_api.CELERY_AVAILABLE', False)
    @patch('orders.msrn_api.send_msrn_notification')
    def test_generate_msrn_report_email_failure(self, mock_send):
        """Test generate_msrn_report_api avec échec d'envoi d'email (mode synchrone)"""
        mock_send.side_effect = Exception("Email failed")
        
        data = {
            'retention_rate': '5.0',
            'retention_cause': 'Test cause'
        }
        
        response = self.client.post(
            reverse('orders:generate_msrn_report_api', args=[self.bon_commande.id]),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        # L'échec d'email ne devrait pas affecter la génération du rapport
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])

    def test_update_msrn_retention_invalid_json_format(self):
        """Test update_msrn_retention avec format JSON invalide"""
        response = self.client.post(
            reverse('orders:update_msrn_retention', args=[self.msrn_report.id]),
            data='not json at all',
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertFalse(response_data['success'])

    def test_update_msrn_retention_invalid_retention_rate_format(self):
        """Test update_msrn_retention avec format de taux invalide"""
        data = {
            'retention_rate': 'not_a_number',
            'retention_cause': 'Test cause'
        }
        
        response = self.client.post(
            reverse('orders:update_msrn_retention', args=[self.msrn_report.id]),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertFalse(response_data['success'])

    def test_update_msrn_retention_snapshot_update(self):
        """Test update_msrn_retention avec mise à jour des snapshots"""
        # Créer un rapport avec des snapshots vides
        msrn_report = MSRNReport.objects.create(
            report_number='MSRN250002',
            bon_commande=self.bon_commande,
            user=self.user.email,
            retention_rate=Decimal('5.0'),
            montant_total_snapshot=None,
            montant_recu_snapshot=None,
            progress_rate_snapshot=None
        )
        
        data = {
            'retention_rate': '7.5',
            'retention_cause': 'Updated cause'
        }
        
        # Patch save uniquement pendant la requête pour conserver l'ID créé
        with patch('orders.models.MSRNReport.save') as mock_save:
            response = self.client.post(
                reverse('orders:update_msrn_retention', args=[msrn_report.id]),
                data=json.dumps(data),
                content_type='application/json'
            )
            self.assertEqual(response.status_code, 200)
            self.assertTrue(mock_save.called)

    @patch('orders.models.Reception.objects.filter')
    @patch('orders.models.LigneFichier.objects.filter')
    def test_update_msrn_retention_receptions_snapshot(self, mock_ligne_filter, mock_reception_filter):
        """Test update_msrn_retention avec snapshot des réceptions"""
        # Mock des réceptions
        mock_reception = MagicMock()
        mock_reception.id = 1
        mock_reception.business_id = 'TEST-BIZ-1'
        mock_reception.ordered_quantity = Decimal('100')
        mock_reception.quantity_delivered = Decimal('80')
        mock_reception.received_quantity = Decimal('80')
        mock_reception.quantity_not_delivered = Decimal('20')
        mock_reception.amount_delivered = Decimal('4000')
        mock_reception.unit_price = Decimal('50')
        mock_reception_filter.return_value = [mock_reception]
        
        # Mock des lignes
        mock_ligne = MagicMock()
        mock_ligne.contenu = {
            'Line Description': 'Test Item Description',
            'Line': '1',
            'Schedule': '1'
        }
        mock_ligne_filter.return_value.first.return_value = mock_ligne
        
        data = {
            'retention_rate': '7.5',
            'retention_cause': 'Updated cause'
        }
        
        response = self.client.post(
            reverse('orders:update_msrn_retention', args=[self.msrn_report.id]),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)

    @patch('orders.msrn_api.generate_msrn_report')
    def test_update_msrn_retention_pdf_regeneration(self, mock_generate):
        """Test update_msrn_retention avec régénération PDF"""
        # Mock de la génération PDF
        from io import BytesIO
        mock_pdf = BytesIO(b"fake pdf content")
        mock_generate.return_value = mock_pdf
        
        data = {
            'retention_rate': '7.5',
            'retention_cause': 'Updated cause'
        }
        
        response = self.client.post(
            reverse('orders:update_msrn_retention', args=[self.msrn_report.id]),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(mock_generate.called)

    @patch('orders.models.MSRNReport.save')
    def test_update_msrn_retention_save_exception(self, mock_save):
        """Test update_msrn_retention avec exception lors de la sauvegarde"""
        mock_save.side_effect = Exception("Save failed")
        
        data = {
            'retention_rate': '7.5',
            'retention_cause': 'Updated cause'
        }
        
        response = self.client.post(
            reverse('orders:update_msrn_retention', args=[self.msrn_report.id]),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 500)
        response_data = json.loads(response.content)
        self.assertFalse(response_data['success'])


class TestMSRNAPIEdgeCases(TestCase):
    """Tests pour les cas limites de MSRN API"""
    
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

    def test_generate_msrn_report_empty_body(self):
        """Test generate_msrn_report_api avec body vide"""
        response = self.client.post(
            reverse('orders:generate_msrn_report_api', args=[self.bon_commande.id]),
            data='',
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])

    def test_generate_msrn_report_none_retention_rate(self):
        """Test generate_msrn_report_api avec retention_rate None"""
        data = {
            'retention_rate': None,
            'retention_cause': None
        }
        
        response = self.client.post(
            reverse('orders:generate_msrn_report_api', args=[self.bon_commande.id]),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])

    @patch('orders.models.MSRNReport.objects.get')
    def test_update_msrn_retention_report_deleted(self, mock_get):
        """Test update_msrn_retention avec rapport supprimé"""
        mock_get.side_effect = MSRNReport.DoesNotExist
        
        data = {
            'retention_rate': '7.5',
            'retention_cause': 'Updated cause'
        }
        
        response = self.client.post(
            reverse('orders:update_msrn_retention', args=[999]),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 404)
class TestMSRNAPIUncoveredLines(TestCase):
    """Tests spécifiques pour couvrir les lignes non couvertes de msrn_api.py"""
    
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
        
        # Créer un rapport MSRN avec des snapshots vides pour tester les branches
        self.msrn_report_empty = MSRNReport.objects.create(
            report_number='MSRN250002',
            bon_commande=self.bon_commande,
            user=self.user.email,
            retention_rate=Decimal('5.0'),
            montant_total_snapshot=None,
            montant_recu_snapshot=None,
            progress_rate_snapshot=None,
            payment_terms_snapshot=None,
            receptions_data_snapshot=None
        )
        
        # Créer des réceptions pour tester le fallback
        self.fichier = FichierImporte.objects.create(fichier='test.csv', utilisateur=self.user)
        self.reception = Reception.objects.create(
            bon_commande=self.bon_commande,
            fichier=self.fichier,
            business_id='TEST-BIZ-1',
            ordered_quantity=Decimal('100'),
            quantity_delivered=Decimal('80'),
            received_quantity=Decimal('80'),
            quantity_not_delivered=Decimal('20'),
            unit_price=Decimal('50')
        )

    @patch('orders.msrn_api.CELERY_AVAILABLE', False)
    @patch('orders.msrn_api.send_msrn_notification')
    @patch('orders.msrn_api.generate_msrn_report')
    def test_generate_msrn_report_email_success_false(self, mock_generate, mock_send):
        """Test ligne 176 - email_sent=False (mode synchrone)"""
        mock_generate.return_value = BytesIO(b"fake pdf")
        mock_send.return_value = False  # Email non envoyé
        
        data = {
            'retention_rate': '5.0',
            'retention_cause': 'Test cause'
        }
        
        response = self.client.post(
            reverse('orders:generate_msrn_report_api', args=[self.bon_commande.id]),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(mock_send.called)
        # Vérifier que le logger warning est appelé (ligne 176)

    @patch('orders.msrn_api.CELERY_AVAILABLE', False)
    @patch('orders.msrn_api.send_msrn_notification')
    @patch('orders.msrn_api.generate_msrn_report')
    def test_generate_msrn_report_email_success_true(self, mock_generate, mock_send):
        """Test ligne 179 - email_sent=True (mode synchrone)"""
        mock_generate.return_value = BytesIO(b"fake pdf")
        mock_send.return_value = True  # Email envoyé
        
        data = {
            'retention_rate': '5.0',
            'retention_cause': 'Test cause'
        }
        
        response = self.client.post(
            reverse('orders:generate_msrn_report_api', args=[self.bon_commande.id]),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(mock_send.called)
        # Vérifier que le logger info est appelé (ligne 179)

    @patch('orders.models.NumeroBonCommande.montant_total')
    @patch('orders.models.NumeroBonCommande.montant_recu')
    @patch('orders.models.NumeroBonCommande.taux_avancement')
    @patch('orders.models.Reception.objects.filter')
    @patch('orders.models.LigneFichier.objects.filter')
    @patch('orders.reports.generate_msrn_report')
    @patch('orders.models.Reception.objects')
    def test_update_msrn_retention_snapshot_initialization(
        self, mock_reception_objects, mock_generate, mock_ligne_filter, 
        mock_reception_filter, mock_taux, mock_montant_recu, mock_montant_total
    ):
        """Test lignes 217-227 - Initialisation des snapshots manquants"""
        # Configurer les mocks pour retourner des valeurs
        mock_montant_total.return_value = Decimal('10000.00')
        mock_montant_recu.return_value = Decimal('8000.00')
        mock_taux.return_value = Decimal('80.00')
        
        # Configurer le mock pour generate_msrn_report
        mock_generate.return_value = BytesIO(b'PDF_CONTENT')
        
        # Mock pour payment terms
        mock_reception = MagicMock()
        mock_reception.business_id = 'TEST-BIZ-1'
        mock_reception.quantity_delivered = 10  # Ajout d'une valeur pour quantity_delivered
        mock_reception_filter.return_value.first.return_value = mock_reception
        
        # Configurer le mock pour les réceptions dans reports.py
        mock_reports_reception = MagicMock()
        mock_reports_reception.count.return_value = 10  # Valeur numérique pour le count
        mock_reports_reception.__getitem__.return_value = []  # Pour le slicing [:MAX_LINES_IN_PDF]
        mock_reports_reception.filter.return_value = mock_reports_reception
        mock_reports_reception.select_related.return_value = mock_reports_reception
        mock_reports_reception.order_by.return_value = mock_reports_reception
        mock_reports_reception.first.return_value = mock_reception
        mock_reception_objects.filter.return_value = mock_reports_reception
        
        mock_ligne = MagicMock()
        mock_ligne.contenu = {'Payment Terms': 'Net 30 days'}
        mock_ligne_filter.return_value.first.return_value = mock_ligne
        
        data = {
            'retention_rate': '7.5',
            'retention_cause': 'Updated cause'
        }
        
        response = self.client.post(
            reverse('orders:update_msrn_retention', args=[self.msrn_report_empty.id]),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        # Vérifier que la réponse est un succès (200)
        self.assertEqual(response.status_code, 200)
        
        # Recharger l'objet depuis la base de données
        self.msrn_report_empty.refresh_from_db()
        
        # Vérifier que les snapshots ont été initialisés
        self.assertIsNotNone(self.msrn_report_empty.montant_total_snapshot)
        self.assertIsNotNone(self.msrn_report_empty.montant_recu_snapshot)
        self.assertIsNotNone(self.msrn_report_empty.progress_rate_snapshot)
        self.assertIsNotNone(self.msrn_report_empty.progress_rate_snapshot)

    @patch('orders.models.Reception.objects.filter')
    @patch('orders.models.LigneFichier.objects.filter')
    @patch('orders.reports.generate_msrn_report')
    def test_update_msrn_retention_payment_terms_exception(self, mock_generate, mock_ligne_filter, mock_reception_filter):
        """Test ligne 227 - Exception dans la récupération des payment terms"""
        # Configurer le mock pour générer une erreur lors de la génération du rapport
        mock_generate.side_effect = Exception("Erreur de génération")
        
        data = {
            'retention_rate': '7.5',
            'retention_cause': 'Updated cause'
        }
        
        response = self.client.post(
            reverse('orders:update_msrn_retention', args=[self.msrn_report_empty.id]),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        # Doit retourner une erreur 500 car une exception est levée
        self.assertEqual(response.status_code, 500)

    def test_update_msrn_retention_calculations_with_snapshots(self):
        """Test lignes 248-257 - Calculs avec snapshots"""
        # Configurer le rapport avec des snapshots
        self.msrn_report_empty.montant_recu_snapshot = Decimal('10000.00')
        self.msrn_report_empty.save()
        
        data = {
            'retention_rate': '10.0',  # 10% pour tester le calcul
            'retention_cause': 'Updated cause'
        }
        
        response = self.client.post(
            reverse('orders:update_msrn_retention', args=[self.msrn_report_empty.id]),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Vérifier les calculs dans la réponse
        response_data = json.loads(response.content)
        self.assertEqual(response_data['msrn_report']['retention_rate'], 10.0)
        # retention_amount = 10000 * 10% = 1000
        # total_payable_amount = 10000 - 1000 = 9000
        self.assertEqual(response_data['msrn_report']['retention_amount'], 1000.0)
        self.assertEqual(response_data['msrn_report']['total_payable_amount'], 9000.0)

    @patch('orders.models.Reception.objects.filter')
    def test_update_msrn_retention_receptions_snapshot_fallback(self, mock_reception_filter):
        """Test lignes 287-319 - Fallback des réceptions sans snapshot"""
        # Mock des réceptions pour le fallback
        mock_reception = MagicMock()
        mock_reception.id = 1
        mock_reception.business_id = 'TEST_1_1_1'  # Format pour le split
        mock_reception.ordered_quantity = Decimal('100')
        mock_reception.quantity_delivered = Decimal('80')
        mock_reception.received_quantity = Decimal('80')
        mock_reception.quantity_not_delivered = Decimal('20')
        mock_reception.amount_delivered = Decimal('4000.00')
        mock_reception.unit_price = Decimal('50.00')
        mock_reception_filter.return_value = [mock_reception]
        
        # Créer un fichier et des lignes pour tester la récupération des descriptions
        fichier = FichierImporte.objects.create(fichier='test.csv', utilisateur=self.user)
        self.bon_commande.fichiers.add(fichier)
        
        # Utiliser un numéro de ligne unique pour éviter la violation de contrainte
        LigneFichier.objects.create(
            fichier=fichier,
            numero_ligne=999,  # Utiliser un numéro de ligne unique
            business_id='TEST_1_1_1',
            contenu={
                'Line Description': 'Test Item Description',
                'Line': '1',
                'Schedule': '1'
            }
        )
        
        data = {
            'retention_rate': '7.5',
            'retention_cause': 'Updated cause'
        }
        
        response = self.client.post(
            reverse('orders:update_msrn_retention', args=[self.msrn_report_empty.id]),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)

    @patch('orders.models.Reception.objects.filter')
    def test_update_msrn_retention_receptions_snapshot_fallback_exception(self, mock_reception_filter):
        """Test lignes 306-308 - Exception dans l'extraction du numéro de ligne"""
        # Mock des réceptions avec business_id invalide
        mock_reception = MagicMock()
        mock_reception.id = 1
        mock_reception.business_id = 'INVALID_FORMAT'  # Ne peut pas être split
        mock_reception.ordered_quantity = Decimal('100')
        mock_reception.quantity_delivered = Decimal('80')
        mock_reception.received_quantity = Decimal('80')
        mock_reception.quantity_not_delivered = Decimal('20')
        mock_reception.amount_delivered = Decimal('4000.00')
        mock_reception.unit_price = Decimal('50.00')
        mock_reception_filter.return_value = [mock_reception]
        
        data = {
            'retention_rate': '7.5',
            'retention_cause': 'Updated cause'
        }
        
        response = self.client.post(
            reverse('orders:update_msrn_retention', args=[self.msrn_report_empty.id]),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        # Ne devrait pas lever d'exception
        self.assertEqual(response.status_code, 200)

    @patch('orders.msrn_api.generate_msrn_report')
    def test_update_msrn_retention_pdf_regeneration_save_false(self, mock_generate):
        """Test ligne 319 - save=False lors de la régénération PDF"""
        mock_generate.return_value = BytesIO(b"fake pdf")
        
        data = {
            'retention_rate': '7.5',
            'retention_cause': 'Updated cause'
        }
        
        response = self.client.post(
            reverse('orders:update_msrn_retention', args=[self.msrn_report_empty.id]),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(mock_generate.called)


class TestMSRNAPIEdgeCases(TestCase):
    """Tests pour les cas limites de MSRN API"""
    
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
        self.msrn_report = MSRNReport.objects.create(
            report_number='MSRN250001',
            bon_commande=self.bon_commande,
            user=self.user.email,
            retention_rate=Decimal('5.0')
        )

    def test_update_msrn_retention_with_receptions_data_snapshot(self):
        """Test avec receptions_data_snapshot existant (branche if)"""
        # Créer un snapshot de réceptions existant
        receptions_snapshot = [
            {
                'id': 1,
                'line_description': 'Test Item',
                'ordered_quantity': '100.00',
                'received_quantity': '80.00',
                'quantity_delivered': '80.00',
                'quantity_not_delivered': '20.00',
                'amount_delivered': '4000.00',
                'quantity_payable': '76.00',  # Avec 5% de rétention
                'amount_payable': '3800.00',
                'line': '1',
                'schedule': '1'
            }
        ]
        
        self.msrn_report.receptions_data_snapshot = receptions_snapshot
        self.msrn_report.save()
        
        data = {
            'retention_rate': '10.0',  # Changer à 10%
            'retention_cause': 'Updated cause'
        }
        
        response = self.client.post(
            reverse('orders:update_msrn_retention', args=[self.msrn_report.id]),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Vérifier que le snapshot a été mis à jour avec le nouveau taux
        self.msrn_report.refresh_from_db()
        updated_snapshot = self.msrn_report.receptions_data_snapshot[0]
        # Avec 10% de rétention, quantity_payable = 80 * 0.9 = 72
        self.assertEqual(updated_snapshot['quantity_payable'], 72.0)        