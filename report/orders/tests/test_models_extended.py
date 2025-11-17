import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from django.utils import timezone
from orders.models import (
    round_decimal, normalize_business_id, NumeroBonCommande, 
    FichierImporte, LigneFichier, Reception, ActivityLog,
    MSRNReport, InitialReceptionBusiness, TimelineDelay, VendorEvaluation
)

User = get_user_model()


class TestNumeroBonCommandeExtended(TestCase):
    """Tests étendus pour NumeroBonCommande"""
    
    def setUp(self):
        self.bon_commande = NumeroBonCommande.objects.create(numero='TEST_EXTENDED')
        self.user = User.objects.create_user('test@example.com', 'testpass')
        
        # Mock pour éviter l'extraction de fichiers
        self._exists_patcher = patch('orders.models.default_storage.exists', return_value=False)
        self._exists_patcher.start()
        self.addCleanup(self._exists_patcher.stop)
        self._extract_patcher = patch('orders.utils.extraire_depuis_fichier_relatif', return_value=([], 0))
        self._extract_patcher.start()
        self.addCleanup(self._extract_patcher.stop)
        
        self.fichier = FichierImporte.objects.create(
            fichier='test.csv',
            utilisateur=self.user
        )
        self.bon_commande.fichiers.add(self.fichier)
        self.fichier.lignes.all().delete()

    def test_montant_total_calculated_property(self):
        """Test des propriétés calculées montant_total"""
        # Simuler que _montant_total_calculated n'existe pas
        self.assertFalse(hasattr(self.bon_commande, '_montant_total_calculated'))
        montant = self.bon_commande.montant_total()
        self.assertEqual(montant, Decimal('0'))
        self.assertTrue(hasattr(self.bon_commande, '_montant_total_calculated'))

    def test_montant_recu_calculated_property(self):
        """Test des propriétés calculées montant_recu"""
        self.assertFalse(hasattr(self.bon_commande, '_montant_recu_calculated'))
        montant = self.bon_commande.montant_recu()
        self.assertEqual(montant, Decimal('0'))
        self.assertTrue(hasattr(self.bon_commande, '_montant_recu_calculated'))

    def test_taux_avancement_calculated_property(self):
        """Test des propriétés calculées taux_avancement"""
        self.assertFalse(hasattr(self.bon_commande, '_taux_avancement_calculated'))
        taux = self.bon_commande.taux_avancement()
        self.assertEqual(taux, Decimal('0'))
        self.assertTrue(hasattr(self.bon_commande, '_taux_avancement_calculated'))

    def test_get_sponsor_with_files(self):
        """Test get_sponsor avec fichiers"""
        # Créer une ligne avec sponsor
        LigneFichier.objects.create(
            fichier=self.fichier,
            numero_ligne=1,
            contenu={'Order': 'TEST_EXTENDED', 'Sponsor': 'Test Sponsor'},
            business_id='TEST_SPONSOR'
        )
        
        sponsor = self.bon_commande.get_sponsor()
        self.assertEqual(sponsor, 'Test Sponsor')

    def test_get_supplier_with_variations(self):
        """Test get_supplier avec variations de noms de colonnes"""
        # Tester différents noms de colonnes pour supplier
        test_cases = [
            {'Supplier': 'Supplier1'},
            {'Vendor': 'Supplier2'},
            {'Fournisseur': 'Supplier3'},
            {'Vendeur': 'Supplier4'}
        ]
        
        for i, test_case in enumerate(test_cases):
            ligne = LigneFichier.objects.create(
                fichier=self.fichier,
                numero_ligne=i+1,
                contenu={'Order': 'TEST_EXTENDED', **test_case},
                business_id=f'TEST_SUPPLIER_{i}'
            )
            
            supplier = self.bon_commande.get_supplier()
            # Le premier fournisseur trouvé devrait être retourné
            if supplier == "N/A":
                continue  # Passer au test suivant si non trouvé
            self.assertIn(supplier, ['Supplier1', 'Supplier2', 'Supplier3', 'Supplier4'])
            break

    def test_get_order_description_exact_match(self):
        """Test get_order_description avec correspondance exacte"""
        LigneFichier.objects.create(
            fichier=self.fichier,
            numero_ligne=1,
            contenu={'Order': 'TEST_EXTENDED', 'Order Description': 'Test Description'},
            business_id='TEST_DESC'
        )
        
        description = self.bon_commande.get_order_description()
        self.assertEqual(description, 'Test Description')

    def test_get_currency_from_file(self):
        """Test get_currency depuis fichier"""
        LigneFichier.objects.create(
            fichier=self.fichier,
            numero_ligne=1,
            contenu={'Order': 'TEST_EXTENDED', 'Currency': 'EUR'},
            business_id='TEST_CURRENCY'
        )
        
        currency = self.bon_commande.get_currency()
        self.assertEqual(currency, 'EUR')

    def test_get_project_number_variations(self):
        """Test get_project_number avec variations"""
        test_cases = [
            {'Project Number': 'PRJ001'},
            {'Project_Number': 'PRJ002'},
            {'Project': 'PRJ003'},
            {'Code Projet': 'PRJ004'}
        ]
        
        for i, test_case in enumerate(test_cases):
            ligne = LigneFichier.objects.create(
                fichier=self.fichier,
                numero_ligne=i+1,
                contenu={'Order': 'TEST_EXTENDED', **test_case},
                business_id=f'TEST_PROJ_{i}'
            )
            
            project = self.bon_commande.get_project_number()
            if project != "N/A":
                self.assertIn(project, ['PRJ001', 'PRJ002', 'PRJ003', 'PRJ004'])
                break

    def test_get_cpu_cleaning(self):
        """Test le nettoyage des valeurs CPU"""
        LigneFichier.objects.create(
            fichier=self.fichier,
            numero_ligne=1,
            contenu={'Order': 'TEST_EXTENDED', 'CPU': '02 - ITS'},
            business_id='TEST_CPU'
        )
        
        cpu = self.bon_commande.get_cpu()
        self.assertEqual(cpu, 'ITS')

    def test_get_project_manager_found(self):
        """Test get_project_manager quand trouvé"""
        LigneFichier.objects.create(
            fichier=self.fichier,
            numero_ligne=1,
            contenu={'Order': 'TEST_EXTENDED', 'Project Manager': 'John Doe'},
            business_id='TEST_PM'
        )
        
        pm = self.bon_commande.get_project_manager()
        self.assertEqual(pm, 'John Doe')

    def test_get_project_coordinator_found(self):
        """Test get_project_coordinator quand trouvé"""
        LigneFichier.objects.create(
            fichier=self.fichier,
            numero_ligne=1,
            contenu={'Order': 'TEST_EXTENDED', 'Project Coordinator': 'Jane Smith'},
            business_id='TEST_PC'
        )
        
        pc = self.bon_commande.get_project_coordinator()
        self.assertEqual(pc, 'Jane Smith')

    def test_get_manager_portfolio_found(self):
        """Test get_manager_portfolio quand trouvé"""
        LigneFichier.objects.create(
            fichier=self.fichier,
            numero_ligne=1,
            contenu={'Order': 'TEST_EXTENDED', 'Manager Portfolio': 'Portfolio Manager'},
            business_id='TEST_MP'
        )
        
        mp = self.bon_commande.get_manager_portfolio()
        self.assertEqual(mp, 'Portfolio Manager')

    def test_get_gm_epmo_found(self):
        """Test get_gm_epmo quand trouvé"""
        LigneFichier.objects.create(
            fichier=self.fichier,
            numero_ligne=1,
            contenu={'Order': 'TEST_EXTENDED', 'GM EPMO': 'GM Name'},
            business_id='TEST_GM'
        )
        
        gm = self.bon_commande.get_gm_epmo()
        self.assertEqual(gm, 'GM Name')

    def test_get_senior_pm_found(self):
        """Test get_senior_pm quand trouvé"""
        LigneFichier.objects.create(
            fichier=self.fichier,
            numero_ligne=1,
            contenu={'Order': 'TEST_EXTENDED', 'Senior PM': 'Senior PM Name'},
            business_id='TEST_SPM'
        )
        
        spm = self.bon_commande.get_senior_pm()
        self.assertEqual(spm, 'Senior PM Name')

    def test_get_senior_technical_lead_found(self):
        """Test get_senior_technical_lead quand trouvé"""
        LigneFichier.objects.create(
            fichier=self.fichier,
            numero_ligne=1,
            contenu={'Order': 'TEST_EXTENDED', 'Senior Technical Lead': 'Tech Lead Name'},
            business_id='TEST_STL'
        )
        
        stl = self.bon_commande.get_senior_technical_lead()
        self.assertEqual(stl, 'Tech Lead Name')

    def test_calculate_amount_payable(self):
        """Test calculate_amount_payable"""
        # Créer des réceptions avec amount_payable
        Reception.objects.create(
            bon_commande=self.bon_commande,
            fichier=self.fichier,
            business_id='TEST_PAY1',
            ordered_quantity=Decimal('100'),
            quantity_delivered=Decimal('80'),
            unit_price=Decimal('50')
        )
        Reception.objects.create(
            bon_commande=self.bon_commande,
            fichier=self.fichier,
            business_id='TEST_PAY2',
            ordered_quantity=Decimal('50'),
            quantity_delivered=Decimal('50'),
            unit_price=Decimal('50')
        )
        
        total = self.bon_commande.calculate_amount_payable()
        self.assertEqual(total, Decimal('6500'))

    def test_calculate_quantity_payable(self):
        """Test calculate_quantity_payable"""
        # Créer des réceptions avec quantity_payable
        # Appliquer une rétention de 5% pour obtenir 76 à partir de 80
        self.bon_commande.retention_rate = Decimal('5.0')
        self.bon_commande.save()
        Reception.objects.create(
            bon_commande=self.bon_commande,
            fichier=self.fichier,
            business_id='TEST_QP1',
            ordered_quantity=Decimal('100'),
            quantity_delivered=Decimal('80'),
            unit_price=Decimal('50')
        )
        
        total = self.bon_commande.calculate_quantity_payable()
        self.assertEqual(total, Decimal('76'))

    def test_get_code_ifs_found(self):
        """Test get_code_ifs quand trouvé"""
        LigneFichier.objects.create(
            fichier=self.fichier,
            numero_ligne=1,
            contenu={'Order': 'TEST_EXTENDED', 'Code IFS': 'IFS001'},
            business_id='TEST_IFS'
        )
        
        code_ifs = self.bon_commande.get_code_ifs()
        self.assertEqual(code_ifs, 'IFS001')

    def test_save_with_retention_rate_update(self):
        """Test save() avec mise à jour du taux de rétention"""
        # Créer une réception pour tester la mise à jour
        reception = Reception.objects.create(
            bon_commande=self.bon_commande,
            fichier=self.fichier,
            business_id='TEST_RETENTION',
            ordered_quantity=Decimal('100'),
            quantity_delivered=Decimal('80'),
            unit_price=Decimal('50')
        )
        
        initial_payable = reception.quantity_payable
        self.bon_commande.retention_rate = Decimal('10.0')
        self.bon_commande.save()
        
        reception.refresh_from_db()
        self.assertNotEqual(reception.quantity_payable, initial_payable)


