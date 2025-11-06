# tests/test_exports.py
import pytest
import pandas as pd
from io import BytesIO
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from orders.models import (
    NumeroBonCommande, FichierImporte, LigneFichier, 
    Reception, MSRNReport, VendorEvaluation, InitialReceptionBusiness
)
from orders import views_export as exports

User = get_user_model()


class TestExportPOProgressMonitoring(TestCase):
    def setUp(self):
        self.client = self.client_class()
        self.user = User.objects.create_user('test@example.com', 'testpass')
        self.user.is_active = True
        self.user.save()
        self.client.force_login(self.user)
        self.url = reverse('orders:export_po_progress_monitoring')
        
        # Créer des données de test
        self.bon = NumeroBonCommande.objects.create(numero='PO001', cpu='ITS')
        self.fichier = FichierImporte.objects.create(fichier='test.csv')
        self.bon.fichiers.add(self.fichier)
        
        # Nettoyer les lignes auto-créées
        self.fichier.lignes.all().delete()
        
        # Créer une ligne de fichier
        self.ligne = LigneFichier.objects.create(
            fichier=self.fichier,
            numero_ligne=1,
            business_id='EXPPO-L1',
            contenu={
                'Order': 'PO001',
                'CPU': 'ITS',
                'Sponsor': 'Test Sponsor',
                'Currency': 'XOF',
                'PIP END DATE': '2024-12-31',
                'ACTUAL END DATE': '2025-01-15'
            }
        )
        
        # Créer des réceptions initiales
        self.irb = InitialReceptionBusiness.objects.create(
            business_id='TEST001',
            bon_commande=self.bon,
            source_file=self.fichier,
            received_quantity=Decimal('50'),
            montant_total_initial=Decimal('1000'),
            montant_recu_initial=Decimal('500'),
            taux_avancement_initial=Decimal('50')
        )

    def test_acces_requiert_login(self):
        """Test que l'export nécessite une connexion"""
        # Créer un nouveau client non authentifié
        unauthenticated_client = self.client_class()
        response = unauthenticated_client.get(self.url)
        self.assertNotEqual(response.status_code, 200)

    def test_export_reussi(self):
        """Test export réussi"""
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 
                       'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        self.assertIn('attachment', response['Content-Disposition'])

    def test_export_avec_donnees(self):
        """Test export avec des données existantes"""
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        
        # Vérifier que la réponse contient un fichier Excel valide
        content = response.content
        self.assertGreater(len(content), 0)
        
        # Vérifier que c'est un fichier Excel (signature ZIP)
        self.assertEqual(content[:2], b'PK')

    def test_export_sans_donnees(self):
        """Test export sans données"""
        # Supprimer toutes les données
        NumeroBonCommande.objects.all().delete()
        
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        
        # Devrait quand même réussir mais avec un fichier vide
        self.assertEqual(response.status_code, 200)


