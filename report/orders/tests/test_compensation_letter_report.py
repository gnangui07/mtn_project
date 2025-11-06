# tests/test_compensation_letter_report.py
import pytest
from decimal import Decimal
from datetime import datetime
from io import BytesIO
from unittest.mock import Mock, patch
from reportlab.lib.pagesizes import letter

from orders.compensation_letter_report import (
    generate_compensation_letter,
    _fmt_date,
    _fmt_amount,
    MODERN_BLUE
)


class TestCompensationLetterReport:
    """Tests pour le module compensation_letter_report.py"""

    def test_fmt_date_with_datetime(self):
        """Test le formatage des dates avec objet datetime"""
        test_date = datetime(2024, 3, 15)
        result = _fmt_date(test_date)
        assert result == "15/03/2024"

    def test_fmt_date_with_string(self):
        """Test le formatage des dates avec chaîne de caractères"""
        result = _fmt_date("2024-03-15")
        assert result == "15/03/2024"

    def test_fmt_date_with_none(self):
        """Test le formatage avec valeur None"""
        result = _fmt_date(None)
        assert result == "N/A"

    def test_fmt_date_with_invalid_string(self):
        """Test le formatage avec chaîne invalide"""
        result = _fmt_date("invalid-date")
        assert result == "invalid-date"

    def test_fmt_amount_with_decimal(self):
        """Test le formatage des montants avec Decimal"""
        result = _fmt_amount(Decimal('1500000.50'), 'XOF')
        assert result == "1 500 000 XOF"

    def test_fmt_amount_with_integer(self):
        """Test le formatage des montants avec entier"""
        result = _fmt_amount(1500000, 'XOF')
        assert result == "1 500 000 XOF"

    def test_fmt_amount_with_float(self):
        """Test le formatage des montants avec float"""
        result = _fmt_amount(1500000.0, 'XOF')
        assert result == "1 500 000 XOF"

    def test_fmt_amount_with_none(self):
        """Test le formatage avec valeur None"""
        result = _fmt_amount(None, 'XOF')
        assert result == "N/A"

    def test_fmt_amount_with_string(self):
        """Test le formatage avec chaîne de caractères"""
        result = _fmt_amount("1500000", 'XOF')
        assert result == "1 500 000 XOF"

    def test_fmt_amount_without_currency(self):
        """Test le formatage sans devise"""
        result = _fmt_amount(Decimal('1500000'))
        assert result == "1 500 000"

    @patch('orders.compensation_letter_report.settings')
    @patch('orders.compensation_letter_report.BytesIO')
    @patch('orders.compensation_letter_report.SimpleDocTemplate')
    def test_generate_compensation_letter_success(
        self, mock_doc_template, mock_bytes_io, mock_settings
    ):
        """Test la génération réussie de la lettre de compensation"""
        # Setup mocks
        from unittest.mock import MagicMock
        mock_buffer = MagicMock()
        mock_bytes_io.return_value = mock_buffer
        
        mock_doc = Mock()
        mock_doc_template.return_value = mock_doc
        
        mock_settings.BASE_DIR = '/test/path'
        
        # Mock bon_commande and context
        bon_commande = Mock()
        bon_commande.numero = 'TEST123'
        
        context = {
            'po_number': 'PO123',
            'supplier': 'Test Supplier',
            'order_description': 'Test Equipment',
            'pip_end_date': datetime(2024, 1, 15),
            'actual_end_date': datetime(2024, 2, 15),
            'total_penalty_days': 31,
            'delay_part_vendor': 20,
            'penalty_rate': Decimal('0.30'),
            'penalties_calculated': Decimal('1500000'),
            'currency': 'XOF'
        }

        # Call the function
        result = generate_compensation_letter(bon_commande, context, 'test@example.com')

        # Assertions
        assert result == mock_buffer
        mock_bytes_io.assert_called_once()
        mock_doc_template.assert_called_once()
        mock_doc.build.assert_called_once()
        mock_buffer.seek.assert_called_once_with(0)

    @patch('orders.compensation_letter_report.settings')
    @patch('orders.compensation_letter_report.os.path.exists')
    def test_generate_compensation_letter_with_logo(
        self, mock_exists, mock_settings
    ):
        """Test la génération avec logo"""
        mock_exists.return_value = True
        mock_settings.BASE_DIR = '/test/path'
        
        bon_commande = Mock()
        context = {
            'po_number': 'PO123',
            'supplier': 'Test Supplier',
            'order_description': 'Test',
            'pip_end_date': datetime(2024, 1, 15),
            'actual_end_date': datetime(2024, 2, 15),
            'total_penalty_days': 31,
            'delay_part_vendor': 20,
            'penalty_rate': Decimal('0.30'),
            'penalties_calculated': Decimal('1500000'),
            'currency': 'XOF'
        }

        with patch('orders.compensation_letter_report.Image') as mock_image:
            with patch('orders.compensation_letter_report.SimpleDocTemplate'):
                with patch('orders.compensation_letter_report.BytesIO'):
                    generate_compensation_letter(bon_commande, context)
                    
                    # Verify logo image was processed
                    mock_image.assert_called_once()

    def test_generate_compensation_letter_minimal_context(self):
        """Test avec un contexte minimal"""
        bon_commande = Mock()
        context = {
            'po_number': 'PO123',
            'supplier': 'Test Supplier',
            'order_description': 'Test',
        }

        with patch('orders.compensation_letter_report.SimpleDocTemplate'):
            with patch('orders.compensation_letter_report.BytesIO'):
                result = generate_compensation_letter(bon_commande, context)
                
                assert result is not None

    def test_modern_blue_color(self):
        """Test la couleur MODERN_BLUE"""
        assert MODERN_BLUE.hexval() == '0x1f5c99'