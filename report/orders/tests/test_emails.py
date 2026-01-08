# tests/test_emails.py
import pytest
from decimal import Decimal
from unittest.mock import patch, Mock, MagicMock, mock_open
from django.test import TestCase
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.contrib.auth import get_user_model
from django.conf import settings
from orders.emails import (
    send_msrn_notification, send_signature_reminder, 
    find_user_email_by_name, send_penalty_notification
)

User = get_user_model()
from io import BytesIO
from datetime import datetime
from decimal import Decimal

from orders.emails import send_msrn_notification, send_penalty_notification, send_test_email, find_user_email_by_name, send_signature_reminder


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

    @patch('orders.emails.settings')
    @patch('orders.emails.User.objects.filter')
    @patch('orders.emails.render_to_string')
    @patch('orders.emails.EmailMultiAlternatives')
    def test_send_msrn_notification_created_at_fallback_and_cc(self, mock_email_class, mock_render, mock_user_filter, mock_settings, msrn_report):
        """Couvre le fallback created_at et l'ajout en CC de l'émetteur"""
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

        # Forcer created_at à un objet qui ne supporte pas strftime -> fallback
        class WeirdDate:
            pass
        msrn_report.created_at = WeirdDate()

        mock_email = Mock()
        mock_email_class.return_value = mock_email

        result = send_msrn_notification(msrn_report)
        assert result is True
        # Vérifier que CC a été fourni (l'émetteur est distinct du superuser)
        args, kwargs = mock_email_class.call_args
        assert 'cc' in kwargs and kwargs['cc'] is not None

    @patch('orders.emails.settings')
    @patch('orders.emails.User.objects.filter')
    @patch('orders.emails.render_to_string')
    @patch('orders.emails.EmailMultiAlternatives')
    def test_send_msrn_notification_send_raises_returns_false(self, mock_email_class, mock_render, mock_user_filter, mock_settings, msrn_report):
        """Si l'envoi lève une exception, la fonction retourne False (branche except)"""
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
        mock_email.send.side_effect = Exception('smtp down')
        mock_email_class.return_value = mock_email

        result = send_msrn_notification(msrn_report)
        assert result is False

    @patch('orders.emails.settings')
    @patch('orders.emails.User.objects.filter')
    @patch('orders.emails.EmailMultiAlternatives')
    def test_send_penalty_notification_attach_warning(self, mock_email_class, mock_user_filter, mock_settings):
        """L'échec de lecture de la pièce jointe déclenche un warning mais n'empêche pas l'envoi"""
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
        pdf_buffer.seek.return_value = None
        pdf_buffer.read.side_effect = Exception('read fail')

        result = send_penalty_notification(bon_commande, pdf_buffer, 'user@example.com', 'penalty')
        assert result is True
        mock_email_class.return_value.send.assert_called_once_with(fail_silently=False)


