# tests/test_api.py
import pytest
from django.test import TestCase
from orders import api


class TestApiModule(TestCase):
    def test_api_all_contains_expected_functions(self):
        """Test que __all__ contient toutes les fonctions exportées"""
        expected_functions = [
            # Extracteurs de données
            'get_price_from_ligne',
            'get_supplier_from_ligne',
            'get_ordered_date_from_ligne',
            'get_project_number_from_ligne',
            'get_task_number_from_ligne',
            'get_order_description_from_ligne',
            'get_schedule_from_ligne',
            'get_line_from_ligne',
            
            # APIs de réception
            'update_quantity_delivered',
            'reset_quantity_delivered',
            
            # APIs d'activité
            'get_activity_logs',
            'get_all_bons',
            'get_additional_data_for_reception'
        ]
        
        self.assertEqual(api.__all__, expected_functions)

    def test_data_extractors_imported(self):
        """Test que les extracteurs de données sont importés"""
        self.assertTrue(hasattr(api, 'get_price_from_ligne'))
        self.assertTrue(hasattr(api, 'get_supplier_from_ligne'))
        self.assertTrue(hasattr(api, 'get_ordered_date_from_ligne'))

    def test_reception_api_imported(self):
        """Test que les APIs de réception sont importées"""
        self.assertTrue(hasattr(api, 'update_quantity_delivered'))
        self.assertTrue(hasattr(api, 'reset_quantity_delivered'))

    def test_activity_api_imported(self):
        """Test que les APIs d'activité sont importées"""
        self.assertTrue(hasattr(api, 'get_activity_logs'))
        self.assertTrue(hasattr(api, 'get_all_bons'))
        self.assertTrue(hasattr(api, 'get_additional_data_for_reception'))

    def test_module_can_be_imported(self):
        """Test que le module peut être importé sans erreur"""
        try:
            from orders.api import (
                get_price_from_ligne,
                update_quantity_delivered,
                get_activity_logs
            )
            success = True
        except ImportError:
            success = False
        
        self.assertTrue(success, "Le module api devrait pouvoir être importé sans erreur")