# tests/test_delay_evaluation_api.py
import pytest
import json
from unittest.mock import Mock, patch
from django.http import JsonResponse, HttpResponse
from django.contrib.auth import get_user_model
from orders.delay_evaluation_api import generate_delay_evaluation_report_api

User = get_user_model()


class TestDelayEvaluationAPI:
    """Tests pour la vue generate_delay_evaluation_report_api"""

    @pytest.fixture
    def user(self, db):
        return User.objects.create_user(
            email='test@example.com',
            password='testpass',
            first_name='Test',
            last_name='User'
        )

    @pytest.fixture
    def mock_request(self, user):
        request = Mock()
        request.method = 'GET'
        request.user = user
        return request

    @pytest.mark.django_db
    def test_method_not_allowed(self, mock_request):
        """Test avec une méthode non autorisée"""
        mock_request.method = 'PUT'
        response = generate_delay_evaluation_report_api(mock_request, 1)
        
        assert isinstance(response, JsonResponse)
        assert response.status_code == 405
        data = json.loads(response.content)
        assert data['success'] is False
        assert 'Méthode non autorisée' in data['error']

    @pytest.mark.django_db
    @patch('orders.delay_evaluation_api.NumeroBonCommande.objects.select_related')
    def test_bon_commande_not_found(self, mock_select_related, mock_request):
        """Test quand le bon de commande n'existe pas"""
        mock_select_related.return_value.get.side_effect = Exception('Not found')
        
        response = generate_delay_evaluation_report_api(mock_request, 999)
        
        assert isinstance(response, JsonResponse)
        assert response.status_code == 404
        data = json.loads(response.content)
        assert data['success'] is False
        assert 'Bon de commande non trouvé' in data['error']

    @pytest.mark.django_db
    @patch('orders.delay_evaluation_api.CELERY_AVAILABLE', False)
    @patch('orders.delay_evaluation_api.NumeroBonCommande.objects.select_related')
    @patch('orders.delay_evaluation_api.collect_delay_evaluation_context')
    @patch('orders.delay_evaluation_api.generate_delay_evaluation_report')
    @patch('orders.delay_evaluation_api.threading.Thread')
    def test_successful_pdf_generation(
        self, mock_thread, mock_generate_report, mock_collect_context, 
        mock_select_related, mock_request
    ):
        """Test la génération réussie du PDF"""
        # Setup mocks
        bon_commande = Mock()
        bon_commande.numero = 'TEST123'
        mock_select_related.return_value.get.return_value = bon_commande
        mock_collect_context.return_value = {
            'po_number': 'TEST123',
            'supplier': 'Test Supplier'
        }
        
        mock_pdf_buffer = Mock()
        mock_pdf_buffer.getvalue.return_value = b'%PDF-1.4 fake pdf content'
        mock_generate_report.return_value = mock_pdf_buffer
        
        mock_thread_instance = Mock()
        mock_thread.return_value = mock_thread_instance

        # Call the view
        response = generate_delay_evaluation_report_api(mock_request, 1)

        # Assertions
        assert isinstance(response, HttpResponse)
        assert response.status_code == 200
        assert response['content-type'] == 'application/pdf'
        assert 'DelayEvaluation-TEST123.pdf' in response['content-disposition']
        assert b'%PDF-1.4 fake pdf content' in response.content

        # Verify mocks were called
        mock_select_related.return_value.get.assert_called_once_with(id=1)
        mock_collect_context.assert_called_once_with(bon_commande)
        mock_generate_report.assert_called_once()
        mock_thread.assert_called_once()

    @pytest.mark.django_db
    @patch('orders.delay_evaluation_api.NumeroBonCommande.objects.select_related')
    @patch('orders.delay_evaluation_api.collect_delay_evaluation_context')
    def test_with_observation_and_attachments(self, mock_collect_context, mock_select_related, mock_request):
        """Test avec observation et attachments"""
        bon_commande = Mock()
        bon_commande.numero = 'TEST123'
        mock_select_related.return_value.get.return_value = bon_commande
        mock_collect_context.return_value = {}
        mock_pdf_buffer = Mock()
        mock_pdf_buffer.getvalue.return_value = b'%PDF-1.4 fake pdf content'

        with patch('orders.delay_evaluation_api.generate_delay_evaluation_report', return_value=mock_pdf_buffer):
            with patch('orders.delay_evaluation_api.threading.Thread'):
                # Test avec POST et JSON
                mock_request.method = 'POST'
                mock_request.content_type = 'application/json'
                mock_request.body = json.dumps({
                    'observation': 'Test observation',
                    'attachments': 'Test attachments'
                }).encode('utf-8')

                response = generate_delay_evaluation_report_api(mock_request, 1)
                assert response.status_code == 200

                # Vérifier que le contexte a été enrichi
                call_args = mock_collect_context.call_args
                assert call_args[0] == (bon_commande,)

    @pytest.mark.django_db
    @patch('orders.delay_evaluation_api.NumeroBonCommande.objects.select_related')
    @patch('orders.delay_evaluation_api.collect_delay_evaluation_context')
    def test_with_form_data(self, mock_collect_context, mock_select_related, mock_request):
        """Test avec données de formulaire"""
        bon_commande = Mock()
        bon_commande.numero = 'TEST123'
        mock_select_related.return_value.get.return_value = bon_commande
        mock_collect_context.return_value = {}
        mock_pdf_buffer = Mock()
        mock_pdf_buffer.getvalue.return_value = b'%PDF-1.4 fake pdf content'

        with patch('orders.delay_evaluation_api.generate_delay_evaluation_report', return_value=mock_pdf_buffer):
            with patch('orders.delay_evaluation_api.threading.Thread'):
                # Test avec POST et form data
                mock_request.method = 'POST'
                mock_request.content_type = 'application/x-www-form-urlencoded'
                mock_request.POST = {
                    'observation': 'Test observation',
                    'attachments': 'Test attachments'
                }

                response = generate_delay_evaluation_report_api(mock_request, 1)
                assert response.status_code == 200

    @patch('orders.delay_evaluation_api.CELERY_AVAILABLE', False)
    def test_post_method_allowed(self, mock_request):
        """Test que la méthode POST est autorisée (mode synchrone)"""
        mock_request.method = 'POST'
        mock_request.content_type = 'application/x-www-form-urlencoded'
        mock_request.POST = {}
        
        with patch('orders.delay_evaluation_api.NumeroBonCommande.objects.select_related') as mock_select_related:
            bon_commande = Mock()
            bon_commande.numero = 'TEST123'
            mock_select_related.return_value.get.return_value = bon_commande
            with patch('orders.delay_evaluation_api.collect_delay_evaluation_context', return_value={}):
                mock_pdf_buffer = Mock()
                mock_pdf_buffer.getvalue.return_value = b'%PDF-1.4 fake pdf content'
                with patch('orders.delay_evaluation_api.generate_delay_evaluation_report', return_value=mock_pdf_buffer):
                    with patch('orders.delay_evaluation_api.threading.Thread'):
                        response = generate_delay_evaluation_report_api(mock_request, 1)
                        
                        # Should not return method not allowed
                        assert not isinstance(response, JsonResponse) or response.status_code != 405

    @patch('orders.delay_evaluation_api.CELERY_AVAILABLE', False)
    @patch('orders.delay_evaluation_api.NumeroBonCommande.objects.select_related')
    @patch('orders.delay_evaluation_api.collect_delay_evaluation_context')
    @patch('orders.delay_evaluation_api.generate_delay_evaluation_report')
    def test_email_sent_async(self, mock_generate_report, mock_collect_context, mock_select_related, mock_request):
        """Test que l'email est envoyé de façon asynchrone (mode synchrone)"""
        bon_commande = Mock()
        bon_commande.numero = 'TEST123'
        mock_select_related.return_value.get.return_value = bon_commande
        mock_collect_context.return_value = {}
        mock_pdf_buffer = Mock()
        mock_pdf_buffer.getvalue.return_value = b'%PDF-1.4 fake pdf content'
        mock_generate_report.return_value = mock_pdf_buffer

        with patch('orders.delay_evaluation_api.send_penalty_notification') as mock_send_email:
            with patch('orders.delay_evaluation_api.threading.Thread') as mock_thread:
                mock_thread_instance = Mock()
                mock_thread.return_value = mock_thread_instance

                response = generate_delay_evaluation_report_api(mock_request, 1)

                # Verify thread was started
                mock_thread.assert_called_once()
                mock_thread_instance.start.assert_called_once()