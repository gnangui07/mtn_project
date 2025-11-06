# tests/test_penalty_report.py
import os
from decimal import Decimal
from datetime import datetime
from django.test import TestCase
from django.conf import settings
from orders.models import NumeroBonCommande
from orders.penalty_report import generate_penalty_report, _fmt_date, _fmt_amount


class TestPenaltyReport(TestCase):
    def setUp(self):
        # Créer un bon de commande
        self.bon_commande = NumeroBonCommande.objects.create(numero='TEST123')
        
        # Contexte de test
        self.context = {
            'po_number': 'TEST123',
            'supplier': 'Test Supplier',
            'currency': 'XOF',
            'creation_date': datetime(2024, 1, 15),
            'pip_end_date': datetime(2024, 6, 30),
            'actual_end_date': datetime(2024, 7, 15),
            'total_penalty_days': 15,
            'delay_part_mtn': 5,
            'delay_part_force_majeure': 3,
            'delay_part_vendor': 2,
            'po_amount': Decimal('1000000'),
            'penalty_rate': Decimal('0.30'),
            'project_coordinator': 'John Doe',
            'order_description': 'Test Project Description',
            'quotite_realisee': Decimal('100.00'),
            'quotite_non_realisee': Decimal('0.00'),
            'quotite_factor': Decimal('0.00'),
            'observation': 'Test observation text',
            'penalties_calculated': Decimal('6000'),
            'penalty_cap': Decimal('100000'),
            'penalties_due': Decimal('6000')
        }

    def test_generate_penalty_report_success(self):
        """Test la génération du rapport de pénalité avec succès"""
        pdf_buffer = generate_penalty_report(
            self.bon_commande,
            self.context,
            user_email='test@example.com'
        )
        
        # Vérifier que le PDF a été généré
        self.assertIsNotNone(pdf_buffer)
        self.assertGreater(len(pdf_buffer.getvalue()), 0)
        
        # Vérifier que c'est bien un PDF
        pdf_content = pdf_buffer.getvalue()
        self.assertTrue(pdf_content.startswith(b'%PDF'))

    def test_generate_penalty_report_no_user_email(self):
        """Test la génération sans email utilisateur"""
        pdf_buffer = generate_penalty_report(
            self.bon_commande,
            self.context
        )
        
        self.assertIsNotNone(pdf_buffer)
        self.assertGreater(len(pdf_buffer.getvalue()), 0)

    def test_generate_penalty_report_no_observation(self):
        """Test la génération sans observation"""
        context_no_obs = self.context.copy()
        context_no_obs['observation'] = ''
        
        pdf_buffer = generate_penalty_report(
            self.bon_commande,
            context_no_obs
        )
        
        self.assertIsNotNone(pdf_buffer)
        self.assertGreater(len(pdf_buffer.getvalue()), 0)

    def test_fmt_date(self):
        """Test le formatage des dates"""
        date = datetime(2024, 1, 15)
        self.assertEqual(_fmt_date(date), '15/01/2024')
        
        # Test avec None
        self.assertEqual(_fmt_date(None), 'N/A')

    def test_fmt_amount(self):
        """Test le formatage des montants"""
        # Test avec Decimal
        self.assertEqual(_fmt_amount(Decimal('1000000.50'), 'XOF'), '1 000 000,50 XOF')
        
        # Test avec float
        self.assertEqual(_fmt_amount(1000.50, 'XOF'), '1 000,50 XOF')
        
        # Test avec entier
        self.assertEqual(_fmt_amount(1000, 'XOF'), '1 000,00 XOF')
        
        # Test sans devise
        self.assertEqual(_fmt_amount(Decimal('1000.50')), '1 000,50')
        
        # Test avec valeur invalide
        self.assertEqual(_fmt_amount('invalid'), 'N/A')

    def test_logo_exists(self):
        """Test que le logo existe"""
        logo_path = os.path.join(settings.BASE_DIR, 'static', 'logo_mtn.jpeg')
        self.assertTrue(os.path.exists(logo_path))