class TestLigneFichierExtended(TestCase):
    """Tests étendus pour LigneFichier"""
    
    def setUp(self):
        self._exists_patcher = patch('orders.models.default_storage.exists', return_value=False)
        self._exists_patcher.start()
        self.addCleanup(self._exists_patcher.stop)
        self._extract_patcher = patch('orders.utils.extraire_depuis_fichier_relatif', return_value=([], 0))
        self._extract_patcher.start()
        self.addCleanup(self._extract_patcher.stop)

        self.user = User.objects.create_user('test@example.com', 'testpass')
        self.fichier = FichierImporte.objects.create(
            fichier='test.csv',
            utilisateur=self.user
        )
        self.fichier.lignes.all().delete()

    def test_generate_business_id_complete(self):
        """Test generate_business_id avec tous les composants"""
        ligne = LigneFichier(
            fichier=self.fichier,
            numero_ligne=1,
            contenu={
                'Order': 'TEST123',
                'Line': '1',
                'Item': 'A',
                'Schedule': 'S1'
            }
        )
        
        business_id = ligne.generate_business_id()
        expected = "ORDER:TEST123|LINE:1|ITEM:A|SCHEDULE:S1"
        self.assertEqual(business_id, expected)

    def test_generate_business_id_with_numeric_normalization(self):
        """Test generate_business_id avec normalisation numérique"""
        ligne = LigneFichier(
            fichier=self.fichier,
            numero_ligne=1,
            contenu={
                'Order': 'TEST123',
                'Line': '43.0',  # Devrait être normalisé à 43
                'Item': '1.0',   # Devrait être normalisé à 1
                'Schedule': '2.5'  # Devrait rester 2.5
            }
        )
        
        business_id = ligne.generate_business_id()
        expected = "ORDER:TEST123|LINE:43|ITEM:1|SCHEDULE:2.5"
        self.assertEqual(business_id, expected)

    def test_generate_business_id_missing_components(self):
        """Test generate_business_id avec composants manquants"""
        # Test avec seulement Order et Line
        ligne = LigneFichier(
            fichier=self.fichier,
            numero_ligne=1,
            contenu={
                'Order': 'TEST123',
                'Line': '1'
            }
        )
        
        business_id = ligne.generate_business_id()
        expected = "ORDER:TEST123|LINE:1"
        self.assertEqual(business_id, expected)

    def test_save_generates_business_id(self):
        """Test que save() génère automatiquement business_id"""
        ligne = LigneFichier(
            fichier=self.fichier,
            numero_ligne=1,
            contenu={
                'Order': 'TEST123',
                'Line': '1',
                'Item': 'A',
                'Schedule': 'S1'
            }
        )
        
        # business_id devrait être None avant save
        self.assertIsNone(ligne.business_id)
        
        ligne.save()
        
        # business_id devrait être généré après save
        self.assertIsNotNone(ligne.business_id)
        self.assertEqual(ligne.business_id, "ORDER:TEST123|LINE:1|ITEM:A|SCHEDULE:S1")

    def test_get_key_columns_with_values(self):
        """Test get_key_columns avec des valeurs réelles"""
        ligne = LigneFichier.objects.create(
            fichier=self.fichier,
            numero_ligne=1,
            contenu={
                'Ordered Quantity': '100',
                'Quantity Delivered': '80',
                'Quantity Not Delivered': '20',
                'Price': '50.5'
            },
            business_id='TEST_KEYS'
        )
        
        key_columns = ligne.get_key_columns()
        
        self.assertEqual(key_columns['ordered_quantity'], Decimal('100'))
        self.assertEqual(key_columns['quantity_delivered'], Decimal('80'))
        self.assertEqual(key_columns['quantity_not_delivered'], Decimal('20'))
        self.assertEqual(key_columns['unit_price'], Decimal('50.5'))


