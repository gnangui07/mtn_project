# tests/test_delay_evaluation_report.py
import pytest
from decimal import Decimal
from datetime import datetime
from unittest.mock import Mock, patch
from orders.delay_evaluation_report import generate_delay_evaluation_report, _fmt_date, _fmt_amount


class TestDelayEvaluationReport:
    """Tests pour la génération du PDF d'évaluation des délais"""

    def test_fmt_date(self):
        """Test le formatage des dates"""
        date_obj = datetime(2024, 3, 15)
        result = _fmt_date(date_obj)
        assert result == "15/03/2024"

    def test_fmt_date_none(self):
        """Test le formatage avec date None"""
        result = _fmt_date(None)
        assert result == "N/A"

    def test_fmt_amount(self):
        """Test le formatage des montants"""
        result = _fmt_amount(Decimal('1500000.50'), 'XOF')
        assert result == "1 500 000,50 XOF"

    def test_fmt_amount_no_currency(self):
        """Test le formatage sans devise"""
        result = _fmt_amount(Decimal('1500000.50'))
        assert result == "1 500 000,50"

    def test_fmt_amount_none(self):
        """Test le formatage avec montant None"""
        result = _fmt_amount(None, 'XOF')
        assert result == "N/A"

    def test_fmt_amount_integer(self):
        """Test le formatage avec entier"""
        result = _fmt_amount(1500000, 'XOF')
        assert result == "1 500 000,00 XOF"

    def test_fmt_amount_string(self):
        """Test le formatage avec chaîne"""
        result = _fmt_amount('1500000.75', 'XOF')
        assert result == "1 500 000,75 XOF"

    @patch('orders.delay_evaluation_report.settings')
    @patch('orders.delay_evaluation_report.BytesIO')
    @patch('orders.delay_evaluation_report.SimpleDocTemplate')
    def test_generate_delay_evaluation_report(self, mock_doc_template, mock_bytes_io, mock_settings):
        """Test la génération complète du PDF"""
        mock_settings.BASE_DIR = '/test/path'
        mock_buffer = Mock()
        mock_bytes_io.return_value = mock_buffer
        mock_doc = Mock()
        mock_doc_template.return_value = mock_doc

        bon_commande = Mock()
        bon_commande.numero = 'TEST123'

        context = {
            'po_number': 'TEST123',
            'supplier': 'Test Supplier',
            'currency': 'XOF',
            'po_amount': Decimal('1000000.00'),
            'creation_date': datetime(2024, 1, 1),
            'pip_end_date': datetime(2024, 2, 1),
            'actual_end_date': datetime(2024, 2, 15),
            'total_delay_days': 14,
            'project_manager': 'John Doe',
            'order_description': 'Test Equipment',
            'delay_part_mtn': 5,
            'delay_part_vendor': 7,
            'delay_part_force_majeure': 2,
            'comment_mtn': 'Retard MTN',
            'comment_vendor': 'Retard fournisseur',
            'comment_force_majeure': 'Force majeure',
            'evaluation_date': datetime(2024, 3, 1),
            'evaluator_name': 'Jane Doe',
            'total_score': 41,
            'final_rating': Decimal('8.20'),
            'criteria_details': [
                {
                    'key': 'delivery_compliance',
                    'label': 'Conformité livraison',
                    'score': 9,
                    'description': 'Très conforme'
                }
            ],
            'observation': 'Observation test'
        }

        with patch('orders.delay_evaluation_report.Image'):
            with patch('orders.delay_evaluation_report._ensure_styles'):
                result = generate_delay_evaluation_report(bon_commande, context, 'test@example.com')

        assert result == mock_buffer
        mock_doc.build.assert_called_once()
        mock_buffer.seek.assert_called_once_with(0)

    @patch('orders.delay_evaluation_report.settings')
    @patch('orders.delay_evaluation_report.BytesIO')
    @patch('orders.delay_evaluation_report.SimpleDocTemplate')
    def test_generate_delay_evaluation_report_minimal_context(self, mock_doc_template, mock_bytes_io, mock_settings):
        """Test avec contexte minimal"""
        mock_settings.BASE_DIR = '/test/path'
        mock_buffer = Mock()
        mock_bytes_io.return_value = mock_buffer
        mock_doc = Mock()
        mock_doc_template.return_value = mock_doc

        bon_commande = Mock()
        bon_commande.numero = 'TEST123'

        context = {
            'po_number': 'TEST123',
            'supplier': 'Test Supplier',
            'currency': 'XOF',
            'po_amount': Decimal('1000000.00'),
            'creation_date': None,
            'pip_end_date': None,
            'actual_end_date': None,
            'total_delay_days': 0,
            'project_manager': 'N/A',
            'order_description': 'N/A',
            'delay_part_mtn': 0,
            'delay_part_vendor': 0,
            'delay_part_force_majeure': 0,
            'comment_mtn': '',
            'comment_vendor': '',
            'comment_force_majeure': '',
            'evaluation_date': None,
            'evaluator_name': 'N/A',
            'total_score': 0,
            'final_rating': Decimal('0.00'),
            'criteria_details': [],
            'observation': ''
        }

        with patch('orders.delay_evaluation_report.Image'):
            with patch('orders.delay_evaluation_report._ensure_styles'):
                result = generate_delay_evaluation_report(bon_commande, context)

        assert result is not None

    @patch('orders.delay_evaluation_report.settings')
    @patch('orders.delay_evaluation_report.Path.exists')
    def test_generate_delay_evaluation_report_with_logo(self, mock_exists, mock_settings):
        """Test avec logo"""
        mock_exists.return_value = True
        mock_settings.BASE_DIR = '/test/path'

        bon_commande = Mock()
        context = {
            'po_number': 'TEST123',
            'supplier': 'Test Supplier',
            'currency': 'XOF',
            'po_amount': Decimal('1000000.00'),
            'creation_date': None,
            'pip_end_date': None,
            'actual_end_date': None,
            'total_delay_days': 0,
            'project_manager': 'N/A',
            'order_description': 'N/A',
            'delay_part_mtn': 0,
            'delay_part_vendor': 0,
            'delay_part_force_majeure': 0,
            'comment_mtn': '',
            'comment_vendor': '',
            'comment_force_majeure': '',
            'evaluation_date': None,
            'evaluator_name': 'N/A',
            'total_score': 0,
            'final_rating': Decimal('0.00'),
            'criteria_details': [],
            'observation': ''
        }

        with patch('orders.delay_evaluation_report.Image') as mock_image:
            with patch('orders.delay_evaluation_report.SimpleDocTemplate'):
                with patch('orders.delay_evaluation_report.BytesIO'):
                    generate_delay_evaluation_report(bon_commande, context)
                    
                    # Verify logo image was processed
                    mock_image.assert_called_once()