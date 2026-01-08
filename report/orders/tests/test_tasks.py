import pytest
from unittest.mock import Mock, patch, MagicMock, mock_open
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.cache import cache
from celery.result import AsyncResult
from decimal import Decimal
from datetime import date, datetime
from django.utils import timezone
import tempfile
import os

from orders.tasks import (
    send_signature_reminder_task,
    invalidate_bon_cache,
    invalidate_service_cache,
    _make_export_payload,
    export_po_progress_task,
    export_vendor_evaluations_task,
    export_bon_excel_task,
    import_fichier_task,
    generate_msrn_pdf_task,
    generate_penalty_pdf_task,
    generate_delay_evaluation_pdf_task,
    generate_compensation_letter_pdf_task,
    generate_penalty_amendment_pdf_task
)
from orders.models import (
    MSRNSignatureTracking, MSRNReport, NumeroBonCommande,
    FichierImporte, PenaltyReportLog, DelayEvaluationReportLog,
    CompensationLetterLog, PenaltyAmendmentReportLog
)

User = get_user_model()


class TestSignatureReminderTask(TestCase):
    """Test la tâche d'envoi de rappel de signature"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.bon = NumeroBonCommande.objects.create(
            numero='PO001'
        )
        self.report = MSRNReport.objects.create(
            bon_commande=self.bon,
            report_number='MSRN-001',
            retention_rate=5,
            retention_amount=50
        )
        self.signature = MSRNSignatureTracking.objects.create(
            msrn_report=self.report,
            signatory_name='John Doe',
            signatory_role='project_manager'
        )
    
    @patch('orders.emails.find_user_email_by_name')
    @patch('orders.emails.send_signature_reminder')
    def test_signature_reminder_success(self, mock_send, mock_find_email):
        """Test envoi réussi du rappel"""
        mock_find_email.return_value = 'john.doe@example.com'
        mock_send.return_value = True
        
        result = send_signature_reminder_task(self.signature.id)
        
        self.assertEqual(result['status'], 'sent')
        self.assertEqual(result['signature_id'], self.signature.id)
        self.assertEqual(result['email'], 'john.doe@example.com')
        mock_find_email.assert_called_once_with('John Doe')
        mock_send.assert_called_once()
    
    @patch('orders.emails.find_user_email_by_name')
    def test_signature_already_signed(self, mock_find_email):
        """Test si la signature est déjà signée"""
        self.signature.date_received = date.today()
        self.signature.save()
        
        # Vérifier que le statut est bien passé à 'signed'
        self.assertEqual(self.signature.status, 'signed')
        
        result = send_signature_reminder_task(self.signature.id)
        
        self.assertEqual(result['status'], 'already_signed')
        mock_find_email.assert_not_called()
    
    @patch('orders.emails.find_user_email_by_name')
    def test_signature_email_not_found(self, mock_find_email):
        """Test si l'email n'est pas trouvé"""
        mock_find_email.return_value = None
        
        result = send_signature_reminder_task(self.signature.id)
        
        self.assertEqual(result['status'], 'no_email')
        self.assertEqual(result['name'], 'John Doe')
    
    def test_signature_not_found(self):
        """Test si la signature n'existe pas"""
        result = send_signature_reminder_task(99999)
        
        self.assertEqual(result['status'], 'not_found')
        self.assertEqual(result['signature_id'], 99999)
    
    @patch('orders.emails.find_user_email_by_name')
    @patch('orders.emails.send_signature_reminder')
    def test_signature_reminder_failed(self, mock_send, mock_find_email):
        """Test échec de l'envoi"""
        mock_find_email.return_value = 'john.doe@example.com'
        mock_send.return_value = False
        
        result = send_signature_reminder_task(self.signature.id)
        
        self.assertEqual(result['status'], 'failed')
    
    @patch('orders.emails.find_user_email_by_name')
    @patch('orders.emails.send_signature_reminder')
    def test_signature_reminder_exception(self, mock_send, mock_find_email):
        """Test gestion des exceptions"""
        mock_find_email.return_value = 'john.doe@example.com'
        mock_send.side_effect = Exception('SMTP error')
        
        with self.assertRaises(Exception):
            send_signature_reminder_task(self.signature.id)