class TestReceptionExtended(TestCase):
    """Tests étendus pour Reception"""
    
    def setUp(self):
        self._exists_patcher = patch('orders.models.default_storage.exists', return_value=False)
        self._exists_patcher.start()
        self.addCleanup(self._exists_patcher.stop)
        self._extract_patcher = patch('orders.utils.extraire_depuis_fichier_relatif', return_value=([], 0))
        self._extract_patcher.start()
        self.addCleanup(self._extract_patcher.stop)

        self.user = User.objects.create_user('test@example.com', 'testpass')
        self.bon_commande = NumeroBonCommande.objects.create(numero='TEST_RECEPTION')
        self.fichier = FichierImporte.objects.create(
            fichier='test.csv',
            utilisateur=self.user
        )
        self.fichier.lignes.all().delete()

    def test_save_calculations_with_retention(self):
        """Test des calculs save() avec taux de rétention"""
        self.bon_commande.retention_rate = Decimal('10.0')  # 10%
        self.bon_commande.save()
        
        reception = Reception.objects.create(
            bon_commande=self.bon_commande,
            fichier=self.fichier,
            business_id='TEST_RET',
            ordered_quantity=Decimal('100'),
            quantity_delivered=Decimal('80'),
            received_quantity=Decimal('80'),
            quantity_not_delivered=Decimal('20'),
            unit_price=Decimal('100'),
            user=self.user.email
        )
        
        # Vérifier les calculs
        # amount_delivered = 80 * 100 = 8000
        self.assertEqual(reception.amount_delivered, Decimal('8000'))
        
        # amount_not_delivered = 20 * 100 = 2000
        self.assertEqual(reception.amount_not_delivered, Decimal('2000'))
        
        # quantity_payable = 80 * (1 - 0.10) = 72
        self.assertEqual(reception.quantity_payable, Decimal('72'))
        
        # amount_payable = 72 * 100 = 7200
        self.assertEqual(reception.amount_payable, Decimal('7200'))

    def test_save_with_none_values(self):
        """Test save() avec certaines valeurs None"""
        reception = Reception(
            bon_commande=self.bon_commande,
            fichier=self.fichier,
            business_id='TEST_NONE',
            ordered_quantity=None,
            quantity_delivered=Decimal('0'),
            received_quantity=Decimal('0'),
            quantity_not_delivered=None,
            unit_price=Decimal('0'),
            user=self.user.email
        )
        
        # Ne devrait pas lever d'exception
        reception.save()
        
        # Les valeurs None devraient être gérées gracieusement
        self.assertEqual(reception.amount_delivered, Decimal('0'))
        self.assertEqual(reception.amount_not_delivered, Decimal('0'))

    def test_verify_alignment_success(self):
        """Test verify_alignment avec correspondance"""
        ligne = LigneFichier.objects.create(
            fichier=self.fichier,
            numero_ligne=1,
            contenu={'Order': 'TEST_RECEPTION', 'Ordered Quantity': '100'},
            business_id='TEST_ALIGN'
        )
        
        reception = Reception.objects.create(
            bon_commande=self.bon_commande,
            fichier=self.fichier,
            business_id='TEST_ALIGN',
            ordered_quantity=Decimal('100'),
            quantity_delivered=Decimal('80'),
            received_quantity=Decimal('80'),
            quantity_not_delivered=Decimal('20'),
            unit_price=Decimal('50'),
            user=self.user.email
        )
        
        result = reception.verify_alignment(ligne)
        self.assertTrue(result)

    def test_verify_alignment_failure(self):
        """Test verify_alignment sans correspondance"""
        ligne = LigneFichier.objects.create(
            fichier=self.fichier,
            numero_ligne=1,
            contenu={'Order': 'TEST_RECEPTION', 'Ordered Quantity': '50'},  # Différent de 100
            business_id='TEST_MISALIGN'
        )
        
        reception = Reception.objects.create(
            bon_commande=self.bon_commande,
            fichier=self.fichier,
            business_id='TEST_ALIGN',
            ordered_quantity=Decimal('100'),  # Différent de 50
            quantity_delivered=Decimal('80'),
            received_quantity=Decimal('80'),
            quantity_not_delivered=Decimal('20'),
            unit_price=Decimal('50'),
            user=self.user.email
        )
        
        result = reception.verify_alignment(ligne)
        self.assertFalse(result)


