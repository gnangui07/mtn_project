# tests/test_signals.py
from decimal import Decimal
from django.test import TestCase
from orders.models import NumeroBonCommande, FichierImporte, Reception
from orders.signals import update_bon_commande_montants


class TestSignals(TestCase):
    def setUp(self):
        # Créer un bon de commande
        self.bon_commande = NumeroBonCommande.objects.create(numero='TEST123')
        
        # Créer un fichier
        self.fichier = FichierImporte.objects.create(fichier='test.csv')

    def test_update_bon_commande_montants_on_save(self):
        """Test la mise à jour des montants lors de la sauvegarde d'une réception"""
        # Créer une réception
        reception = Reception.objects.create(
            bon_commande=self.bon_commande,
            fichier=self.fichier,
            business_id="ORDER:TEST123|LINE:1|ITEM:1|SCHEDULE:1",
            ordered_quantity=Decimal('100'),
            quantity_delivered=Decimal('80'),
            unit_price=Decimal('10.50')
        )
        
        # Vérifier que les montants ont été mis à jour
        self.bon_commande.refresh_from_db()
        self.assertGreater(self.bon_commande._montant_total, Decimal('0'))
        self.assertGreater(self.bon_commande._montant_recu, Decimal('0'))

    def test_update_bon_commande_montants_on_delete(self):
        """Test la mise à jour des montants lors de la suppression d'une réception"""
        # Créer une réception
        reception = Reception.objects.create(
            bon_commande=self.bon_commande,
            fichier=self.fichier,
            business_id="ORDER:TEST123|LINE:1|ITEM:1|SCHEDULE:1",
            ordered_quantity=Decimal('100'),
            quantity_delivered=Decimal('80'),
            unit_price=Decimal('10.50')
        )
        
        # Sauvegarder les montants avant suppression
        self.bon_commande.refresh_from_db()
        montant_total_avant = self.bon_commande._montant_total
        montant_recu_avant = self.bon_commande._montant_recu
        
        # Supprimer la réception
        reception.delete()
        
        # Vérifier que les montants ont été mis à jour
        self.bon_commande.refresh_from_db()
        self.assertNotEqual(self.bon_commande._montant_total, montant_total_avant)
        self.assertNotEqual(self.bon_commande._montant_recu, montant_recu_avant)

    def test_update_bon_commande_montants_no_bon_commande(self):
        """Test avec une réception sans bon de commande"""
        # Créer une réception sans bon de commande (bon_commande_id sera None)
        reception = Reception(
            fichier=self.fichier,
            business_id="ORDER:TEST123|LINE:1|ITEM:1|SCHEDULE:1",
            ordered_quantity=Decimal('100'),
            quantity_delivered=Decimal('80'),
            unit_price=Decimal('10.50')
        )
        # Ne pas sauvegarder pour éviter les contraintes de validation
        
        # Ne devrait pas lever d'exception car bon_commande_id est None
        try:
            update_bon_commande_montants(Reception, reception)
        except Exception as e:
            self.fail(f"update_bon_commande_montants a levé une exception pour une réception sans bon de commande: {e}")

    def test_update_bon_commande_montants_bon_not_found(self):
        """Test avec un bon de commande qui n'existe pas"""
        # Créer une réception avec un bon_commande_id invalide
        reception = Reception(
            bon_commande_id=999,  # ID qui n'existe pas
            fichier=self.fichier,
            business_id="ORDER:TEST123|LINE:1|ITEM:1|SCHEDULE:1",
            ordered_quantity=Decimal('100'),
            quantity_delivered=Decimal('80'),
            unit_price=Decimal('10.50')
        )
        
        # Ne devrait pas lever d'exception
        try:
            update_bon_commande_montants(Reception, reception)
        except Exception:
            self.fail("update_bon_commande_montants a levé une exception pour un bon de commande inexistant")