class TestCacheInvalidationTasks(TestCase):
    """Test les tâches d'invalidation de cache"""
    
    @patch('orders.tasks.cache')
    def test_invalidate_bon_cache(self, mock_cache):
        """Test invalidation cache bon"""
        invalidate_bon_cache(123)
        
        mock_cache.delete.assert_any_call('bon_details_123')
        mock_cache.delete.assert_any_call('bon_receptions_123')
        mock_cache.delete.assert_any_call('bon_lignes_123')
    
    @patch('orders.tasks.cache')
    def test_invalidate_bon_cache_exception(self, mock_cache):
        """Test gestion exception cache bon"""
        mock_cache.delete.side_effect = Exception('Cache error')
        
        # Ne doit pas lever d'exception
        invalidate_bon_cache(123)
    
    @patch('orders.tasks.cache')
    def test_invalidate_service_cache(self, mock_cache):
        """Test invalidation cache service"""
        invalidate_service_cache('IT')
        
        mock_cache.delete.assert_called_once_with('bons_service_IT')
    
    @patch('orders.tasks.cache')
    def test_invalidate_service_cache_empty(self, mock_cache):
        """Test avec service vide"""
        invalidate_service_cache('')
        
        mock_cache.delete.assert_not_called()
    
    @patch('orders.tasks.cache')
    def test_invalidate_service_cache_exception(self, mock_cache):
        """Test gestion exception cache service"""
        mock_cache.delete.side_effect = Exception('Cache error')
        
        # Ne doit pas lever d'exception
        invalidate_service_cache('IT')