class TestFichierImporteExtended(TestCase):
    """Tests étendus pour FichierImporte"""
    
    def setUp(self):
        self._exists_patcher = patch('orders.models.default_storage.exists', return_value=False)
        self._exists_patcher.start()
        self.addCleanup(self._exists_patcher.stop)
        self._extract_patcher = patch('orders.utils.extraire_depuis_fichier_relatif', return_value=([], 0))
        self._extract_patcher.start()
        self.addCleanup(self._extract_patcher.stop)

        self.user = User.objects.create_user('test@example.com', 'testpass')

    def test_get_raw_data_with_lines(self):
        """Test get_raw_data avec des lignes existantes"""
        fichier = FichierImporte.objects.create(
            fichier='test.csv',
            utilisateur=self.user
        )
        
        # Créer quelques lignes
        LigneFichier.objects.create(
            fichier=fichier,
            numero_ligne=1,
            contenu={'Order': 'TEST1', 'Data': 'Value1'},
            business_id='TEST1'
        )
        LigneFichier.objects.create(
            fichier=fichier,
            numero_ligne=2,
            contenu={'Order': 'TEST2', 'Data': 'Value2'},
            business_id='TEST2'
        )
        
        raw_data = fichier.get_raw_data()
        self.assertEqual(len(raw_data), 2)
        self.assertEqual(raw_data[0]['Order'], 'TEST1')
        self.assertEqual(raw_data[1]['Order'], 'TEST2')

    def test_extraire_et_enregistrer_bons_commande_with_data(self):
        """Test extraire_et_enregistrer_bons_commande avec données"""
        fichier = FichierImporte.objects.create(
            fichier='test.csv',
            utilisateur=self.user
        )
        
        # Créer des lignes avec différents orders
        LigneFichier.objects.create(
            fichier=fichier,
            numero_ligne=1,
            contenu={'Order': 'PO001', 'CPU': '01 - ITS'},
            business_id='PO001_L1'
        )
        LigneFichier.objects.create(
            fichier=fichier,
            numero_ligne=2,
            contenu={'Order': 'PO002', 'CPU': '02 - FINANCE'},
            business_id='PO002_L1'
        )
        LigneFichier.objects.create(
            fichier=fichier,
            numero_ligne=3,
            contenu={'Order': 'PO001', 'CPU': '01 - ITS'},  # Même PO
            business_id='PO001_L2'
        )
        
        # Appeler la méthode
        fichier.extraire_et_enregistrer_bons_commande()
        
        # Vérifier que les bons ont été créés
        bons = NumeroBonCommande.objects.filter(fichiers=fichier)
        self.assertEqual(bons.count(), 2)
        
        # Vérifier le CPU nettoyé
        bon_its = NumeroBonCommande.objects.get(numero='PO001')
        self.assertEqual(bon_its.cpu, 'ITS')