class TestFindUserEmailByName(TestCase):
    """Test recherche email par nom"""
    
    def setUp(self):
        self.user1 = User.objects.create_user(
            email='john.doe@example.com',
            password='pass123',
            first_name='John',
            last_name='Doe',
            is_active=True
        )
        self.user2 = User.objects.create_user(
            email='marc.dupont@example.com',
            password='pass123',
            first_name='Marc',
            last_name='Dupont',
            is_active=True
        )
        self.user3 = User.objects.create_user(
            email='jm.konin@example.com',
            password='pass123',
            first_name='JM',
            last_name='Konin',
            is_active=True
        )
        self.user4 = User.objects.create_user(
            email='jean.marc@example.com',
            password='pass123',
            first_name='Jean Marc',
            last_name='Martin',
            is_active=True
        )
        # Utilisateur inactif
        self.user5 = User.objects.create_user(
            email='inactive@example.com',
            password='pass123',
            first_name='Inactive',
            last_name='User',
            is_active=False
        )
    
    def test_find_user_exact_match(self):
        """Test correspondance exacte"""
        email = find_user_email_by_name('John Doe')
        self.assertEqual(email, 'john.doe@example.com')
        
        email = find_user_email_by_name('Doe John')
        self.assertEqual(email, 'john.doe@example.com')
    
    def test_find_user_partial_match(self):
        """Test correspondance partielle"""
        email = find_user_email_by_name('John DOE Test')
        self.assertEqual(email, 'john.doe@example.com')
        
        email = find_user_email_by_name('Test Marc Dupont')
        self.assertEqual(email, 'marc.dupont@example.com')
    
    def test_find_user_initials_match(self):
        """Test correspondance avec initiales"""
        # JM Konin -> JM = Jean Marc
        email = find_user_email_by_name('JEAN MARC KONIN')
        self.assertEqual(email, 'jm.konin@example.com')
    
    def test_find_user_composed_first_name(self):
        """Test prénom composé avec initiales"""
        # Jean Marc Martin -> JM
        email = find_user_email_by_name('JM Martin')
        self.assertEqual(email, 'jean.marc@example.com')
    
    def test_find_user_with_hyphens(self):
        """Test noms avec tirets"""
        user = User.objects.create_user(
            email='jean-marc@example.com',
            password='pass123',
            first_name='Jean-Marc',
            last_name='Test',
            is_active=True
        )
        
        email = find_user_email_by_name('JEAN MARC TEST')
        self.assertEqual(email, 'jean-marc@example.com')
        
        email = find_user_email_by_name('Jean-Marc Test')
        self.assertEqual(email, 'jean-marc@example.com')
    
    def test_find_user_case_insensitive(self):
        """Test insensibilité à la casse"""
        email = find_user_email_by_name('john doe')
        self.assertEqual(email, 'john.doe@example.com')
        
        email = find_user_email_by_name('JOHN DOE')
        self.assertEqual(email, 'john.doe@example.com')
    
    def test_find_user_multiple_spaces(self):
        """Test gestion espaces multiples"""
        email = find_user_email_by_name('John   Doe')
        self.assertEqual(email, 'john.doe@example.com')
    
    def test_find_user_not_found(self):
        """Test utilisateur non trouvé"""
        email = find_user_email_by_name('Unknown User')
        self.assertIsNone(email)
    
    def test_find_user_empty_input(self):
        """Test entrée vide"""
        email = find_user_email_by_name('')
        self.assertIsNone(email)
        
        email = find_user_email_by_name(None)
        self.assertIsNone(email)
    
    def test_find_user_inactive_not_returned(self):
        """Test utilisateur inactif non retourné"""
        email = find_user_email_by_name('Inactive User')
        self.assertIsNone(email)
    
    def test_find_user_no_email(self):
        """Test utilisateur non trouvé (ex: sans email)"""
        # On teste que find_user_email_by_name retourne None si l'email n'est pas trouvé
        # ou si aucun utilisateur ne correspond
        email = find_user_email_by_name('No Match')
        self.assertIsNone(email)
    
    @patch('orders.emails.logger')
    def test_find_user_logging(self, mock_logger):
        """Test logging quand non trouvé"""
        find_user_email_by_name('Unknown User')
        mock_logger.warning.assert_called_once()