class TestExportTasks(TestCase):
    """Test les tâches d'export"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
    
    def test_make_export_payload(self):
        """Test création payload export"""
        mock_response = Mock()
        mock_response.content = b'file content'
        mock_response.get.side_effect = lambda key, default=None: {
            'Content-Disposition': 'attachment; filename="test.xlsx"',
            'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        }.get(key, default)
        
        result = _make_export_payload(mock_response, 'default.xlsx')
        
        self.assertEqual(result['filename'], 'test.xlsx')
        self.assertEqual(result['content_type'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        self.assertEqual(result['content_base64'], 'ZmlsZSBjb250ZW50')
    
    def test_make_export_payload_no_header(self):
        """Test payload sans Content-Disposition"""
        mock_response = Mock()
        mock_response.content = b'file content'
        mock_response.get.side_effect = lambda key, default=None: {
            'Content-Type': 'application/octet-stream'
        }.get(key, default)
        
        result = _make_export_payload(mock_response, 'default.xlsx')
        
        self.assertEqual(result['filename'], 'default.xlsx')
    
    @patch('orders.views_export.export_po_progress_monitoring')
    @patch('orders.tasks.RequestFactory')
    def test_export_po_progress_task(self, mock_rf, mock_export):
        """Test export PO progress"""
        mock_request = Mock()
        mock_request.user = self.user
        mock_rf.return_value.get.return_value = mock_request
        
        mock_response = Mock()
        mock_response.content = b'po content'
        mock_response.get.return_value = 'attachment; filename="po.xlsx"'
        mock_export.return_value = mock_response
        
        result = export_po_progress_task(self.user.id)
        
        self.assertIn('filename', result)
        self.assertIn('content_base64', result)
        mock_export.assert_called_once()
    
    @patch('orders.views_export.export_vendor_evaluations')
    @patch('orders.tasks.RequestFactory')
    def test_export_vendor_evaluations_task(self, mock_rf, mock_export):
        """Test export vendor evaluations"""
        mock_request = Mock()
        mock_request.user = self.user
        mock_rf.return_value.get.return_value = mock_request
        
        mock_response = Mock()
        mock_response.content = b'vendor content'
        mock_response.get.return_value = 'attachment; filename="vendor.xlsx"'
        mock_export.return_value = mock_response
        
        result = export_vendor_evaluations_task(self.user.id, supplier='SUP1')
        
        self.assertIn('filename', result)
        self.assertIn('content_base64', result)
        mock_export.assert_called_once()
    
    @patch('orders.views_export.export_bon_excel')
    @patch('orders.tasks.RequestFactory')
    def test_export_bon_excel_task(self, mock_rf, mock_export):
        """Test export bon Excel"""
        mock_request = Mock()
        mock_request.user = self.user
        mock_rf.return_value.get.return_value = mock_request
        
        mock_response = Mock()
        mock_response.content = b'bon content'
        mock_response.get.return_value = 'attachment; filename="bon.xlsx"'
        mock_export.return_value = mock_response
        
        result = export_bon_excel_task(self.user.id, 123, 'PO001')
        
        self.assertIn('filename', result)
        self.assertIn('content_base64', result)
        mock_export.assert_called_once()


class TestImportFichierTask(TestCase):
    """Test la tâche d'import de fichier"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
    
    @patch('orders.import_utils.import_file_optimized')
    def test_import_fichier_with_fichier_id(self, mock_import):
        """Test import avec fichier_id existant"""
        mock_import.return_value = (100, 5)
        
        # On crée l'objet sans le sauvegarder immédiatement pour fixer _skip_extraction
        fichier = FichierImporte(
            fichier=ContentFile(b'test content', name='test.xlsx'),
            utilisateur=self.user
        )
        fichier._skip_extraction = True
        fichier.save()
        
        # On peut aussi reset le mock pour être sûr qu'on ne compte que l'appel de la tâche
        mock_import.reset_mock()
        
        # Simuler l'existence du fichier sur le disque pour éviter FileNotFoundError
        with patch('os.path.exists', return_value=True):
            result = import_fichier_task('fake_path.xlsx', self.user.id, fichier_id=fichier.id)
            
            self.assertEqual(result['fichier_id'], fichier.id)
            self.assertEqual(result['nombre_lignes'], 100)
            self.assertEqual(result['bons_count'], 5)
            mock_import.assert_called_once_with(fichier, 'fake_path.xlsx')
    
    @patch('orders.import_utils.import_file_optimized')
    @patch('builtins.open', new_callable=mock_open, read_data=b'test content')
    @patch('os.path.exists')
    def test_import_fichier_without_fichier_id(self, mock_exists, mock_file, mock_import):
        """Test import sans fichier_id (création)"""
        mock_exists.return_value = True
        mock_import.return_value = (50, 3)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, 'test.xlsx')
            # Mock de open déjà fait par le décorateur
            
            result = import_fichier_task(file_path, self.user.id, original_filename='test.xlsx')
            
            self.assertIn('fichier_id', result)
            self.assertEqual(result['nombre_lignes'], 50)
            self.assertEqual(result['bons_count'], 3)
    
    @patch('orders.import_utils.import_file_optimized')
    @patch('builtins.open', new_callable=mock_open, read_data=b'test content')
    @patch('os.path.exists')
    @patch('os.remove')
    def test_import_fichier_cleanup_temp(self, mock_remove, mock_exists, mock_file, mock_import):
        """Test nettoyage fichier temporaire"""
        mock_exists.return_value = True
        mock_import.return_value = (50, 3)
        
        # Sur Windows, abspath va utiliser des \. On doit s'assurer que MEDIA_ROOT et file_path concordent.
        media_root = os.path.abspath("media")
        temp_dir = os.path.join(media_root, "imports", "temp")
        file_path = os.path.join(temp_dir, "test.xlsx")
        
        with override_settings(MEDIA_ROOT=media_root):
            # On simule que le fichier existe
            mock_exists.return_value = True
            
            result = import_fichier_task(file_path, self.user.id)
            
            # Vérifier que os.remove a bien été appelé car le chemin est dans temp
            mock_remove.assert_called_once_with(os.path.abspath(file_path))
    
    def test_import_fichier_file_not_found(self):
        """Test fichier non trouvé"""
        with self.assertRaises(Exception):
            import_fichier_task('/nonexistent/file.xlsx', self.user.id)