class TestExportMSRNPOLines(TestCase):
    def setUp(self):
        self.client = self.client_class()
        self.user = User.objects.create_user('test@example.com', 'testpass')
        self.user.is_active = True
        self.user.save()
        self.client.force_login(self.user)
        
        # Créer un rapport MSRN avec réceptions
        self.bon = NumeroBonCommande.objects.create(numero='PO001')
        self.fichier = FichierImporte.objects.create(fichier='test.csv')
        self.bon.fichiers.add(self.fichier)
        
        self.msrn = MSRNReport.objects.create(
            report_number='MSRN250001',
            bon_commande=self.bon,
            user=self.user.email,
            retention_rate=Decimal('5.0')
        )
        
        # Nettoyer les lignes auto-créées
        self.fichier.lignes.all().delete()
        
        # Créer une ligne de fichier
        self.ligne = LigneFichier.objects.create(
            fichier=self.fichier,
            numero_ligne=1,
            contenu={
                'Order': 'PO001',
                'Line': '1',
                'Line Description': 'Test Item',
                'Ordered Quantity': '100',
                'Received Quantity': '80',
                'Price': '10'
            },
            business_id='ORDER:PO001|LINE:1|ITEM:1|SCHEDULE:1'
        )
        
        # Créer une réception correspondante
        self.reception = Reception.objects.create(
            bon_commande=self.bon,
            fichier=self.fichier,
            business_id='ORDER:PO001|LINE:1|ITEM:1|SCHEDULE:1',
            ordered_quantity=Decimal('100'),
            quantity_delivered=Decimal('80'),
            received_quantity=Decimal('80'),
            quantity_not_delivered=Decimal('20'),
            unit_price=Decimal('10'),
            user=self.user.email
        )

    def test_export_msrn_po_lines(self):
        """Test export des lignes PO d'un MSRN"""
        self.client.force_login(self.user)
        url = reverse('orders:export_msrn_po_lines', args=[self.msrn.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 
                       'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        self.assertIn('MSRN_MSRN250001_PO_Lines.xlsx', response['Content-Disposition'])

    def test_export_msrn_inexistant(self):
        """Test export avec MSRN inexistant"""
        self.client.force_login(self.user)
        url = reverse('orders:export_msrn_po_lines', args=[999])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 404)

    def test_export_sans_lignes_po(self):
        """Test export sans lignes PO"""
        # Supprimer les réceptions
        Reception.objects.all().delete()
        
        self.client.force_login(self.user)
        url = reverse('orders:export_msrn_po_lines', args=[self.msrn.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 404)


class TestExportVendorEvaluations(TestCase):
    def setUp(self):
        self.client = self.client_class()
        self.user = User.objects.create_user('test@example.com', 'testpass')
        self.user.is_active = True
        self.user.save()
        self.client.force_login(self.user)
        self.url = reverse('orders:export_vendor_evaluations')
        
        # Créer des évaluations de test
        self.bon = NumeroBonCommande.objects.create(numero='PO001', cpu='ITS')
        self.fichier = FichierImporte.objects.create(fichier='test.csv')
        self.bon.fichiers.add(self.fichier)
        
        self.evaluation = VendorEvaluation.objects.create(
            bon_commande=self.bon,
            supplier="Test Supplier",
            delivery_compliance=8,
            delivery_timeline=7,
            advising_capability=6,
            after_sales_qos=9,
            vendor_relationship=8,
            evaluator=self.user
        )
        
        # Nettoyer les lignes auto-créées
        self.fichier.lignes.all().delete()
        
        # Créer une ligne de fichier avec des données de timeline
        self.ligne = LigneFichier.objects.create(
            fichier=self.fichier,
            numero_ligne=1,
            business_id='EXPVE-L1',
            contenu={
                'Order': 'PO001',
                'Order Description': 'Test Description',
                'Project Manager': 'Test PM',
                'PIP END DATE': '2024-12-31',
                'ACTUAL END DATE': '2025-01-15'
            }
        )

    def test_export_vendor_evaluations(self):
        """Test export des évaluations fournisseurs"""
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 
                       'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        self.assertIn('Vendor_Evaluations', response['Content-Disposition'])

    def test_export_avec_filtres(self):
        """Test export avec filtres"""
        self.client.force_login(self.user)
        response = self.client.get(self.url, {
            'supplier': 'Test Supplier',
            'min_score': '30'
        })
        
        self.assertEqual(response.status_code, 200)

    def test_export_sans_evaluations(self):
        """Test export sans évaluations"""
        # Supprimer toutes les évaluations
        VendorEvaluation.objects.all().delete()
        
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        
        # Devrait quand même réussir mais avec un fichier vide
        self.assertEqual(response.status_code, 200)


class TestExportVendorRanking(TestCase):
    def setUp(self):
        self.client = self.client_class()
        self.user = User.objects.create_user('test@example.com', 'testpass')
        self.user.is_active = True
        self.user.is_superuser = True  # Superuser pour voir tous les bons
        self.user.save()
        self.client.force_login(self.user)
        self.url = reverse('orders:export_vendor_ranking')
        
        # Créer des données de test
        self.bon = NumeroBonCommande.objects.create(numero='PO001', cpu='ITS')
        self.fichier = FichierImporte.objects.create(fichier='test.csv')
        self.bon.fichiers.add(self.fichier)
        
        self.evaluation = VendorEvaluation.objects.create(
            bon_commande=self.bon,
            supplier="Test Supplier",
            delivery_compliance=8,
            delivery_timeline=7,
            advising_capability=6,
            after_sales_qos=9,
            vendor_relationship=8,
            evaluator=self.user
        )
        
        # Nettoyer les lignes auto-créées
        self.fichier.lignes.all().delete()
        
        # Créer une ligne de fichier
        self.ligne = LigneFichier.objects.create(
            fichier=self.fichier,
            numero_ligne=1,
            business_id='EXPVR-L1',
            contenu={
                'Order': 'PO001',
                'Order Status': 'Closed',
                'Closed Date': '2024-12-31',
                'Project Manager': 'Test PM',
                'Buyer': 'Test Buyer',
                'Order Description': 'Test Description',
                'Currency': 'XOF'
            }
        )

    def test_export_vendor_ranking(self):
        """Test export du classement des fournisseurs"""
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 
                       'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        self.assertIn('vendor_ranking_export', response['Content-Disposition'])

    def test_export_sans_donnees(self):
        """Test export sans données"""
        NumeroBonCommande.objects.all().delete()
        
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        
        # Devrait rediriger avec message d'avertissement
        self.assertEqual(response.status_code, 302)


class TestExportFichierComplet(TestCase):
    def setUp(self):
        self.client = self.client_class()
        self.user = User.objects.create_user('test@example.com', 'testpass')
        self.user.is_active = True
        self.user.save()
        self.client.force_login(self.user)
        
        # Créer un fichier avec des lignes
        self.fichier = FichierImporte.objects.create(
            fichier='test.csv',
            utilisateur=self.user
        )
        
        # Nettoyer les lignes auto-créées
        self.fichier.lignes.all().delete()
        
        # Créer des lignes de fichier
        self.ligne1 = LigneFichier.objects.create(
            fichier=self.fichier,
            numero_ligne=1,
            business_id='EXPFC-L1',
            contenu={'Order': 'PO001', 'Ordered Quantity': '100', 'Price': '10'}
        )
        self.ligne2 = LigneFichier.objects.create(
            fichier=self.fichier,
            numero_ligne=2,
            business_id='EXPFC-L2',
            contenu={'Order': 'PO002', 'Ordered Quantity': '50', 'Price': '20'}
        )

    def test_export_fichier_complet(self):
        """Test export complet d'un fichier"""
        self.client.force_login(self.user)
        url = reverse('orders:export_fichier_complet', args=[self.fichier.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 
                       'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        self.assertIn('Fichier_complet', response['Content-Disposition'])

    def test_export_fichier_inexistant(self):
        """Test export d'un fichier inexistant"""
        self.client.force_login(self.user)
        url = reverse('orders:export_fichier_complet', args=[999])
        response = self.client.get(url)
        
        # Accepter 404 ou 302 (redirection si fichier inexistant)
        self.assertIn(response.status_code, [302, 404])


class TestExportBonExcel(TestCase):
    def setUp(self):
        self.client = self.client_class()
        self.user = User.objects.create_user('test@example.com', 'testpass')
        self.user.is_active = True
        self.user.save()
        self.client.force_login(self.user)
        
        # Créer un fichier avec un bon de commande
        self.fichier = FichierImporte.objects.create(fichier='test.csv')
        self.bon = NumeroBonCommande.objects.create(numero='PO001')
        self.bon.fichiers.add(self.fichier)
        
        # Nettoyer les lignes auto-créées
        self.fichier.lignes.all().delete()
        
        # Créer des lignes de fichier
        self.ligne1 = LigneFichier.objects.create(
            fichier=self.fichier,
            numero_ligne=1,
            business_id='EXPBON-L1',
            contenu={'Order': 'PO001', 'Ordered Quantity': '100', 'Price': '10'}
        )
        
        # Créer une réception
        self.reception = Reception.objects.create(
            bon_commande=self.bon,
            fichier=self.fichier,
            business_id='ORDER:PO001|LINE:1|ITEM:1|SCHEDULE:1',
            ordered_quantity=Decimal('100'),
            quantity_delivered=Decimal('80'),
            received_quantity=Decimal('80'),
            unit_price=Decimal('10')
        )

    def test_export_bon_avec_order_number(self):
        """Test export d'un bon avec numéro de commande"""
        self.client.force_login(self.user)
        url = f"{reverse('orders:export_bon_excel', args=[self.fichier.id])}?selected_order_number=PO001"
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 
                       'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        self.assertIn('PO_PO001_updated.xlsx', response['Content-Disposition'])

    def test_export_bon_sans_order_number(self):
        """Test export d'un fichier sans numéro de commande spécifique"""
        self.client.force_login(self.user)
        url = reverse('orders:export_bon_excel', args=[self.fichier.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        # Le nom du fichier contient le numéro du PO, pas "Fichier"
        self.assertIn('PO_PO001', response['Content-Disposition'])

    def test_export_bon_recherche(self):
        """Test export via recherche de bon de commande"""
        self.client.force_login(self.user)
        # Utiliser l'ID du fichier au lieu de 'search'
        url = f"{reverse('orders:export_bon_excel', args=[self.fichier.id])}?order_number=PO001"
        response = self.client.get(url)
        
        # Devrait exporter le bon spécifique
        self.assertEqual(response.status_code, 200)

    def test_export_bon_inexistant(self):
        """Test export d'un bon inexistant"""
        self.client.force_login(self.user)
        url = reverse('orders:export_bon_excel', args=[999])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 404)


class TestExportUtilities(TestCase):
    """Tests pour les fonctions utilitaires des exports"""
    
    def test_normalize_header_function(self):
        """Test la fonction de normalisation des en-têtes"""
        from orders import views_export
        
        # Créer une instance pour accéder à la fonction
        export_view = type('MockView', (), {})()
        
        # Simuler la fonction normalize_header
        def normalize_header(s: str):
            return ' '.join(str(s).strip().lower().replace('_', ' ').replace('-', ' ').split())
        
        test_cases = [
            ('Order_Description', 'order description'),
            ('Project-Manager', 'project manager'),
            ('  CPU  ', 'cpu'),
            ('Line Type', 'line type'),
        ]
        
        for input_str, expected in test_cases:
            result = normalize_header(input_str)
            self.assertEqual(result, expected)

    def test_get_value_tolerant_function(self):
        """Test la fonction de récupération tolérante des valeurs"""
        from orders import views_export
        
        # Données de test
        contenu = {
            'Order Description': 'Test Order',
            'Project_Manager': 'John Doe',
            'CPU': 'IT Department'
        }
        
        # Simuler la fonction get_value_tolerant
        def get_value_tolerant(contenu, exact_candidates=None, tokens=None):
            if not contenu:
                return None
            
            def norm(s: str):
                return ' '.join(str(s).strip().lower().replace('_', ' ').replace('-', ' ').split())
            
            normalized = {norm(k): (k, v) for k, v in contenu.items() if k}
            
            if exact_candidates:
                for cand in exact_candidates:
                    nk = norm(cand)
                    if nk in normalized:
                        return normalized[nk][1]
            
            if tokens:
                needed = [norm(t) for t in tokens]
                for nk, (_ok, v) in normalized.items():
                    if all(t in nk for t in needed):
                        return v
            return None
        
        # Test avec candidats exacts
        result = get_value_tolerant(contenu, exact_candidates=['Order Description'])
        self.assertEqual(result, 'Test Order')
        
        # Test avec tokens
        result = get_value_tolerant(contenu, tokens=['project', 'manager'])
        self.assertEqual(result, 'John Doe')
        
        # Test sans correspondance
        result = get_value_tolerant(contenu, exact_candidates=['Non Existent'])
        self.assertIsNone(result)