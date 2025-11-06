# tests/test_penalty_data.py
import json
from decimal import Decimal
from datetime import datetime
from django.test import TestCase
from orders.models import NumeroBonCommande, FichierImporte, LigneFichier, TimelineDelay
from orders.penalty_data import collect_penalty_context, _normalize_header, _find_order_key, _get_value_tolerant, _parse_date


class TestPenaltyData(TestCase):
    def setUp(self):
        # Créer un bon de commande
        self.bon_commande = NumeroBonCommande.objects.create(numero='TEST123')
        
        # Créer un fichier avec des lignes
        self.fichier = FichierImporte.objects.create(fichier='test.csv')
        
        # Nettoyer les lignes auto-créées
        self.fichier.lignes.all().delete()
        
        # Créer une ligne avec des données de test
        self.ligne = LigneFichier.objects.create(
            fichier=self.fichier,
            numero_ligne=1,
            contenu={
                'Order': 'TEST123',
                'Supplier': 'Test Supplier',
                'Currency': 'XOF',
                'Creation Date': '2024-01-15',
                'PIP END DATE': '2024-06-30',
                'ACTUAL END DATE': '2024-07-15',
                'Total': '1000000',
                'Order Description': 'Test Project',
                'Project Coordinator': 'John Doe'
            }
        )
        
        # Associer le fichier au bon de commande
        self.bon_commande.fichiers.add(self.fichier)
        
        # Créer un délai de timeline
        self.timeline_delay = TimelineDelay.objects.create(
            bon_commande=self.bon_commande,
            delay_part_mtn=5,
            delay_part_force_majeure=3,
            delay_part_vendor=2,
            quotite_realisee=Decimal('100.00')
        )

    def test_collect_penalty_context_success(self):
        """Test la collecte du contexte de pénalité avec succès"""
        context = collect_penalty_context(self.bon_commande)
        
        # Vérifier les champs principaux
        self.assertEqual(context['po_number'], 'TEST123')
        self.assertEqual(context['supplier'], 'Test Supplier')
        self.assertEqual(context['currency'], 'XOF')
        self.assertEqual(context['po_amount'], Decimal('1000000'))
        self.assertEqual(context['order_description'], 'Test Project')
        self.assertEqual(context['project_coordinator'], 'John Doe')
        
        # Vérifier les calculs de pénalité
        self.assertIn('penalties_due', context)
        self.assertIn('penalty_cap', context)
        self.assertIn('penalties_calculated', context)
        self.assertEqual(context['delay_part_mtn'], 5)
        self.assertEqual(context['delay_part_vendor'], 2)

    def test_collect_penalty_context_no_timeline_delay(self):
        """Test la collecte sans délai de timeline"""
        # Supprimer le timeline delay
        self.timeline_delay.delete()
        
        # Rafraîchir le bon de commande pour s'assurer que la relation est à jour
        self.bon_commande.refresh_from_db()
        
        context = collect_penalty_context(self.bon_commande)
        
        # Les valeurs de délai devraient être 0 quand il n'y a pas de TimelineDelay
        self.assertEqual(context['delay_part_mtn'], 0)
        self.assertEqual(context['delay_part_vendor'], 0)
        self.assertEqual(context['quotite_realisee'], Decimal('100.00'))

    def test_collect_penalty_context_no_lignes(self):
        """Test la collecte sans lignes de fichier"""
        # Supprimer la ligne
        self.ligne.delete()
        
        context = collect_penalty_context(self.bon_commande)
        
        # Les valeurs devraient être des valeurs par défaut
        self.assertEqual(context['supplier'], 'N/A')
        self.assertEqual(context['currency'], 'N/A')

    def test_normalize_header(self):
        """Test la normalisation des en-têtes"""
        self.assertEqual(_normalize_header('Order Description'), 'order description')
        self.assertEqual(_normalize_header('PIP_END_DATE'), 'pip end date')
        self.assertEqual(_normalize_header('  Creation Date  '), 'creation date')

    def test_find_order_key(self):
        """Test la recherche de clé d'ordre"""
        contenu = {'Order': 'TEST123', 'Description': 'Test'}
        self.assertEqual(_find_order_key(contenu), 'Order')
        
        contenu = {'Commande': 'TEST123', 'Description': 'Test'}
        self.assertEqual(_find_order_key(contenu), 'Commande')
        
        contenu = {'Description': 'Test'}  # Pas de clé d'ordre
        self.assertIsNone(_find_order_key(contenu))

    def test_get_value_tolerant(self):
        """Test la récupération tolérante de valeurs"""
        contenu = {
            'Supplier': 'Test Supplier',
            'Order Description': 'Test Project',
            'Total Amount': '1000'
        }
        
        # Test avec candidats exacts
        self.assertEqual(_get_value_tolerant(contenu, exact_candidates=('Supplier',)), 'Test Supplier')
        
        # Test avec tokens
        self.assertEqual(_get_value_tolerant(contenu, tokens=('order', 'description')), 'Test Project')
        self.assertEqual(_get_value_tolerant(contenu, tokens=('total', 'amount')), '1000')
        
        # Test avec valeur non trouvée
        self.assertIsNone(_get_value_tolerant(contenu, exact_candidates=('Nonexistent',)))

    def test_parse_date(self):
        """Test l'analyse des dates"""
        # Format YYYY-MM-DD
        date = _parse_date('2024-01-15')
        self.assertIsInstance(date, datetime)
        self.assertEqual(date.year, 2024)
        self.assertEqual(date.month, 1)
        self.assertEqual(date.day, 15)
        
        # Format DD/MM/YYYY
        date = _parse_date('15/01/2024')
        self.assertIsInstance(date, datetime)
        self.assertEqual(date.year, 2024)
        self.assertEqual(date.month, 1)
        self.assertEqual(date.day, 15)
        
        # Date invalide
        self.assertIsNone(_parse_date('invalid-date'))
        self.assertIsNone(_parse_date(''))
        self.assertIsNone(_parse_date(None))

    def test_penalty_calculation(self):
        """Test les calculs de pénalité"""
        context = collect_penalty_context(self.bon_commande)
        
        # Vérifier que les pénalités sont calculées correctement
        self.assertIsInstance(context['penalties_due'], Decimal)
        self.assertIsInstance(context['penalty_cap'], Decimal)
        self.assertIsInstance(context['penalties_calculated'], Decimal)
        
        # La pénalité due ne doit pas dépasser le plafond
        self.assertLessEqual(context['penalties_due'], context['penalty_cap'])
        
        # Le plafond doit être 10% du montant du PO
        expected_cap = context['po_amount'] * Decimal('0.10')
        self.assertEqual(context['penalty_cap'], expected_cap)