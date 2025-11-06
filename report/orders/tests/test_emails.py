# tests/test_emails.py
import pytest
from unittest.mock import Mock, patch
from django.core.mail import EmailMultiAlternatives
from orders.emails import send_msrn_notification, send_penalty_notification, send_test_email


class TestEmails:
    """Tests pour les fonctions d'envoi d'emails"""

    @pytest.fixture
    def msrn_report(self):
        report = Mock()
        report.report_number = 'MSRN250001'
        report.bon_commande = Mock()
        report.bon_commande.numero = 'TEST123'
        report.bon_commande.get_supplier.return_value = 'Test Supplier'
        report.bon_commande.get_currency.return_value = 'XOF'
        report.bon_commande.montant_total.return_value = 1000000
        report.bon_commande.montant_recu.return_value = 800000
        report.progress_rate_snapshot = 80.0
        report.retention_rate = 5.0
        report.retention_cause = 'Test cause'
        report.user = 'user@example.com'
        report.created_at = '2024-03-15 10:00:00'
        return report

    @patch('orders.emails.settings')
    @patch('orders.emails.User.objects.filter')
    @patch('orders.emails.render_to_string')
    @patch('orders.emails.EmailMultiAlternatives')
    def test_send_msrn_notification_success(self, mock_email_class, mock_render, mock_user_filter, mock_settings, msrn_report):
        """Test l'envoi réussi de notification MSRN"""
        mock_settings.ENABLE_EMAIL_NOTIFICATIONS = True
        mock_settings.DEFAULT_FROM_EMAIL = 'noreply@example.com'
        mock_settings.SITE_URL = 'http://localhost:8000'

        user = Mock()
        user.email = 'admin@example.com'
        mock_queryset = Mock()
        mock_queryset.exists.return_value = True
        mock_queryset.__iter__ = Mock(return_value=iter([user]))
        mock_user_filter.return_value.exclude.return_value = mock_queryset

        mock_render.return_value = '<html>Email content</html>'

        mock_email = Mock()
        mock_email_class.return_value = mock_email

        result = send_msrn_notification(msrn_report)

        assert result is True
        mock_email_class.assert_called_once()
        mock_email.attach_alternative.assert_called_once_with('<html>Email content</html>', 'text/html')
        mock_email.send.assert_called_once_with(fail_silently=False)

    @patch('orders.emails.settings')
    def test_send_msrn_notification_disabled(self, mock_settings, msrn_report):
        """Test avec notifications désactivées"""
        mock_settings.ENABLE_EMAIL_NOTIFICATIONS = False

        result = send_msrn_notification(msrn_report)

        assert result is False

    @patch('orders.emails.settings')
    @patch('orders.emails.User.objects.filter')
    def test_send_msrn_notification_no_superusers(self, mock_user_filter, mock_settings, msrn_report):
        """Test sans superusers disponibles"""
        from unittest.mock import Mock
        mock_settings.ENABLE_EMAIL_NOTIFICATIONS = True
        mock_queryset = Mock()
        mock_queryset.exists.return_value = False
        mock_user_filter.return_value.exclude.return_value = mock_queryset

        result = send_msrn_notification(msrn_report)

        assert result is False

    @patch('orders.emails.settings')
    @patch('orders.emails.User.objects.filter')
    @patch('orders.emails.render_to_string')
    @patch('orders.emails.EmailMultiAlternatives')
    def test_send_msrn_notification_with_pdf_attachment(self, mock_email_class, mock_render, mock_user_filter, mock_settings, msrn_report):
        """Test avec attachment PDF"""
        mock_settings.ENABLE_EMAIL_NOTIFICATIONS = True
        mock_settings.DEFAULT_FROM_EMAIL = 'noreply@example.com'
        mock_settings.SITE_URL = 'http://localhost:8000'

        user = Mock()
        user.email = 'admin@example.com'
        mock_queryset = Mock()
        mock_queryset.exists.return_value = True
        mock_queryset.__iter__ = Mock(return_value=iter([user]))
        mock_user_filter.return_value.exclude.return_value = mock_queryset

        mock_render.return_value = '<html>Email content</html>'

        # Mock PDF file attachment
        msrn_report.pdf_file = Mock()
        msrn_report.pdf_file.path = '/path/to/pdf.pdf'

        mock_email = Mock()
        mock_email_class.return_value = mock_email

        with patch('orders.emails.open') as mock_open:
            mock_file = Mock()
            mock_open.return_value.__enter__.return_value = mock_file
            mock_file.read.return_value = b'PDF content'

            result = send_msrn_notification(msrn_report)

        assert result is True
        mock_email.attach.assert_called_once()

    @patch('orders.emails.settings')
    @patch('orders.emails.User.objects.filter')
    @patch('orders.emails.EmailMultiAlternatives')
    def test_send_penalty_notification_success(self, mock_email_class, mock_user_filter, mock_settings):
        """Test l'envoi réussi de notification de pénalité"""
        mock_settings.ENABLE_EMAIL_NOTIFICATIONS = True
        mock_settings.DEFAULT_FROM_EMAIL = 'noreply@example.com'

        user = Mock()
        user.email = 'admin@example.com'
        mock_queryset = Mock()
        mock_queryset.exists.return_value = True
        mock_queryset.__iter__ = Mock(return_value=iter([user]))
        mock_user_filter.return_value.exclude.return_value = mock_queryset

        bon_commande = Mock()
        bon_commande.numero = 'TEST123'
        bon_commande.get_supplier.return_value = 'Test Supplier'

        pdf_buffer = Mock()
        pdf_buffer.read.return_value = b'%PDF-1.4'

        result = send_penalty_notification(bon_commande, pdf_buffer, 'user@example.com', 'penalty')

        assert result is True
        mock_email_class.assert_called_once()
        mock_email_class.return_value.attach.assert_called_once()
        mock_email_class.return_value.send.assert_called_once_with(fail_silently=False)

    @patch('orders.emails.settings')
    @patch('orders.emails.User.objects.filter')
    def test_send_penalty_notification_fallback_to_user(self, mock_user_filter, mock_settings):
        """Test fallback sur l'email utilisateur"""
        mock_settings.ENABLE_EMAIL_NOTIFICATIONS = True
        mock_settings.DEFAULT_FROM_EMAIL = 'noreply@example.com'

        # Aucun superuser
        mock_queryset = Mock()
        mock_queryset.exists.return_value = False
        mock_user_filter.return_value.exclude.return_value = mock_queryset

        bon_commande = Mock()
        bon_commande.numero = 'TEST123'
        bon_commande.get_supplier.return_value = 'Test Supplier'

        pdf_buffer = Mock()
        pdf_buffer.read.return_value = b'%PDF-1.4'

        # L'utilisateur a un email valide
        result = send_penalty_notification(bon_commande, pdf_buffer, 'user@example.com', 'penalty')

        assert result is True

    @patch('orders.emails.settings')
    @patch('orders.emails.User.objects.filter')
    def test_send_penalty_notification_no_recipients(self, mock_user_filter, mock_settings):
        """Test sans destinataires valides"""
        mock_settings.ENABLE_EMAIL_NOTIFICATIONS = True

        # Aucun superuser et utilisateur sans email
        mock_user_filter.return_value.exclude.return_value = []

        bon_commande = Mock()
        pdf_buffer = Mock()

        result = send_penalty_notification(bon_commande, pdf_buffer, None, 'penalty')

        assert result is False

    @patch('orders.emails.send_mail')
    def test_send_test_email_success(self, mock_send_mail):
        """Test l'envoi réussi d'email de test"""
        mock_send_mail.return_value = 1

        result = send_test_email('test@example.com')

        assert result is True
        mock_send_mail.assert_called_once()

    @patch('orders.emails.send_mail')
    def test_send_test_email_failure(self, mock_send_mail):
        """Test l'échec d'envoi d'email de test"""
        mock_send_mail.side_effect = Exception('SMTP error')

        result = send_test_email('test@example.com')

        assert result is False