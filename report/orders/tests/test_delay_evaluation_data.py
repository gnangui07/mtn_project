# tests/test_delay_evaluation_data.py
import pytest
from decimal import Decimal
from datetime import datetime
from unittest.mock import Mock, patch
from django.test import TestCase
from orders.delay_evaluation_data import collect_delay_evaluation_context, CRITERIA_LABELS
from orders.models import NumeroBonCommande, TimelineDelay


class TestDelayEvaluationData:
    """Tests pour la collecte des données d'évaluation des délais"""

    @pytest.fixture
    def bon_commande(self, db):
        """Create a real NumeroBonCommande object"""
        bon = NumeroBonCommande.objects.create(
            numero='TEST123',
            cpu='ITS'
        )
        return bon

    @pytest.mark.django_db
    @patch('orders.delay_evaluation_data._get_first_occurrence_contenu')
    def test_collect_delay_evaluation_context_basic(self, mock_get_contenu, bon_commande):
        """Test la collecte de contexte de base"""
        mock_get_contenu.return_value = {
            'Supplier': 'Test Supplier',
            'Currency': 'XOF',
            'Project Manager': 'John Doe',
            'Order Description': 'Test Equipment',
            'Creation Date': '2024-01-01',
            'PIP END DATE': '2024-02-01',
            'ACTUAL END DATE': '2024-02-15',
            'Total': '1000000'
        }

        context = collect_delay_evaluation_context(bon_commande)

        assert context['po_number'] == 'TEST123'
        assert context['supplier'] == 'Test Supplier'
        assert context['currency'] == 'XOF'
        assert context['project_manager'] == 'John Doe'
        assert context['order_description'] == 'Test Equipment'
        assert context['po_amount'] == Decimal('1000000.00')
        assert context['total_delay_days'] == 14  # du 2024-02-01 au 2024-02-15

    @pytest.mark.django_db
    @patch('orders.delay_evaluation_data._get_first_occurrence_contenu')
    def test_collect_delay_evaluation_context_with_timeline(self, mock_get_contenu, bon_commande):
        """Test la collecte avec données de timeline"""
        mock_get_contenu.return_value = {
            'Supplier': 'Test Supplier',
            'Currency': 'XOF',
            'Project Manager': 'John Doe',
            'Order Description': 'Test Equipment',
            'Creation Date': '2024-01-01',
            'PIP END DATE': '2024-02-01',
            'ACTUAL END DATE': '2024-02-15',
            'Total': '1000000'
        }

        timeline = TimelineDelay.objects.create(
            bon_commande=bon_commande,
            delay_part_mtn=5,
            delay_part_vendor=7,
            delay_part_force_majeure=2,
            comment_mtn="Retard MTN",
            comment_vendor="Retard fournisseur",
            comment_force_majeure="Force majeure"
        )

        context = collect_delay_evaluation_context(bon_commande)

        assert context['delay_part_mtn'] == 5
        assert context['delay_part_vendor'] == 7
        assert context['delay_part_force_majeure'] == 2
        assert context['comment_mtn'] == "Retard MTN"
        assert context['comment_vendor'] == "Retard fournisseur"
        assert context['comment_force_majeure'] == "Force majeure"

    @pytest.mark.django_db
    @patch('orders.delay_evaluation_data._get_first_occurrence_contenu')
    def test_collect_delay_evaluation_context_with_vendor_evaluation(self, mock_get_contenu, bon_commande):
        """Test la collecte avec évaluation fournisseur"""
        mock_get_contenu.return_value = {
            'Supplier': 'Test Supplier',
            'Currency': 'XOF',
            'Project Manager': 'John Doe',
            'Order Description': 'Test Equipment',
            'Creation Date': '2024-01-01',
            'PIP END DATE': '2024-02-01',
            'ACTUAL END DATE': '2024-02-15',
            'Total': '1000000'
        }

        evaluator = Mock()
        evaluator.get_full_name.return_value = 'Jane Doe'
        evaluator.email = 'jane@example.com'

        vendor_evaluation = Mock()
        vendor_evaluation.date_evaluation = datetime(2024, 3, 1)
        vendor_evaluation.vendor_final_rating = Decimal('8.50')
        vendor_evaluation.comments = "Très bon fournisseur"
        vendor_evaluation.evaluator = evaluator
        vendor_evaluation.delivery_compliance = 9
        vendor_evaluation.delivery_timeline = 8
        vendor_evaluation.advising_capability = 7
        vendor_evaluation.after_sales_qos = 9
        vendor_evaluation.vendor_relationship = 8

        with patch('orders.delay_evaluation_data.VendorEvaluation.objects.filter') as mock_filter:
            mock_filter.return_value.order_by.return_value.first.return_value = vendor_evaluation

            context = collect_delay_evaluation_context(bon_commande)

        assert context['evaluation_date'] == datetime(2024, 3, 1)
        assert context['final_rating'] == Decimal('8.50')
        assert context['observation'] == "Très bon fournisseur"
        assert context['evaluator_name'] == 'Jane Doe'
        assert context['total_score'] == 41  # 9+8+7+9+8
        assert len(context['criteria_details']) == 5
        # Vérifier que les critères sont bien formatés
        criteria_keys = [c['key'] for c in context['criteria_details']]
        assert set(criteria_keys) == set(CRITERIA_LABELS.keys())

    @pytest.mark.django_db
    @patch('orders.delay_evaluation_data._get_first_occurrence_contenu')
    def test_collect_delay_evaluation_context_no_vendor_evaluation(self, mock_get_contenu, bon_commande):
        """Test la collecte sans évaluation fournisseur"""
        mock_get_contenu.return_value = {
            'Supplier': 'Test Supplier',
            'Currency': 'XOF',
            'Project Manager': 'John Doe',
            'Order Description': 'Test Equipment',
            'Creation Date': '2024-01-01',
            'PIP END DATE': '2024-02-01',
            'ACTUAL END DATE': '2024-02-15',
            'Total': '1000000'
        }

        with patch('orders.delay_evaluation_data.VendorEvaluation.objects.filter') as mock_filter:
            mock_filter.return_value.order_by.return_value.first.return_value = None

            context = collect_delay_evaluation_context(bon_commande)

        assert context['final_rating'] == Decimal('0.00')
        assert context['criteria_details'] == []
        assert context['total_score'] == 0
        assert context['evaluator_name'] == 'N/A'

    @patch('orders.delay_evaluation_data._get_first_occurrence_contenu')
    def test_collect_delay_evaluation_context_no_dates(self, mock_get_contenu, bon_commande):
        """Test la collecte sans dates"""
        mock_get_contenu.return_value = {
            'Supplier': 'Test Supplier',
            'Currency': 'XOF',
            'Project Manager': 'John Doe',
            'Order Description': 'Test Equipment',
            'Total': '1000000'
        }

        context = collect_delay_evaluation_context(bon_commande)

        assert context['creation_date'] is None
        assert context['pip_end_date'] is None
        assert context['actual_end_date'] is None
        assert context['total_delay_days'] == 0

    @patch('orders.delay_evaluation_data._get_first_occurrence_contenu')
    def test_collect_delay_evaluation_context_fallback_values(self, mock_get_contenu, bon_commande):
        """Test les valeurs par défaut"""
        mock_get_contenu.return_value = {}

        context = collect_delay_evaluation_context(bon_commande)

        assert context['supplier'] == 'Test Supplier'  # fallback sur bon_commande.fournisseur
        assert context['currency'] == 'XOF'  # fallback sur bon_commande.devise
        assert context['project_manager'] == 'N/A'
        assert context['order_description'] == 'N/A'
        assert context['po_amount'] == Decimal('0.00')