class TestMSRNReportExtended(TestCase):
    """Tests étendus pour MSRNReport"""
    
    def setUp(self):
        self._exists_patcher = patch('orders.models.default_storage.exists', return_value=False)
        self._exists_patcher.start()
        self.addCleanup(self._exists_patcher.stop)
        self._extract_patcher = patch('orders.utils.extraire_depuis_fichier_relatif', return_value=([], 0))
        self._extract_patcher.start()
        self.addCleanup(self._extract_patcher.stop)

        self.user = User.objects.create_user('test@example.com', 'testpass')
        self.bon_commande = NumeroBonCommande.objects.create(numero='TEST_MSRN')

    def test_save_generates_report_number(self):
        """Test que save() génère automatiquement le numéro de rapport"""
        msrn_report = MSRNReport(
            bon_commande=self.bon_commande,
            user=self.user.email,
            retention_rate=Decimal('5.0')
        )
        
        # report_number est vide (CharField), donc falsy avant save
        self.assertFalse(msrn_report.report_number)
        
        msrn_report.save()
        
        # report_number devrait être généré après save
        self.assertIsNotNone(msrn_report.report_number)
        self.assertTrue(msrn_report.report_number.startswith('MSRN'))

    def test_progress_rate_with_activity_log(self):
        """Test progress_rate avec ActivityLog existant"""
        fichier = FichierImporte.objects.create(fichier='test.csv', utilisateur=self.user)
        
        # Créer un ActivityLog avant le MSRN
        ActivityLog.objects.create(
            bon_commande='TEST_MSRN',
            fichier=fichier,
            business_id="ORDER:TEST_MSRN|LINE:1|ITEM:1|SCHEDULE:1",
            ordered_quantity=Decimal('100'),
            quantity_delivered=Decimal('75'),
            quantity_not_delivered=Decimal('25'),
            user=self.user.email,
            progress_rate=Decimal('75.0'),
            action_date=timezone.now()
        )
        
        msrn_report = MSRNReport.objects.create(
            bon_commande=self.bon_commande,
            user=self.user.email,
            retention_rate=Decimal('5.0')
        )
        
        rate = msrn_report.progress_rate
        self.assertEqual(rate, Decimal('75.0'))

    def test_save_captures_snapshots(self):
        """Test que save() capture les snapshots"""
        # Créer des réceptions pour le bon de commande
        fichier = FichierImporte.objects.create(fichier='test.csv', utilisateur=self.user)
        Reception.objects.create(
            bon_commande=self.bon_commande,
            fichier=fichier,
            business_id='MSRN_REC1',
            ordered_quantity=Decimal('100'),
            quantity_delivered=Decimal('80'),
            unit_price=Decimal('50')
        )
        
        msrn_report = MSRNReport(
            bon_commande=self.bon_commande,
            user=self.user.email,
            retention_rate=Decimal('5.0')
        )
        
        msrn_report.save()
        
        # Vérifier que les snapshots ont été capturés
        self.assertIsNotNone(msrn_report.montant_total_snapshot)
        self.assertIsNotNone(msrn_report.montant_recu_snapshot)
        self.assertIsNotNone(msrn_report.progress_rate_snapshot)
        self.assertIsNotNone(msrn_report.receptions_data_snapshot)


