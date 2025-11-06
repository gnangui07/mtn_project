# tests/test_data_extractors.py
import pytest
from decimal import Decimal
from unittest.mock import Mock
from orders.data_extractors import (
    get_price_from_ligne,
    get_supplier_from_ligne,
    get_ordered_date_from_ligne,
    get_project_number_from_ligne,
    get_task_number_from_ligne,
    get_order_description_from_ligne,
    get_schedule_from_ligne,
    get_line_from_ligne,
    calculate_quantity_payable
)


class TestDataExtractors:
    """Tests pour les fonctions d'extraction de données des lignes"""

    def setup_method(self):
        self.ligne = Mock()
        self.ligne.contenu = {}

    def test_get_price_from_ligne_with_price_key(self):
        """Test l'extraction du prix avec différentes clés"""
        test_cases = [
            ('Price', '100.50'),
            ('Prix', '150.75'),
            ('Unit Price', '200.00'),
            ('Prix Unitaire', '250.25'),
        ]

        for key, value in test_cases:
            self.ligne.contenu = {key: value}
            result = get_price_from_ligne(self.ligne)
            assert result == float(value)

    def test_get_price_from_ligne_with_comma_decimal(self):
        """Test l'extraction du prix avec virgule comme séparateur décimal"""
        self.ligne.contenu = {'Price': '100,50'}
        result = get_price_from_ligne(self.ligne)
        assert result == 100.50

    def test_get_price_from_ligne_not_found(self):
        """Test quand le prix n'est pas trouvé"""
        self.ligne.contenu = {'Other': 'value'}
        result = get_price_from_ligne(self.ligne)
        assert result == 0.0

    def test_get_price_from_ligne_invalid_value(self):
        """Test avec valeur de prix invalide"""
        self.ligne.contenu = {'Price': 'invalid'}
        result = get_price_from_ligne(self.ligne)
        assert result == 0.0

    def test_get_price_from_ligne_none_ligne(self):
        """Test avec ligne None"""
        result = get_price_from_ligne(None)
        assert result == 0.0

    def test_get_price_from_ligne_empty_contenu(self):
        """Test avec contenu vide"""
        self.ligne.contenu = {}
        result = get_price_from_ligne(self.ligne)
        assert result == 0.0

    def test_get_supplier_from_ligne(self):
        """Test l'extraction du fournisseur"""
        test_cases = [
            ('Supplier', 'Test Supplier Inc.'),
            ('Fournisseur', 'Fournisseur Test'),
            ('Vendor', 'Vendor Corp'),
            ('Vendeur', 'Vendeur SA'),
        ]

        for key, value in test_cases:
            self.ligne.contenu = {key: value}
            result = get_supplier_from_ligne(self.ligne)
            assert result == value

    def test_get_supplier_from_ligne_not_found(self):
        """Test quand le fournisseur n'est pas trouvé"""
        self.ligne.contenu = {'Other': 'value'}
        result = get_supplier_from_ligne(self.ligne)
        assert result == "N/A"

    def test_get_ordered_date_from_ligne(self):
        """Test l'extraction de la date de commande"""
        self.ligne.contenu = {'Ordered': '2024-03-15'}
        result = get_ordered_date_from_ligne(self.ligne)
        assert result == '2024-03-15'

    def test_get_ordered_date_from_ligne_with_date_key(self):
        """Test avec d'autres clés de date"""
        test_cases = [
            ('Order Date', '2024-03-15'),
            ('Date Commande', '2024-03-16'),
        ]

        for key, value in test_cases:
            self.ligne.contenu = {key: value}
            result = get_ordered_date_from_ligne(self.ligne)
            assert result == value

    def test_get_project_number_from_ligne(self):
        """Test l'extraction du numéro de projet"""
        test_cases = [
            ('Project Number', 'PROJ-001'),
            ('Project', 'PROJ-002'),
            ('Projet Numero', 'PROJ-003'),
            ('Projet', 'PROJ-004'),
        ]

        for key, value in test_cases:
            self.ligne.contenu = {key: value}
            result = get_project_number_from_ligne(self.ligne)
            assert result == value

    def test_get_task_number_from_ligne(self):
        """Test l'extraction du numéro de tâche"""
        test_cases = [
            ('Task Number', 'TASK-001'),
            ('Task', 'TASK-002'),
            ('Tache Numero', 'TASK-003'),
            ('Tache', 'TASK-004'),
        ]

        for key, value in test_cases:
            self.ligne.contenu = {key: value}
            result = get_task_number_from_ligne(self.ligne)
            assert result == value

    def test_get_order_description_from_ligne(self):
        """Test l'extraction de la description de commande"""
        test_cases = [
            ('Order Description', 'Test Equipment'),
            ('Commande Description', 'Équipement Test'),
            ('Description', 'Generic Description'),
        ]

        for key, value in test_cases:
            self.ligne.contenu = {key: value}
            result = get_order_description_from_ligne(self.ligne)
            assert result == value

    def test_get_order_description_excludes_line_description(self):
        """Test que la description de ligne est exclue"""
        self.ligne.contenu = {
            'Line Description': 'Line Desc',
            'Description': 'Order Desc'
        }
        result = get_order_description_from_ligne(self.ligne)
        assert result == 'Order Desc'

    def test_get_schedule_from_ligne(self):
        """Test l'extraction du schedule"""
        test_cases = [
            ('Schedule', 'SCHED-001'),
            ('Planning', 'SCHED-002'),
            ('Calendrier', 'SCHED-003'),
            ('Echeance', 'SCHED-004'),
        ]

        for key, value in test_cases:
            self.ligne.contenu = {key: value}
            result = get_schedule_from_ligne(self.ligne)
            assert result == value

    def test_get_line_from_ligne(self):
        """Test l'extraction du numéro de ligne"""
        test_cases = [
            ('Line', '001'),
            ('Ligne', '002'),
        ]

        for key, value in test_cases:
            self.ligne.contenu = {key: value}
            result = get_line_from_ligne(self.ligne)
            assert result == value

    def test_get_line_excludes_line_description(self):
        """Test que Line Description est exclu"""
        self.ligne.contenu = {
            'Line Description': 'Test Description',
            'Line': '001'
        }
        result = get_line_from_ligne(self.ligne)
        assert result == '001'

    def test_calculate_quantity_payable_valid(self):
        """Test le calcul de la quantité payable avec données valides"""
        self.ligne.contenu = {
            'Quantity Delivered': '100',
            'Price': '10.50'
        }
        result = calculate_quantity_payable(self.ligne)
        expected = Decimal('100') * Decimal('10.50')
        assert result == expected.quantize(Decimal('0.01'))

    def test_calculate_quantity_payable_with_comma_decimal(self):
        """Test le calcul avec virgule comme séparateur décimal"""
        self.ligne.contenu = {
            'Quantity Delivered': '100',
            'Price': '10,50'
        }
        result = calculate_quantity_payable(self.ligne)
        expected = Decimal('100') * Decimal('10.50')
        assert result == expected.quantize(Decimal('0.01'))

    def test_calculate_quantity_payable_no_quantity(self):
        """Test le calcul sans quantité livrée"""
        self.ligne.contenu = {'Price': '10.50'}
        result = calculate_quantity_payable(self.ligne)
        assert result == Decimal('0.00')

    def test_calculate_quantity_payable_no_price(self):
        """Test le calcul sans prix"""
        self.ligne.contenu = {'Quantity Delivered': '100'}
        result = calculate_quantity_payable(self.ligne)
        assert result == Decimal('0.00')

    def test_calculate_quantity_payable_invalid_price(self):
        """Test le calcul avec prix invalide"""
        self.ligne.contenu = {
            'Quantity Delivered': '100',
            'Price': 'invalid'
        }
        result = calculate_quantity_payable(self.ligne)
        assert result == Decimal('0.00')

    def test_calculate_quantity_payable_none_ligne(self):
        """Test le calcul avec ligne None"""
        result = calculate_quantity_payable(None)
        assert result == Decimal('0.00')