class TestSendSignatureReminder(TestCase):
    """Test envoi rappel de signature"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='user@example.com',
            password='pass123',
            is_superuser=True,
            is_active=True
        )
        self.pending_reports = [
            {
                'po_number': 'PO001',
                'report_number': 'MSRN-001',
                'deadline': datetime(2024, 1, 20, 10, 0, 0)
            },
            {
                'po_number': 'PO002',
                'report_number': 'MSRN-002',
                'deadline': datetime(2024, 1, 21, 15, 0, 0)
            }
        ]
    
    @patch('orders.emails.render_to_string')
    @patch('orders.emails.EmailMultiAlternatives')
    def test_send_signature_reminder_success(self, mock_email_class, mock_render):
        """Test envoi réussi rappel"""
        mock_render.return_value = '<html>Reminder HTML</html>'
        mock_email = Mock()
        mock_email_class.return_value = mock_email
        
        result = send_signature_reminder(
            'John Doe',
            'john.doe@example.com',
            self.pending_reports
        )
        
        self.assertTrue(result)
        mock_email.send.assert_called_once()
    
    def test_send_signature_reminder_no_email(self):
        """Test sans email"""
        result = send_signature_reminder(
            'John Doe',
            None,
            self.pending_reports
        )
        
        self.assertFalse(result)
    
    def test_send_signature_reminder_no_reports(self):
        """Test sans rapports"""
        result = send_signature_reminder(
            'John Doe',
            'john.doe@example.com',
            []
        )
        
        self.assertFalse(result)
    
    @patch('orders.emails.render_to_string')
    @patch('orders.emails.EmailMultiAlternatives')
    def test_send_signature_reminder_with_cc(self, mock_email_class, mock_render):
        """Test avec CC aux superusers"""
        mock_render.return_value = '<html>Reminder HTML</html>'
        mock_email = Mock()
        mock_email_class.return_value = mock_email
        
        result = send_signature_reminder(
            'John Doe',
            'john.doe@example.com',
            self.pending_reports
        )
        
        self.assertTrue(result)
        # Vérifie la présence des superusers en CC
        args, kwargs = mock_email_class.call_args
        self.assertIn('cc', kwargs)
        self.assertIn('user@example.com', kwargs['cc'])
    
    @patch('orders.emails.render_to_string')
    @patch('orders.emails.EmailMultiAlternatives')
    def test_send_signature_reminder_template_error(self, mock_email_class, mock_render):
        """Test erreur template HTML"""
        mock_render.side_effect = Exception('Template error')
        mock_email = Mock()
        mock_email_class.return_value = mock_email
        
        result = send_signature_reminder(
            'John Doe',
            'john.doe@example.com',
            self.pending_reports
        )
        
        self.assertTrue(result)
        # Vérifie que le fallback texte est utilisé
        args, kwargs = mock_email_class.call_args
        self.assertIn('Bonjour John Doe', kwargs['body'])
    
    @patch('orders.emails.render_to_string')
    @patch('orders.emails.EmailMultiAlternatives')
    def test_send_signature_reminder_send_error(self, mock_email_class, mock_render):
        """Test erreur envoi email"""
        mock_render.return_value = '<html>Reminder HTML</html>'
        mock_email = Mock()
        mock_email.send.side_effect = Exception('SMTP error')
        mock_email_class.return_value = mock_email
        
        with patch('orders.emails.logger') as mock_logger:
            result = send_signature_reminder(
                'John Doe',
                'john.doe@example.com',
                self.pending_reports
            )
        
        self.assertFalse(result)
        mock_logger.error.assert_called_once()
    
    @patch('orders.emails.settings')
    @patch('orders.emails.render_to_string')
    @patch('orders.emails.EmailMultiAlternatives')
    def test_send_signature_reminder_site_url(self, mock_email_class, mock_render, mock_settings):
        """Test URL du site dans le contexte"""
        mock_settings.SITE_URL = 'https://msrn.example.com'
        mock_render.return_value = '<html>Reminder HTML</html>'
        mock_email = Mock()
        mock_email_class.return_value = mock_email
        
        result = send_signature_reminder(
            'John Doe',
            'john.doe@example.com',
            self.pending_reports
        )
        
        self.assertTrue(result)
        # Vérifie que l'URL du site est dans le contexte du template
        mock_render.assert_called_once()
        context = mock_render.call_args[0][1]
        self.assertEqual(context['site_url'], 'https://msrn.example.com')
    
    @patch('orders.emails.render_to_string')
    @patch('orders.emails.EmailMultiAlternatives')
    def test_send_signature_reminder_text_content(self, mock_email_class, mock_render):
        """Test contenu texte avec plusieurs rapports"""
        mock_render.return_value = '<html>Reminder HTML</html>'
        mock_email = Mock()
        mock_email_class.return_value = mock_email
        
        result = send_signature_reminder(
            'John Doe',
            'john.doe@example.com',
            self.pending_reports
        )
        
        self.assertTrue(result)
        # Vérise le contenu texte
        args, kwargs = mock_email_class.call_args
        body = kwargs['body']
        self.assertIn('2 rapport(s) MSRN en attente', body)
        self.assertIn('PO001 (MSRN: MSRN-001', body)
        self.assertIn('PO002 (MSRN: MSRN-002', body)


class TestMSRNNotificationWithPDF(TestCase):
    """Test notification MSRN avec pièce jointe PDF"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='John',
            last_name='Doe'
        )
        self.superuser = User.objects.create_user(
            email='admin@example.com',
            password='adminpass123',
            is_superuser=True,
            is_active=True
        )
        self.user.is_active = True
        self.user.save()
    
    @patch('orders.emails.settings')
    @patch('orders.emails.User.objects.filter')
    @patch('orders.emails.render_to_string')
    @patch('orders.emails.EmailMultiAlternatives')
    def test_send_msrn_notification_with_pdf(self, mock_email_class, mock_render, mock_user_filter, mock_settings):
        """Test envoi avec pièce jointe PDF"""
        mock_settings.ENABLE_EMAIL_NOTIFICATIONS = True
        mock_settings.DEFAULT_FROM_EMAIL = 'noreply@example.com'
        mock_settings.SITE_URL = 'http://localhost:8000'
        
        user = Mock()
        user.email = 'admin@example.com'
        mock_queryset = Mock()
        mock_queryset.exists.return_value = True
        mock_queryset.__iter__ = Mock(return_value=iter([user]))
        mock_user_filter.return_value.exclude.return_value = mock_queryset


        # Créer un rapport mock avec PDF
        report = Mock()
        report.report_number = 'MSRN-001'
        report.bon_commande = Mock()
        report.bon_commande.numero = 'PO001'
        report.bon_commande.get_supplier.return_value = 'SUPPLIER1'
        report.bon_commande.get_currency.return_value = 'XOF'
        report.bon_commande.montant_total.return_value = 1000000
        report.bon_commande.montant_recu.return_value = 800000
        report.progress_rate_snapshot = 80.0
        report.retention_rate = 5.0
        report.retention_cause = 'Test cause'
        report.user = 'test@example.com'
        report.created_at = datetime(2024, 1, 15, 10, 30, 0)
        
        # Mock PDF file
        pdf_file = Mock()
        pdf_file.path = '/path/to/file.pdf'
        pdf_file.name = 'test.pdf'
        setattr(report, 'pdf_file', pdf_file)
        
        mock_render.return_value = '<html>Test HTML</html>'
        mock_email = Mock()
        mock_email_class.return_value = mock_email
        
        with patch('builtins.open', mock_open(read_data=b'PDF content')):
            result = send_msrn_notification(report)
        
        self.assertTrue(result)
        mock_email.attach.assert_called_once()
    
    @patch('orders.emails.settings')
    @patch('orders.emails.User.objects.filter')
    @patch('orders.emails.render_to_string')
    @patch('orders.emails.EmailMultiAlternatives')
    def test_send_msrn_notification_created_at_formatting(self, mock_email_class, mock_render, mock_user_filter, mock_settings):
        """Test formatage de created_at"""
        mock_settings.ENABLE_EMAIL_NOTIFICATIONS = True
        mock_settings.DEFAULT_FROM_EMAIL = 'noreply@example.com'
        mock_settings.SITE_URL = 'http://localhost:8000'

        user = Mock()
        user.email = 'admin@example.com'
        mock_queryset = Mock()
        mock_queryset.exists.return_value = True
        mock_queryset.__iter__ = Mock(return_value=iter([user]))
        mock_user_filter.return_value.exclude.return_value = mock_queryset


        report = Mock()
        report.report_number = 'MSRN-001'
        report.bon_commande = Mock()
        report.bon_commande.numero = 'PO001'
        report.bon_commande.get_supplier.return_value = 'SUPPLIER1'
        report.bon_commande.get_currency.return_value = 'XOF'
        report.bon_commande.montant_total.return_value = 1000000
        report.bon_commande.montant_recu.return_value = 800000
        report.progress_rate_snapshot = 80.0
        report.retention_rate = 5.0
        report.retention_cause = 'Test cause'
        report.user = 'test@example.com'
        report.created_at = datetime(2024, 1, 15, 10, 30, 0)
        
        mock_render.return_value = '<html>Test HTML</html>'
        mock_email = Mock()
        mock_email_class.return_value = mock_email
        
        result = send_msrn_notification(report)
        
        self.assertTrue(result)
        # Vérifie que le contenu texte contient la date formatée
        args, kwargs = mock_email_class.call_args
        self.assertIn('2024-01-15 10:30:00', kwargs['body'])
    
    @patch('orders.emails.settings')
    @patch('orders.emails.User.objects.filter')
    @patch('orders.emails.render_to_string')
    @patch('orders.emails.EmailMultiAlternatives')
    def test_send_msrn_notification_created_at_invalid(self, mock_email_class, mock_render, mock_user_filter, mock_settings):
        """Test avec created_at invalide"""
        mock_settings.ENABLE_EMAIL_NOTIFICATIONS = True
        mock_settings.DEFAULT_FROM_EMAIL = 'noreply@example.com'
        mock_settings.SITE_URL = 'http://localhost:8000'

        user = Mock()
        user.email = 'admin@example.com'
        mock_queryset = Mock()
        mock_queryset.exists.return_value = True
        mock_queryset.__iter__ = Mock(return_value=iter([user]))
        mock_user_filter.return_value.exclude.return_value = mock_queryset


        report = Mock()
        report.report_number = 'MSRN-001'
        report.bon_commande = Mock()
        report.bon_commande.numero = 'PO001'
        report.bon_commande.get_supplier.return_value = 'SUPPLIER1'
        report.bon_commande.get_currency.return_value = 'XOF'
        report.bon_commande.montant_total.return_value = 1000000
        report.bon_commande.montant_recu.return_value = 800000
        report.progress_rate_snapshot = 80.0
        report.retention_rate = 5.0
        report.retention_cause = 'Test cause'
        report.user = 'test@example.com'
        report.created_at = None
        report.pdf_file = None
        
        mock_render.return_value = '<html>Test HTML</html>'
        mock_email = Mock()
        mock_email_class.return_value = mock_email
        
        result = send_msrn_notification(report)
        
        self.assertTrue(result)
        # Vérise que ça utilise 'N/A' pour la date
        args, kwargs = mock_email_class.call_args
        self.assertIn('N/A', kwargs['body'])