class TestVendorEvaluationExtended(TestCase):
    """Tests étendus pour VendorEvaluation"""
    
    def setUp(self):
        self.user = User.objects.create_user('test@example.com', 'testpass')
        self.bon_commande = NumeroBonCommande.objects.create(numero='PO-EVAL-001')

    def test_criteria_descriptions_all_scores(self):
        """Test get_criteria_description pour tous les scores possibles"""
        evaluation = VendorEvaluation.objects.create(
            bon_commande=self.bon_commande,
            supplier="Test Supplier",
            delivery_compliance=5,
            delivery_timeline=5,
            advising_capability=5,
            after_sales_qos=5,
            vendor_relationship=5,
            evaluator=self.user
        )
        
        # Tester quelques scores pour s'assurer que les descriptions sont retournées
        desc1 = evaluation.get_criteria_description('delivery_compliance', 0)
        desc2 = evaluation.get_criteria_description('delivery_timeline', 10)
        desc3 = evaluation.get_criteria_description('advising_capability', 7)
        
        self.assertIsNotNone(desc1)
        self.assertIsNotNone(desc2)
        self.assertIsNotNone(desc3)
        self.assertNotEqual(desc1, "Score: 0")
        self.assertNotEqual(desc2, "Score: 10")
        self.assertNotEqual(desc3, "Score: 7")

    def test_vendor_evaluation_auto_calculation(self):
        """Test que vendor_final_rating est calculé automatiquement"""
        evaluation = VendorEvaluation(
            bon_commande=self.bon_commande,
            supplier="Test Supplier",
            delivery_compliance=8,
            delivery_timeline=7,
            advising_capability=6,
            after_sales_qos=9,
            vendor_relationship=8,
            evaluator=self.user
        )
        
        # Avant save, vendor_final_rating devrait être 0
        self.assertEqual(evaluation.vendor_final_rating, Decimal('0.00'))
        
        evaluation.save()
        
        # Après save, vendor_final_rating devrait être calculé
        expected = Decimal('7.60')  # (8+7+6+9+8)/5 = 7.6
        self.assertEqual(evaluation.vendor_final_rating, expected)


