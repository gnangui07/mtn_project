import pytest
from decimal import Decimal
from django.test import TestCase
from orders.models import NumeroBonCommande
from orders.penalty_amendment_data import (
    collect_penalty_amendment_context,
    _as_decimal
)

class TestPenaltyAmendmentData(TestCase):
    def test_as_decimal(self):
        """Test conversion en Decimal"""
        assert _as_decimal('100') == Decimal('100')
        assert _as_decimal('1,000.50') == Decimal('1000.50')
        assert _as_decimal(None) == Decimal('0.00')
        assert _as_decimal('invalid') == Decimal('0.00')
    
    def test_collect_penalty_amendment_context(self):
        """Test collecte du contexte d'amendement"""
        # Créer un bon de commande de test
        bon = NumeroBonCommande.objects.create(numero='PO123')
        
        # Appeler la fonction
        context = collect_penalty_amendment_context(bon)
        
        # Vérifier les champs de base
        assert context['po_number'] == 'PO123'
        assert isinstance(context['po_amount'], Decimal)
        assert context['supplier'] == 'N/A'
        assert context['penalty_due'] == Decimal('0.00')
        assert context['new_penalty_due'] == Decimal('0.00')