class TestGeneratePDFTasks(TestCase):
    """Test les tâches de génération PDF"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.bon = NumeroBonCommande.objects.create(
            numero='PO001'
        )
        self.report = MSRNReport.objects.create(
            bon_commande=self.bon,
            report_number='MSRN-001',
            retention_rate=5,
            retention_amount=50
        )
    
    @patch('orders.reports.generate_msrn_report')
    @patch('orders.emails.send_msrn_notification')
    def test_generate_msrn_pdf_task(self, mock_send, mock_generate):
        """Test génération PDF MSRN"""
        mock_pdf = Mock()
        mock_pdf.getvalue.return_value = b'pdf content'
        mock_generate.return_value = mock_pdf
        
        result = generate_msrn_pdf_task(self.report.id, self.user.id, send_email=False)
        
        self.assertEqual(result['report_id'], self.report.id)
        self.assertEqual(result['report_number'], 'MSRN-001')
        
        self.report.refresh_from_db()
        self.assertTrue(self.report.pdf_file)
        mock_send.assert_not_called()
    
    @patch('orders.reports.generate_msrn_report')
    @patch('orders.emails.send_msrn_notification')
    def test_generate_msrn_pdf_task_with_email(self, mock_send, mock_generate):
        """Test génération PDF MSRN avec email"""
        mock_pdf = Mock()
        mock_pdf.getvalue.return_value = b'pdf content'
        mock_generate.return_value = mock_pdf
        
        result = generate_msrn_pdf_task(self.report.id, self.user.id, send_email=True)
        
        mock_send.assert_called_once()
    
    @patch('orders.penalty_report.generate_penalty_report')
    @patch('orders.penalty_data.collect_penalty_context')
    @patch('orders.emails.send_penalty_notification')
    def test_generate_penalty_pdf_task(self, mock_send, mock_collect, mock_generate):
        """Test génération PDF pénalité"""
        mock_collect.return_value = {'test': 'data'}
        mock_pdf = Mock()
        mock_pdf.getvalue.return_value = b'penalty pdf'
        mock_generate.return_value = mock_pdf
        
        result = generate_penalty_pdf_task(self.bon.id, self.user.id, observation='Test obs', send_email=False)
        
        self.assertEqual(result['bon_id'], self.bon.id)
        self.assertIn('log_id', result)
        mock_send.assert_not_called()
    
    @patch('orders.delay_evaluation_report.generate_delay_evaluation_report')
    @patch('orders.delay_evaluation_data.collect_delay_evaluation_context')
    @patch('orders.emails.send_penalty_notification')
    def test_generate_delay_evaluation_pdf_task(self, mock_send, mock_collect, mock_generate):
        """Test génération PDF évaluation délais"""
        mock_collect.return_value = {'test': 'data'}
        mock_pdf = Mock()
        mock_pdf.getvalue.return_value = b'delay pdf'
        mock_generate.return_value = mock_pdf
        
        result = generate_delay_evaluation_pdf_task(
            self.bon.id, 
            self.user.id, 
            observation='Test obs',
            attachments='Attach1',
            send_email=False
        )
        
        self.assertEqual(result['bon_id'], self.bon.id)
        mock_send.assert_not_called()
    
    @patch('orders.compensation_letter_report.generate_compensation_letter')
    @patch('orders.penalty_data.collect_penalty_context')
    @patch('orders.emails.send_penalty_notification')
    @patch('django.utils.timezone.now')
    def test_generate_compensation_letter_pdf_task(self, mock_now, mock_send, mock_collect, mock_generate):
        """Test génération PDF lettre compensation"""
        # created_at utilise timezone.now() pour auto_now_add.
        # On doit retourner un VRAI objet datetime aware pour éviter le RuntimeWarning
        fixed_now = timezone.make_aware(datetime(2024, 1, 15, 12, 0, 0))
        mock_now.return_value = fixed_now
        
        mock_collect.return_value = {'test': 'data'}
        mock_pdf = Mock()
        mock_pdf.getvalue.return_value = b'compensation pdf'
        mock_generate.return_value = mock_pdf
        
        result = generate_compensation_letter_pdf_task(self.bon.id, self.user.id, send_email=False)
        
        self.assertEqual(result['bon_id'], self.bon.id)
        mock_send.assert_not_called()
    
    @patch('orders.penalty_amendment_report.generate_penalty_amendment_report')
    @patch('orders.penalty_amendment_data.collect_penalty_amendment_context')
    @patch('orders.emails.send_penalty_notification')
    def test_generate_penalty_amendment_pdf_task(self, mock_send, mock_collect, mock_generate):
        """Test génération PDF amendement pénalité"""
        mock_collect.return_value = {'test': 'data'}
        mock_pdf = Mock()
        mock_pdf.getvalue.return_value = b'amendment pdf'
        mock_generate.return_value = mock_pdf
        
        result = generate_penalty_amendment_pdf_task(
            self.bon.id,
            self.user.id,
            supplier_plea='Supplier plea',
            pm_proposal='PM proposal',
            penalty_status='reduite',
            new_penalty_due='100.50',
            send_email=False
        )
        
        self.assertEqual(result['bon_id'], self.bon.id)
        mock_send.assert_not_called()
    
    def test_generate_penalty_amendment_decimal_conversion(self):
        """Test conversion décimale dans amendement"""
        with patch('orders.penalty_amendment_report.generate_penalty_amendment_report') as mock_generate, \
             patch('orders.penalty_amendment_data.collect_penalty_amendment_context') as mock_collect, \
             patch('orders.emails.send_penalty_notification'):
            
            mock_collect.return_value = {}
            mock_pdf = Mock()
            mock_pdf.getvalue.return_value = b'amendment pdf'
            mock_generate.return_value = mock_pdf
            
            # Test avec string
            result = generate_penalty_amendment_pdf_task(
                self.bon.id, self.user.id, new_penalty_due='100,50', send_email=False
            )
            self.assertEqual(result['bon_id'], self.bon.id)
            
            # Test avec Decimal
            result = generate_penalty_amendment_pdf_task(
                self.bon.id, self.user.id, new_penalty_due=Decimal('200.75'), send_email=False
            )
            self.assertEqual(result['bon_id'], self.bon.id)
            
            # Test avec vide
            result = generate_penalty_amendment_pdf_task(
                self.bon.id, self.user.id, new_penalty_due='', send_email=False
            )
            self.assertEqual(result['bon_id'], self.bon.id)


class TestTaskExceptions(TestCase):
    """Test gestion des exceptions dans les tâches"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
    
    @patch('orders.reports.generate_msrn_report')
    def test_generate_msrn_pdf_task_exception(self, mock_generate):
        """Test exception dans génération MSRN"""
        mock_generate.side_effect = Exception('PDF generation error')
        
        with self.assertRaises(Exception):
            generate_msrn_pdf_task(999, self.user.id)
    
    @patch('orders.emails.send_msrn_notification')
    @patch('orders.reports.generate_msrn_report')
    def test_generate_msrn_email_error(self, mock_generate, mock_send):
        """Test erreur email ne bloque pas la génération"""
        mock_pdf = Mock()
        mock_pdf.getvalue.return_value = b'pdf content'
        mock_generate.return_value = mock_pdf
        mock_send.side_effect = Exception('Email error')
        
        # Ne doit pas lever d'exception
        result = generate_msrn_pdf_task(self.create_report().id, self.user.id, send_email=True)
        
        self.assertIn('report_id', result)
    
    def create_report(self):
        """Helper pour créer un rapport"""
        bon = NumeroBonCommande.objects.create(
            numero='PO002'
        )
        return MSRNReport.objects.create(
            bon_commande=bon,
            report_number='MSRN-002',
            retention_rate=5,
            retention_amount=100
        )