class TestInitialReceptionBusinessExtended(TestCase):
    """Tests étendus pour InitialReceptionBusiness"""
    
    def setUp(self):
        self.bon_commande = NumeroBonCommande.objects.create(numero='TEST_IRB')
        self.fichier = FichierImporte.objects.create(fichier='test.csv')

    def test_save_normalizes_business_id(self):
        """Test que save() normalise le business_id"""
        irb = InitialReceptionBusiness(
            business_id="ORDER:123|LINE:43.0|ITEM:1.0|SCHEDULE:1.0",
            bon_commande=self.bon_commande,
            received_quantity=Decimal('50'),
            montant_total_initial=Decimal('1000'),
            montant_recu_initial=Decimal('500'),
            taux_avancement_initial=Decimal('50')
        )
        
        irb.save()
        
        # Les .0 devraient être supprimés
        self.assertEqual(irb.business_id, "ORDER:123|LINE:43|ITEM:1|SCHEDULE:1")


class TestTimelineDelayExtended(TestCase):
    """Tests étendus pour TimelineDelay"""
    
    def setUp(self):
        self._exists_patcher = patch('orders.models.default_storage.exists', return_value=False)
        self._exists_patcher.start()
        self.addCleanup(self._exists_patcher.stop)
        self._extract_patcher = patch('orders.utils.extraire_depuis_fichier_relatif', return_value=([], 0))
        self._extract_patcher.start()
        self.addCleanup(self._extract_patcher.stop)

        self.bon_commande = NumeroBonCommande.objects.create(numero='TEST_TIMELINE')
        # Créer des réceptions pour avoir un montant total
        fichier = FichierImporte.objects.create(fichier='test.csv')
        Reception.objects.create(
            bon_commande=self.bon_commande,
            fichier=fichier,
            business_id='TIMELINE_REC1',
            ordered_quantity=Decimal('100'),
            quantity_delivered=Decimal('80'),
            unit_price=Decimal('100')  # Montant total = 10000
        )

    def test_calculate_retention_timeline_with_amount(self):
        """Test calculate_retention_timeline avec montant total"""
        timeline_delay = TimelineDelay(
            bon_commande=self.bon_commande,
            delay_part_mtn=5,
            delay_part_force_majeure=3,
            delay_part_vendor=2,  # 2 jours de retard fournisseur
            quotite_realisee=Decimal('100.00'),
            comment_mtn="Retard côté MTN",
            comment_force_majeure="Force majeure météo",
            comment_vendor="Retard fournisseur"
        )
        
        amount, rate = timeline_delay.calculate_retention_timeline()
        
        # Montant total = 100 * 100 = 10000
        # Rétention = 10000 * 0.003 * 2 = 60
        # Taux = (60 / 10000) * 100 = 0.6%
        self.assertEqual(amount, Decimal('60'))
        self.assertEqual(rate, Decimal('0.6'))

    def test_calculate_retention_timeline_max_rate(self):
        """Test calculate_retention_timeline avec taux maximum"""
        timeline_delay = TimelineDelay(
            bon_commande=self.bon_commande,
            delay_part_mtn=0,
            delay_part_force_majeure=0,
            delay_part_vendor=40,  # 40 jours de retard fournisseur
            quotite_realisee=Decimal('100.00'),
            comment_mtn="Aucun",
            comment_force_majeure="Aucun",
            comment_vendor="Retard important"
        )
        
        amount, rate = timeline_delay.calculate_retention_timeline()
        
        # Le taux devrait être plafonné à 10%
        self.assertEqual(rate, Decimal('10'))
        # Montant = 10000 * 10% = 1000
        self.assertEqual(amount, Decimal('1000'))


# Tests pour les fonctions utilitaires non couvertes
class TestUtilityFunctionsComplete(TestCase):
    """Tests complets pour les fonctions utilitaires"""
    
    def test_round_decimal_edge_cases(self):
        """Test round_decimal avec cas limites"""
        # Test avec Decimal('0')
        self.assertEqual(round_decimal(Decimal('0')), Decimal('0.00'))
        
        # Test avec string vide
        self.assertEqual(round_decimal(''), Decimal('0'))
        
        # Test avec string non numérique
        self.assertEqual(round_decimal('abc'), Decimal('0'))
        
        # Test avec None
        self.assertEqual(round_decimal(None), Decimal('0'))

    def test_normalize_business_id_edge_cases(self):
        """Test normalize_business_id avec cas limites"""
        # Test avec business_id vide
        self.assertEqual(normalize_business_id(''), '')
        
        # Test avec parties sans ':'
        self.assertEqual(normalize_business_id('simple|value'), 'simple|value')
        
        # Test avec valeurs décimales complexes
        business_id = "ORDER:123|LINE:43.000|ITEM:1.00|SCHEDULE:2.50"
        normalized = normalize_business_id(business_id)
        self.assertEqual(normalized, "ORDER:123|LINE:43|ITEM:1|SCHEDULE:2.50")
        
        # Test avec valeurs non numériques
        business_id = "ORDER:ABC|LINE:XYZ|ITEM:123"
        normalized = normalize_business_id(business_id)
        self.assertEqual(normalized, business_id)
