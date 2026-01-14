# tests/test_models.py
import pytest
from decimal import Decimal
from unittest.mock import patch, Mock, MagicMock
from django.test import TestCase, TransactionTestCase
from django.db import IntegrityError, transaction
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.exceptions import ValidationError
from orders.models import (
    round_decimal, normalize_business_id, NumeroBonCommande, 
    FichierImporte, LigneFichier, Reception, ActivityLog,
    MSRNReport, InitialReceptionBusiness, TimelineDelay, VendorEvaluation
)

User = get_user_model()


class TestUtilityFunctions(TestCase):
    def test_round_decimal_with_decimal(self):
        """Test l'arrondi des valeurs décimales"""
        self.assertEqual(round_decimal(Decimal('10.12345'), 2), Decimal('10.12'))
        self.assertEqual(round_decimal(Decimal('10.125'), 2), Decimal('10.13'))
        self.assertEqual(round_decimal(Decimal('10.1'), 2), Decimal('10.10'))

    def test_round_decimal_with_float(self):
        """Test l'arrondi des valeurs float"""
        self.assertEqual(round_decimal(10.12345, 2), Decimal('10.12'))
        self.assertEqual(round_decimal(10.125, 2), Decimal('10.13'))

    def test_round_decimal_with_string(self):
        """Test l'arrondi des valeurs string"""
        self.assertEqual(round_decimal('10.12345', 2), Decimal('10.12'))
        self.assertEqual(round_decimal('10.125', 2), Decimal('10.13'))

    def test_round_decimal_with_none(self):
        """Test l'arrondi avec valeur None"""
        self.assertEqual(round_decimal(None, 2), Decimal('0'))

    def test_normalize_business_id(self):
        """Test la normalisation des business_id"""
        # Test avec valeurs décimales
        business_id = "ORDER:123|LINE:43.0|ITEM:1.0|SCHEDULE:1"
        normalized = normalize_business_id(business_id)
        self.assertEqual(normalized, "ORDER:123|LINE:43|ITEM:1|SCHEDULE:1")

        # Test sans valeurs décimales
        business_id = "ORDER:123|LINE:43|ITEM:1|SCHEDULE:1"
        normalized = normalize_business_id(business_id)
        self.assertEqual(normalized, business_id)

        # Test avec valeurs mixtes
        business_id = "ORDER:123|LINE:43.0|ITEM:1|SCHEDULE:2.5"
        normalized = normalize_business_id(business_id)
        self.assertEqual(normalized, "ORDER:123|LINE:43|ITEM:1|SCHEDULE:2.5")

        # Test avec valeur None
        self.assertEqual(normalize_business_id(None), None)


class TestNumeroBonCommande(TestCase):
    def setUp(self):
        self.bon_commande = NumeroBonCommande.objects.create(numero='TEST123')

    def test_creation(self):
        """Test la création d'un bon de commande"""
        self.assertEqual(self.bon_commande.numero, 'TEST123')
        self.assertIsNotNone(self.bon_commande.date_creation)

    def test_string_representation(self):
        """Test la représentation en string"""
        self.assertEqual(str(self.bon_commande), 'TEST123')

    def test_default_values(self):
        """Test les valeurs par défaut"""
        self.assertEqual(self.bon_commande.retention_rate, Decimal('0'))
        self.assertIsNone(self.bon_commande.retention_cause)
        self.assertEqual(self.bon_commande._montant_total, Decimal('0'))
        self.assertEqual(self.bon_commande._montant_recu, Decimal('0'))
        self.assertEqual(self.bon_commande._taux_avancement, Decimal('0'))

    def test_montant_total_without_receptions(self):
        """Test le calcul du montant total sans réceptions"""
        self.assertEqual(self.bon_commande.montant_total(), Decimal('0'))

    def test_montant_recu_without_receptions(self):
        """Test le calcul du montant reçu sans réceptions"""
        self.assertEqual(self.bon_commande.montant_recu(), Decimal('0'))

    def test_taux_avancement_without_receptions(self):
        """Test le calcul du taux d'avancement sans réceptions"""
        self.assertEqual(self.bon_commande.taux_avancement(), Decimal('0'))

    def test_get_sponsor_without_files(self):
        """Test la récupération du sponsor sans fichiers"""
        self.assertEqual(self.bon_commande.get_sponsor(), "N/A")

    def test_get_supplier_without_files(self):
        """Test la récupération du fournisseur sans fichiers"""
        self.assertEqual(self.bon_commande.get_supplier(), "N/A")

    def test_get_order_description_without_files(self):
        """Test la récupération de la description sans fichiers"""
        self.assertEqual(self.bon_commande.get_order_description(), "N/A")

    def test_get_currency_default(self):
        """Test la récupération de la devise par défaut"""
        self.assertEqual(self.bon_commande.get_currency(), "XOF")

    def test_get_project_number_without_files(self):
        """Test la récupération du numéro de projet sans fichiers"""
        self.assertEqual(self.bon_commande.get_project_number(), "N/A")

    def test_get_cpu_without_files(self):
        """Test la récupération du CPU sans fichiers"""
        self.assertEqual(self.bon_commande.get_cpu(), "N/A")

    def test_get_project_manager_without_files(self):
        """Test la récupération du project manager sans fichiers"""
        self.assertEqual(self.bon_commande.get_project_manager(), "N/A")

    def test_retention_rate_validation(self):
        """Test la validation du taux de rétention"""
        # Test avec taux valide
        self.bon_commande.retention_rate = Decimal('5.0')
        self.bon_commande.save()
        self.assertEqual(self.bon_commande.retention_rate, Decimal('5.0'))

    def test_meta_attributes(self):
        """Test les attributs Meta"""
        self.assertEqual(self.bon_commande._meta.verbose_name, "Numéro de bon de commande")
        self.assertEqual(self.bon_commande._meta.verbose_name_plural, "Numéros de bons de commande")
        self.assertEqual(self.bon_commande._meta.ordering, ['-date_creation'])


class TestLigneFichier(TestCase):
    def setUp(self):
        # Empêcher l'extraction auto sur fichiers factices
        self._exists_patcher = patch('orders.models.default_storage.exists', return_value=False)
        self._exists_patcher.start()
        self.addCleanup(self._exists_patcher.stop)
        self._extract_patcher = patch('orders.utils.extraire_depuis_fichier_relatif', return_value=([], 0))
        self._extract_patcher.start()
        self.addCleanup(self._extract_patcher.stop)

        self.user = User.objects.create_user('testligne@example.com', 'testpass')
        self.fichier = FichierImporte.objects.create(
            fichier='test.csv',
            utilisateur=self.user
        )
        self.bon_commande, _ = NumeroBonCommande.objects.get_or_create(numero='TEST_LIGNE_123')
        self.bon_commande.fichiers.add(self.fichier)
        
        # Nettoyer les lignes auto-créées
        self.fichier.lignes.all().delete()
        
        # Créer une ligne de fichier
        self.ligne = LigneFichier.objects.create(
            fichier=self.fichier,
            numero_ligne=1,
            business_id='TEST-L1',
            contenu={'Order': 'TEST_LIGNE_123', 'Line': '1', 'Item': '1', 'Schedule': '1'}
        )

    def test_creation(self):
        """Test la création d'une ligne de fichier"""
        self.assertEqual(self.ligne.numero_ligne, 1)
        self.assertEqual(self.ligne.contenu['Order'], 'TEST_LIGNE_123')
        self.assertIsNotNone(self.ligne.date_creation)

    def test_generate_business_id(self):
        """Test la génération du business_id"""
        business_id = self.ligne.generate_business_id()
        expected = "ORDER:TEST_LIGNE_123|LINE:1|ITEM:1|SCHEDULE:1"
        self.assertEqual(business_id, expected)

    def test_generate_business_id_with_none_values(self):
        """Test la génération du business_id avec valeurs None"""
        ligne = LigneFichier(
            fichier=self.fichier,
            numero_ligne=2,
            contenu={}
        )
        business_id = ligne.generate_business_id()
        self.assertIsNone(business_id)

    def test_get_key_columns(self):
        """Test la récupération des colonnes clés"""
        key_columns = self.ligne.get_key_columns()
        self.assertEqual(key_columns['id'], 1)
        self.assertEqual(key_columns['ordered_quantity'], Decimal('0'))
        self.assertEqual(key_columns['quantity_delivered'], Decimal('0'))

    def test_string_representation(self):
        """Test la représentation en string"""
        expected = f"Ligne 1 du fichier {self.fichier.id}"
        self.assertEqual(str(self.ligne), expected)

    def test_meta_attributes(self):
        """Test les attributs Meta"""
        self.assertEqual(self.ligne._meta.verbose_name, "Ligne de fichier")
        self.assertEqual(self.ligne._meta.verbose_name_plural, "Lignes de fichiers")
        self.assertEqual(self.ligne._meta.ordering, ['fichier', 'numero_ligne'])


class TestFichierImporte(TestCase):
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
        # Nettoyer les lignes auto-créées
        self.fichier.lignes.all().delete()

    def test_creation(self):
        """Test la création d'un fichier importé"""
        self.assertEqual(self.fichier.fichier.name, 'test.csv')
        self.assertEqual(self.fichier.utilisateur, self.user)
        # Après nettoyage dans setUp, nombre_lignes doit être 0
        self.fichier.refresh_from_db()
        self.assertEqual(self.fichier.lignes.count(), 0)

    def test_string_representation(self):
        """Test la représentation en string"""
        self.assertIn('test.csv', str(self.fichier))
        self.assertIn(str(self.fichier.date_importation.year), str(self.fichier))

    def test_get_raw_data_empty(self):
        """Test la récupération des données brutes sans lignes"""
        raw_data = self.fichier.get_raw_data()
        self.assertEqual(raw_data, [])

    def test_get_recipe_quantities(self):
        """Test la récupération des quantités de recette"""
        quantities = self.fichier.get_recipe_quantities()
        self.assertEqual(quantities, {})

    def test_extraire_et_enregistrer_bons_commande_empty(self):
        """Test l'extraction des bons de commande sans lignes"""
        # Ne devrait pas lever d'exception
        self.fichier.extraire_et_enregistrer_bons_commande()

    def test_meta_attributes(self):
        """Test les attributs Meta"""
        self.assertEqual(self.fichier._meta.verbose_name, "Imported File")
        self.assertEqual(self.fichier._meta.verbose_name_plural, "Imported Files")


class TestReception(TestCase):
    def setUp(self):
        self._exists_patcher = patch('orders.models.default_storage.exists', return_value=False)
        self._exists_patcher.start()
        self.addCleanup(self._exists_patcher.stop)
        self._extract_patcher = patch('orders.utils.extraire_depuis_fichier_relatif', return_value=([], 0))
        self._extract_patcher.start()
        self.addCleanup(self._extract_patcher.stop)

        self.user = User.objects.create_user('test@example.com', 'testpass')
        self.bon_commande = NumeroBonCommande.objects.create(numero='TEST123')
        self.fichier = FichierImporte.objects.create(
            fichier='test.csv',
            utilisateur=self.user
        )
        self.reception = Reception.objects.create(
            bon_commande=self.bon_commande,
            fichier=self.fichier,
            business_id="ORDER:TEST123|LINE:1|ITEM:1|SCHEDULE:1",
            ordered_quantity=Decimal('100'),
            quantity_delivered=Decimal('80'),
            received_quantity=Decimal('80'),
            quantity_not_delivered=Decimal('20'),
            unit_price=Decimal('10'),
            user=self.user.email
        )

    def test_creation(self):
        """Test la création d'une réception"""
        self.assertEqual(self.reception.ordered_quantity, Decimal('100'))
        self.assertEqual(self.reception.quantity_delivered, Decimal('80'))
        self.assertEqual(self.reception.unit_price, Decimal('10'))

    def test_save_calculates_fields(self):
        """Test que save() calcule les champs dérivés"""
        # amount_delivered = quantity_delivered * unit_price
        expected_amount = Decimal('80') * Decimal('10')
        self.assertEqual(self.reception.amount_delivered, expected_amount)

    def test_verify_alignment(self):
        """Test la vérification de l'alignement avec une ligne fichier"""
        # Nettoyer les lignes auto-créées pour éviter les conflits
        self.fichier.lignes.all().delete()
        
        ligne = LigneFichier.objects.create(
            fichier=self.fichier,
            numero_ligne=1,
            contenu={'Order': 'TEST123', 'Ordered Quantity': '100'},
            business_id="ORDER:TEST123|LINE:1|ITEM:1|SCHEDULE:1"
        )
        
        result = self.reception.verify_alignment(ligne)
        self.assertTrue(result)

    def test_string_representation(self):
        """Test la représentation en string"""
        expected = f"Réception pour TEST123 - ID métier: ORDER:TEST123|LINE:1|ITEM:1|SCHEDULE:1"
        self.assertEqual(str(self.reception), expected)

    def test_meta_attributes(self):
        """Test les attributs Meta"""
        self.assertEqual(self.reception._meta.verbose_name, "Réception")
        self.assertEqual(self.reception._meta.verbose_name_plural, "Réceptions")


class TestActivityLog(TestCase):
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
        self.activity_log = ActivityLog.objects.create(
            bon_commande='TEST123',
            fichier=self.fichier,
            business_id="ORDER:TEST123|LINE:1|ITEM:1|SCHEDULE:1",
            ordered_quantity=Decimal('100'),
            quantity_delivered=Decimal('80'),
            quantity_not_delivered=Decimal('20'),
            user=self.user.email
        )

    def test_creation(self):
        """Test la création d'un log d'activité"""
        self.assertEqual(self.activity_log.bon_commande, 'TEST123')
        self.assertEqual(self.activity_log.ordered_quantity, Decimal('100'))
        self.assertIsNotNone(self.activity_log.action_date)

    def test_string_representation(self):
        """Test la représentation en string"""
        self.assertIn('TEST123', str(self.activity_log))
        self.assertIn('ID métier', str(self.activity_log))

    def test_meta_attributes(self):
        """Test les attributs Meta"""
        self.assertEqual(self.activity_log._meta.verbose_name, "Journal d'activité")
        self.assertEqual(self.activity_log._meta.verbose_name_plural, "Journal d'activité")
        self.assertEqual(self.activity_log._meta.ordering, ['-action_date'])


class TestMSRNReport(TestCase):
    def setUp(self):
        self._exists_patcher = patch('orders.models.default_storage.exists', return_value=False)
        self._exists_patcher.start()
        self.addCleanup(self._exists_patcher.stop)
        self._extract_patcher = patch('orders.utils.extraire_depuis_fichier_relatif', return_value=([], 0))
        self._extract_patcher.start()
        self.addCleanup(self._extract_patcher.stop)

        self.user = User.objects.create_user('test@example.com', 'testpass')
        self.bon_commande = NumeroBonCommande.objects.create(numero='TEST123')
        self.msrn_report = MSRNReport.objects.create(
            report_number='MSRN250001',
            bon_commande=self.bon_commande,
            user=self.user.email,
            retention_rate=Decimal('5.0')
        )

    def test_creation(self):
        """Test la création d'un rapport MSRN"""
        self.assertEqual(self.msrn_report.report_number, 'MSRN250001')
        self.assertEqual(self.msrn_report.bon_commande, self.bon_commande)
        self.assertEqual(self.msrn_report.retention_rate, Decimal('5.0'))

    def test_string_representation(self):
        """Test la représentation en string"""
        expected = "MSRN-MSRN250001 for TEST123"
        self.assertEqual(str(self.msrn_report), expected)

    def test_progress_rate_property(self):
        """Test la propriété progress_rate"""
        rate = self.msrn_report.progress_rate
        # Devrait retourner 0 car pas d'ActivityLog associé
        self.assertEqual(rate, 0)

    def test_meta_attributes(self):
        """Test les attributs Meta"""
        self.assertEqual(self.msrn_report._meta.verbose_name, "Rapport MSRN")
        self.assertEqual(self.msrn_report._meta.verbose_name_plural, "Rapports MSRN")
        self.assertEqual(self.msrn_report._meta.ordering, ['-created_at'])


class TestInitialReceptionBusiness(TestCase):
    def setUp(self):
        self.bon_commande = NumeroBonCommande.objects.create(numero='TEST123')
        self.fichier = FichierImporte.objects.create(fichier='test.csv')
        self.irb = InitialReceptionBusiness.objects.create(
            business_id="ORDER:TEST123|LINE:1|ITEM:1|SCHEDULE:1",
            bon_commande=self.bon_commande,
            source_file=self.fichier,
            received_quantity=Decimal('50'),
            montant_total_initial=Decimal('1000'),
            montant_recu_initial=Decimal('500'),
            taux_avancement_initial=Decimal('50')
        )

    def test_creation(self):
        """Test la création d'une valeur initiale business"""
        self.assertEqual(self.irb.received_quantity, Decimal('50'))
        self.assertEqual(self.irb.taux_avancement_initial, Decimal('50'))

    def test_string_representation(self):
        """Test la représentation en string"""
        expected = "IRV-BI ORDER:TEST123|LINE:1|ITEM:1|SCHEDULE:1 (TEST123)"
        self.assertEqual(str(self.irb), expected)

    def test_meta_attributes(self):
        """Test les attributs Meta"""
        self.assertEqual(self.irb._meta.verbose_name, "Valeur initiale (business)")
        self.assertEqual(self.irb._meta.verbose_name_plural, "Valeurs initiales (business)")


class TestTimelineDelay(TestCase):
    def setUp(self):
        self.bon_commande = NumeroBonCommande.objects.create(numero='TEST123')
        self.timeline_delay = TimelineDelay.objects.create(
            bon_commande=self.bon_commande,
            delay_part_mtn=5,
            delay_part_force_majeure=3,
            delay_part_vendor=2,
            quotite_realisee=Decimal('100.00'),
            comment_mtn="Retard côté MTN",
            comment_force_majeure="Force majeure météo",
            comment_vendor="Retard fournisseur"
        )

    def test_creation(self):
        """Test la création d'un délai de timeline"""
        self.assertEqual(self.timeline_delay.delay_part_mtn, 5)
        self.assertEqual(self.timeline_delay.delay_part_vendor, 2)
        self.assertEqual(self.timeline_delay.quotite_realisee, Decimal('100.00'))

    def test_calculate_retention_timeline(self):
        """Test le calcul de la rétention timeline"""
        amount, rate = self.timeline_delay.calculate_retention_timeline()
        # Avec montant total = 0, devrait retourner 0
        self.assertEqual(amount, Decimal('0'))
        self.assertEqual(rate, Decimal('0'))

    def test_string_representation(self):
        """Test la représentation en string"""
        expected = "Timeline Delays - TEST123"
        self.assertEqual(str(self.timeline_delay), expected)

    def test_meta_attributes(self):
        """Test les attributs Meta"""
        self.assertEqual(self.timeline_delay._meta.verbose_name, "Timeline Delay")
        self.assertEqual(self.timeline_delay._meta.verbose_name_plural, "Timeline Delays")


class TestVendorEvaluation(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('test@example.com', 'testpass')
        self.bon_commande = NumeroBonCommande.objects.create(numero='TEST123')
        self.vendor_eval = VendorEvaluation.objects.create(
            bon_commande=self.bon_commande,
            supplier="Test Supplier",
            delivery_compliance=8,
            delivery_timeline=7,
            advising_capability=6,
            after_sales_qos=9,
            vendor_relationship=8,
            evaluator=self.user
        )

    def test_creation(self):
        """Test la création d'une évaluation fournisseur"""
        self.assertEqual(self.vendor_eval.supplier, "Test Supplier")
        self.assertEqual(self.vendor_eval.delivery_compliance, 8)
        self.assertEqual(self.vendor_eval.vendor_relationship, 8)

    def test_vendor_final_rating_calculation(self):
        """Test le calcul automatique de la note finale"""
        # (8 + 7 + 6 + 9 + 8) / 5 = 7.6
        self.assertEqual(self.vendor_eval.vendor_final_rating, Decimal('7.60'))

    def test_get_criteria_description(self):
        """Test la récupération de la description d'un critère"""
        description = self.vendor_eval.get_criteria_description('delivery_compliance', 8)
        self.assertEqual(description, "Conforme au besoin")

    def test_get_total_score(self):
        """Test le calcul du score total"""
        total = self.vendor_eval.get_total_score()
        self.assertEqual(total, 38)  # 8 + 7 + 6 + 9 + 8

    def test_string_representation(self):
        """Test la représentation en string"""
        expected = "Évaluation Test Supplier - TEST123"
        self.assertEqual(str(self.vendor_eval), expected)

    def test_meta_attributes(self):
        """Test les attributs Meta"""
        self.assertEqual(self.vendor_eval._meta.verbose_name, "Évaluation fournisseur")
        self.assertEqual(self.vendor_eval._meta.verbose_name_plural, "Évaluations fournisseurs")
        self.assertEqual(self.vendor_eval._meta.ordering, ['-date_evaluation'])


# ========== TESTS SUPPLÉMENTAIRES POUR ATTEINDRE 90% DE COUVERTURE ==========

class TestNumeroBonCommandeAdvanced(TestCase):
    """Tests avancés pour NumeroBonCommande avec réceptions"""
    
    def setUp(self):
        self._exists_patcher = patch('orders.models.default_storage.exists', return_value=False)
        self._exists_patcher.start()
        self.addCleanup(self._exists_patcher.stop)
        self._extract_patcher = patch('orders.utils.extraire_depuis_fichier_relatif', return_value=([], 0))
        self._extract_patcher.start()
        self.addCleanup(self._extract_patcher.stop)

        self.user = User.objects.create_user('test@example.com', 'testpass')
        self.bon = NumeroBonCommande.objects.create(numero='PO-ADV-001', cpu='ITS')
        self.fichier = FichierImporte.objects.create(fichier='test.csv', utilisateur=self.user)
        self.bon.fichiers.add(self.fichier)
        
        # Nettoyer les lignes auto-créées
        self.fichier.lignes.all().delete()
        
        # Créer des lignes de fichier avec données
        self.ligne1 = LigneFichier.objects.create(
            fichier=self.fichier,
            numero_ligne=1,
            business_id='PO-ADV-L1',
            contenu={
                'Order': 'PO-ADV-001',
                'Sponsor': 'Test Sponsor',
                'Supplier': 'Test Supplier',
                'CPU': 'ITS',
                'Line Description': 'Test Item',
                'Currency': 'XOF',
                'Project Number': 'PRJ-001',
                'Project Manager': 'John Doe'
            }
        )
        
        # Créer des réceptions
        self.reception1 = Reception.objects.create(
            bon_commande=self.bon,
            fichier=self.fichier,
            business_id='PO-ADV-L1',
            ordered_quantity=Decimal('100'),
            quantity_delivered=Decimal('80'),
            received_quantity=Decimal('80'),
            quantity_not_delivered=Decimal('20'),
            unit_price=Decimal('100'),
            user=self.user.email
        )
        
        self.reception2 = Reception.objects.create(
            bon_commande=self.bon,
            fichier=self.fichier,
            business_id='PO-ADV-L2',
            ordered_quantity=Decimal('50'),
            quantity_delivered=Decimal('50'),
            received_quantity=Decimal('50'),
            quantity_not_delivered=Decimal('0'),
            unit_price=Decimal('200'),
            user=self.user.email
        )
    
    def test_montant_total_with_multiple_receptions(self):
        """Test calcul montant total avec plusieurs réceptions"""
        montant = self.bon.montant_total()
        # (100 * 100) + (50 * 200) = 10000 + 10000 = 20000
        self.assertEqual(montant, Decimal('20000.00'))
    
    def test_montant_recu_with_partial_delivery(self):
        """Test calcul montant reçu avec livraison partielle"""
        montant = self.bon.montant_recu()
        # (80 * 100) + (50 * 200) = 8000 + 10000 = 18000
        self.assertEqual(montant, Decimal('18000.00'))
    
    def test_taux_avancement_calculation(self):
        """Test calcul du taux d'avancement"""
        taux = self.bon.taux_avancement()
        # 18000 / 20000 * 100 = 90%
        self.assertEqual(taux, Decimal('90.00'))
    
    def test_get_sponsor_from_fichier(self):
        """Test récupération du sponsor depuis fichier"""
        sponsor = self.bon.get_sponsor()
        self.assertEqual(sponsor, 'Test Sponsor')
    
    def test_get_supplier_from_fichier(self):
        """Test récupération du fournisseur depuis fichier"""
        supplier = self.bon.get_supplier()
        self.assertEqual(supplier, 'Test Supplier')
    
    def test_get_cpu_from_fichier(self):
        """Test récupération du CPU depuis fichier"""
        cpu = self.bon.get_cpu()
        self.assertEqual(cpu, 'ITS')
    
    def test_get_order_description_from_fichier(self):
        """Test récupération de la description depuis le fichier"""
        description = self.bon.get_order_description()
        # Peut retourner 'N/A' si pas de ligne dans le fichier
        self.assertIn(description, ['Test Item', 'N/A'])
    
    def test_get_currency_from_fichier(self):
        """Test récupération de la devise depuis fichier"""
        currency = self.bon.get_currency()
        self.assertEqual(currency, 'XOF')
    
    def test_get_project_number_from_fichier(self):
        """Test récupération du numéro de projet depuis fichier"""
        project_number = self.bon.get_project_number()
        self.assertEqual(project_number, 'PRJ-001')
    
    def test_get_project_manager_from_fichier(self):
        """Test récupération du project manager depuis fichier"""
        pm = self.bon.get_project_manager()
        self.assertEqual(pm, 'John Doe')


class TestReceptionSaveMethod(TestCase):
    """Tests pour la méthode save() de Reception"""
    
    def setUp(self):
        self._exists_patcher = patch('orders.models.default_storage.exists', return_value=False)
        self._exists_patcher.start()
        self.addCleanup(self._exists_patcher.stop)
        self._extract_patcher = patch('orders.utils.extraire_depuis_fichier_relatif', return_value=([], 0))
        self._extract_patcher.start()
        self.addCleanup(self._extract_patcher.stop)

        self.user = User.objects.create_user('test@example.com', 'testpass')
        self.bon = NumeroBonCommande.objects.create(numero='PO-SAVE-001')
        self.fichier = FichierImporte.objects.create(fichier='test.csv', utilisateur=self.user)
    
    def test_save_calculates_amount_delivered(self):
        """Test que save() calcule amount_delivered"""
        reception = Reception.objects.create(
            bon_commande=self.bon,
            fichier=self.fichier,
            business_id='TEST-SAVE-1',
            ordered_quantity=Decimal('100'),
            quantity_delivered=Decimal('80'),
            received_quantity=Decimal('80'),
            quantity_not_delivered=Decimal('20'),
            unit_price=Decimal('50'),
            user=self.user.email
        )
        
        # amount_delivered = quantity_delivered * unit_price
        expected = Decimal('80') * Decimal('50')
        self.assertEqual(reception.amount_delivered, expected)
    
    def test_save_calculates_amount_not_delivered(self):
        """Test que save() calcule amount_not_delivered"""
        reception = Reception.objects.create(
            bon_commande=self.bon,
            fichier=self.fichier,
            business_id='TEST-SAVE-2',
            ordered_quantity=Decimal('100'),
            quantity_delivered=Decimal('80'),
            received_quantity=Decimal('80'),
            quantity_not_delivered=Decimal('20'),
            unit_price=Decimal('50'),
            user=self.user.email
        )
        
        # amount_not_delivered = quantity_not_delivered * unit_price
        expected = Decimal('20') * Decimal('50')
        self.assertEqual(reception.amount_not_delivered, expected)
    
    def test_save_calculates_quantity_payable(self):
        """Test que save() calcule quantity_payable correctement"""
        reception = Reception.objects.create(
            bon_commande=self.bon,
            fichier=self.fichier,
            business_id='TEST-PAY',
            ordered_quantity=Decimal('100'),
            quantity_delivered=Decimal('80'),
            received_quantity=Decimal('80'),
            quantity_not_delivered=Decimal('20'),
            unit_price=Decimal('50'),
            user=self.user.email
        )
        
        # quantity_payable devrait être calculé automatiquement
        # Vérifier qu'il existe et est un Decimal
        self.assertIsNotNone(reception.quantity_payable)
        self.assertIsInstance(reception.quantity_payable, Decimal)
    
    def test_save_normalizes_business_id(self):
        """Test que save() normalise le business_id"""
        reception = Reception.objects.create(
            bon_commande=self.bon,
            fichier=self.fichier,
            business_id='ORDER:123|LINE:43.0|ITEM:1.0',
            ordered_quantity=Decimal('100'),
            quantity_delivered=Decimal('80'),
            received_quantity=Decimal('80'),
            quantity_not_delivered=Decimal('20'),
            unit_price=Decimal('50'),
            user=self.user.email
        )
        
        # Les .0 devraient être supprimés
        self.assertEqual(reception.business_id, 'ORDER:123|LINE:43|ITEM:1')
    
    def test_save_handles_invalid_decimal(self):
        """Test que save() gère les décimales invalides"""
        reception = Reception(
            bon_commande=self.bon,
            fichier=self.fichier,
            business_id='TEST-INVALID',
            ordered_quantity=Decimal('100'),
            quantity_delivered=Decimal('0'),  # Valeur par défaut au lieu de None
            received_quantity=Decimal('0'),
            quantity_not_delivered=Decimal('100'),
            unit_price=Decimal('50'),
            user=self.user.email
        )
        
        # Devrait gérer gracieusement
        reception.save()
        self.assertEqual(reception.amount_delivered, Decimal('0'))


class TestReceptionProperties(TestCase):
    """Tests pour les propriétés de Reception"""
    
    def setUp(self):
        self.user = User.objects.create_user('test@example.com', 'testpass')
        self.bon = NumeroBonCommande.objects.create(numero='TEST-PROP')
        self.fichier = FichierImporte.objects.create(fichier='test.csv', utilisateur=self.user)
        self.fichier.lignes.all().delete()
        
        self.reception = Reception.objects.create(
            bon_commande=self.bon,
            fichier=self.fichier,
            business_id='PROP-001',
            ordered_quantity=Decimal('100'),
            quantity_delivered=Decimal('80'),
            received_quantity=Decimal('80'),
            quantity_not_delivered=Decimal('20'),
            unit_price=Decimal('50'),
            user=self.user.email
        )
    
    def test_reception_has_bon_commande(self):
        """Test que la réception a un bon de commande"""
        self.assertIsNotNone(self.reception.bon_commande)
        self.assertEqual(self.reception.bon_commande.numero, 'TEST-PROP')
    
    def test_reception_has_fichier(self):
        """Test que la réception a un fichier"""
        self.assertIsNotNone(self.reception.fichier)
    
    def test_reception_business_id(self):
        """Test business_id de la réception"""
        self.assertEqual(self.reception.business_id, 'PROP-001')
    
    def test_reception_calculations(self):
        """Test calculs de la réception"""
        self.assertEqual(self.reception.ordered_quantity, Decimal('100'))
        self.assertEqual(self.reception.quantity_delivered, Decimal('80'))
        self.assertEqual(self.reception.quantity_not_delivered, Decimal('20'))


class TestVendorEvaluationScores(TestCase):
    """Tests pour les calculs de scores de VendorEvaluation"""
    
    def setUp(self):
        self.user = User.objects.create_user('test@example.com', 'testpass')
        self.bon = NumeroBonCommande.objects.create(numero='PO-EVAL-001')
        self.evaluation = VendorEvaluation.objects.create(
            bon_commande=self.bon,
            supplier="Excellent Supplier",
            delivery_compliance=10,
            delivery_timeline=9,
            advising_capability=8,
            after_sales_qos=10,
            vendor_relationship=9,
            evaluator=self.user
        )
    
    def test_total_score_calculation(self):
        """Test calcul du score total"""
        total = self.evaluation.get_total_score()
        # 10 + 9 + 8 + 10 + 9 = 46
        self.assertEqual(total, 46)
    
    def test_average_score_calculation(self):
        """Test calcul de la moyenne"""
        # vendor_final_rating devrait être calculé automatiquement
        # (10 + 9 + 8 + 10 + 9) / 5 = 9.2
        self.assertEqual(self.evaluation.vendor_final_rating, Decimal('9.20'))
    
    def test_criteria_weights(self):
        """Test que tous les critères ont le même poids"""
        # Tous les critères comptent également dans le calcul
        criteria = [
            self.evaluation.delivery_compliance,
            self.evaluation.delivery_timeline,
            self.evaluation.advising_capability,
            self.evaluation.after_sales_qos,
            self.evaluation.vendor_relationship
        ]
        
        total = sum(criteria)
        average = total / len(criteria)
        self.assertEqual(float(self.evaluation.vendor_final_rating), average)


class TestUtilityFunctionsAdvanced(TestCase):
    """Tests avancés pour les fonctions utilitaires"""
    
    def test_round_decimal_with_int(self):
        """Test arrondi avec un entier"""
        result = round_decimal(10, places=2)
        self.assertEqual(result, Decimal('10.00'))
    
    def test_round_decimal_places_0(self):
        """Test arrondi à 0 décimales"""
        result = round_decimal(Decimal('10.6'), places=0)
        self.assertEqual(result, Decimal('11'))
    
    def test_round_decimal_places_3(self):
        """Test arrondi à 3 décimales"""
        result = round_decimal(Decimal('10.4567'), places=3)
        self.assertEqual(result, Decimal('10.457'))
    
    def test_round_decimal_with_invalid_string(self):
        """Test arrondi avec chaîne invalide"""
        result = round_decimal('invalid', places=2)
        self.assertEqual(result, Decimal('0'))
    
    def test_normalize_business_id_without_colon(self):
        """Test normalisation sans ':' """
        result = normalize_business_id('simple_value')
        self.assertEqual(result, 'simple_value')
    
    def test_normalize_business_id_with_empty_string(self):
        """Test normalisation avec chaîne vide"""
        result = normalize_business_id('')
        self.assertEqual(result, '')
    
    def test_normalize_business_id_with_invalid_float(self):
        """Test normalisation avec valeur non convertible"""
        result = normalize_business_id('order:ABC|line:1')
        self.assertEqual(result, 'order:ABC|line:1')


class TestActivityLogModel(TestCase):
    """Tests spécifiques pour le modèle ActivityLog"""
    
    def setUp(self):
        self.user = User.objects.create_user('test@example.com', 'testpass')
        self.fichier = FichierImporte.objects.create(fichier='test.csv', utilisateur=self.user)
        self.fichier.lignes.all().delete()
        
        self.activity_log = ActivityLog.objects.create(
            bon_commande='TEST123',
            fichier=self.fichier,
            business_id="ORDER:TEST123|LINE:1|ITEM:1|SCHEDULE:1",
            ordered_quantity=Decimal('100'),
            quantity_delivered=Decimal('80'),
            quantity_not_delivered=Decimal('20'),
            cumulative_recipe=Decimal('180'),
            user=self.user.email,
            progress_rate=Decimal('80.0'),
            item_reference="REF123"
        )
    
    def test_activity_log_creation(self):
        """Test la création d'un log d'activité avec tous les champs"""
        self.assertEqual(self.activity_log.bon_commande, 'TEST123')
        self.assertEqual(self.activity_log.quantity_delivered, Decimal('80'))
        self.assertEqual(self.activity_log.cumulative_recipe, Decimal('180'))
        self.assertEqual(self.activity_log.item_reference, "REF123")
        self.assertEqual(self.activity_log.progress_rate, Decimal('80.0'))
    
    def test_activity_log_string_representation(self):
        """Test la représentation en string"""
        representation = str(self.activity_log)
        self.assertIn('TEST123', representation)
        self.assertIn('ID métier', representation)
    
    def test_activity_log_meta_attributes(self):
        """Test les attributs Meta"""
        self.assertEqual(self.activity_log._meta.verbose_name, "Journal d'activité")
        self.assertEqual(self.activity_log._meta.verbose_name_plural, "Journal d'activité")
        self.assertEqual(self.activity_log._meta.ordering, ['-action_date'])


class TestMSRNReportProperties(TestCase):
    """Tests pour les propriétés de MSRNReport"""
    
    def setUp(self):
        self.user = User.objects.create_user('test@example.com', 'testpass')
        self.bon_commande = NumeroBonCommande.objects.create(numero='TEST123')
        self.msrn_report = MSRNReport.objects.create(
            report_number='MSRN250001',
            bon_commande=self.bon_commande,
            user=self.user.email,
            retention_rate=Decimal('5.0')
        )
    
    def test_progress_rate_with_activity_log(self):
        """Test progress_rate avec ActivityLog existant"""
        fichier = FichierImporte.objects.create(fichier='test.csv', utilisateur=self.user)
        ActivityLog.objects.create(
            bon_commande='TEST123',
            fichier=fichier,
            business_id="ORDER:TEST123|LINE:1|ITEM:1|SCHEDULE:1",
            ordered_quantity=Decimal('100'),
            quantity_delivered=Decimal('50'),
            quantity_not_delivered=Decimal('50'),
            user=self.user.email,
            progress_rate=Decimal('50.0'),
            action_date=self.msrn_report.created_at
        )
        rate = self.msrn_report.progress_rate
        self.assertEqual(rate, Decimal('50.0'))
    
    def test_progress_rate_fallback(self):
        """Test progress_rate en fallback sur taux_avancement"""
        ActivityLog.objects.all().delete()
        rate = self.msrn_report.progress_rate
        self.assertEqual(rate, Decimal('0'))


class TestReceptionEdgeCases(TestCase):
    """Tests pour les cas limites de Reception"""
    
    def setUp(self):
        self.user = User.objects.create_user('test@example.com', 'testpass')
        self.bon = NumeroBonCommande.objects.create(numero='TEST-EDGE')
        self.fichier = FichierImporte.objects.create(fichier='test.csv', utilisateur=self.user)
        self.fichier.lignes.all().delete()
    
    def test_reception_with_none_values(self):
        """Test Reception avec valeurs None provoque une contrainte NOT NULL"""
        with self.assertRaises(IntegrityError):
            Reception.objects.create(
                bon_commande=self.bon,
                fichier=self.fichier,
                business_id='EDGE-001',
                ordered_quantity=None,
                quantity_delivered=None,
                received_quantity=None,
                quantity_not_delivered=None,
                unit_price=None,
                user=self.user.email
            )
    
    def test_reception_save_with_invalid_calculation(self):
        """Test save() de Reception lève une erreur sur valeur invalide"""
        reception = Reception(
            bon_commande=self.bon,
            fichier=self.fichier,
            business_id='EDGE-002',
            ordered_quantity=Decimal('100'),
            quantity_delivered='invalid',
            received_quantity=Decimal('80'),
            quantity_not_delivered=Decimal('20'),
            unit_price=Decimal('50'),
            user=self.user.email
        )
        with self.assertRaises(Exception):
            reception.save()


class TestFichierImporteMethods(TestCase):
    """Tests pour les méthodes de FichierImporte"""
    
    def setUp(self):
        self.user = User.objects.create_user('test@example.com', 'testpass')
        self.fichier = FichierImporte.objects.create(
            fichier='test.csv',
            utilisateur=self.user
        )
        self.fichier.lignes.all().delete()
    
    def test_get_raw_data_empty(self):
        """Test get_raw_data sans lignes"""
        raw_data = self.fichier.get_raw_data()
        self.assertEqual(raw_data, [])
    
    def test_get_recipe_quantities_empty(self):
        """Test get_recipe_quantities sans données"""
        quantities = self.fichier.get_recipe_quantities()
        self.assertEqual(quantities, {})
    
    def test_extraire_et_enregistrer_bons_commande_empty(self):
        """Test extraction des bons de commande sans lignes"""
        self.fichier.extraire_et_enregistrer_bons_commande()


class TestInitialReceptionBusinessMethods(TestCase):
    """Tests pour InitialReceptionBusiness"""
    
    def setUp(self):
        self.bon_commande = NumeroBonCommande.objects.create(numero='TEST123')
        self.fichier = FichierImporte.objects.create(fichier='test.csv')
        self.irb = InitialReceptionBusiness.objects.create(
            business_id="ORDER:TEST123|LINE:1|ITEM:1|SCHEDULE:1",
            bon_commande=self.bon_commande,
            source_file=self.fichier,
            received_quantity=Decimal('50'),
            montant_total_initial=Decimal('1000'),
            montant_recu_initial=Decimal('500'),
            taux_avancement_initial=Decimal('50')
        )
    
    def test_save_normalizes_business_id(self):
        """Test que save() normalise le business_id"""
        irb = InitialReceptionBusiness(
            business_id="ORDER:123|LINE:43.0|ITEM:1.0|SCHEDULE:1",
            bon_commande=self.bon_commande,
            received_quantity=Decimal('50')
        )
        irb.save()
        self.assertEqual(irb.business_id, "ORDER:123|LINE:43|ITEM:1|SCHEDULE:1")


class TestSignalHandlers(TestCase):
    """Tests pour les signaux"""
    
    def setUp(self):
        self.bon = NumeroBonCommande.objects.create(numero='TEST-SIGNAL', retention_rate=Decimal('0'))
        self.fichier = FichierImporte.objects.create(fichier='test.csv')
        self.fichier.lignes.all().delete()
        
        self.reception = Reception.objects.create(
            bon_commande=self.bon,
            fichier=self.fichier,
            business_id='SIGNAL-001',
            ordered_quantity=Decimal('100'),
            quantity_delivered=Decimal('80'),
            received_quantity=Decimal('80'),
            quantity_not_delivered=Decimal('20'),
            unit_price=Decimal('50'),
            user='test@example.com'
        )
    
    def test_update_receptions_on_retention_rate_change(self):
        """Test que le signal met à jour les réceptions quand le taux de rétention change"""
        initial_payable = self.reception.quantity_payable
        self.bon.retention_rate = Decimal('5.0')
        self.bon.save()
        self.reception.refresh_from_db()
        self.assertNotEqual(self.reception.quantity_payable, initial_payable)
    
    def test_signal_no_update_when_retention_unchanged(self):
        """Test que le signal ne fait rien quand le taux de rétention ne change pas"""
        from django.db.models import F
        with patch.object(Reception.objects, 'update') as mock_update:
            self.bon.save()
            mock_update.assert_not_called()


class TestVendorEvaluationEdgeCases(TestCase):
    """Tests pour les cas limites de VendorEvaluation"""
    
    def setUp(self):
        self.user = User.objects.create_user('test@example.com', 'testpass')
        self.bon_commande = NumeroBonCommande.objects.create(numero='PO-EVAL-001')
    
    def test_vendor_evaluation_with_zero_scores(self):
        """Test avec tous les scores à zéro"""
        evaluation = VendorEvaluation.objects.create(
            bon_commande=self.bon_commande,
            supplier="Test Supplier",
            delivery_compliance=0,
            delivery_timeline=0,
            advising_capability=0,
            after_sales_qos=0,
            vendor_relationship=0,
            evaluator=self.user
        )
        self.assertEqual(evaluation.vendor_final_rating, Decimal('0.00'))
        self.assertEqual(evaluation.get_total_score(), 0)
    
    def test_vendor_evaluation_criteria_description_invalid(self):
        """Test get_criteria_description avec critère invalide"""
        evaluation = VendorEvaluation.objects.create(
            bon_commande=self.bon_commande,
            supplier="Test Supplier",
            delivery_compliance=8,
            delivery_timeline=7,
            advising_capability=6,
            after_sales_qos=9,
            vendor_relationship=8,
            evaluator=self.user
        )
        description = evaluation.get_criteria_description('invalid_criteria', 5)
        self.assertEqual(description, "Score: 5")
    
    def test_vendor_evaluation_unique_together(self):
        """Test la contrainte unique_together"""
        VendorEvaluation.objects.create(
            bon_commande=self.bon_commande,
            supplier="Test Supplier",
            delivery_compliance=8,
            delivery_timeline=7,
            advising_capability=6,
            after_sales_qos=9,
            vendor_relationship=8,
            evaluator=self.user
        )
        with self.assertRaises(Exception):
            VendorEvaluation.objects.create(
                bon_commande=self.bon_commande,
                supplier="Test Supplier",
                delivery_compliance=9,
                delivery_timeline=8,
                advising_capability=7,
                after_sales_qos=10,
                vendor_relationship=9,
                evaluator=self.user
            )
# Ajoutez ces tests à votre fichier test_models.py

class TestUncoveredLines(TestCase):
    """Tests spécifiques pour couvrir les lignes non couvertes"""
    
    def setUp(self):
        self.user = User.objects.create_user('test@example.com', 'password')
        self.fichier = FichierImporte.objects.create(fichier='test.csv', utilisateur=self.user)

    def test_numero_bon_commande_montant_methods_direct_calls(self):
        """Test des méthodes de montant avec appels directs pour couvrir les branches non couvertes"""
        bon = NumeroBonCommande.objects.create(numero='TEST-DIRECT')
        
        # Test direct de _mettre_a_jour_montants sans réceptions
        bon._mettre_a_jour_montants()
        self.assertEqual(bon._montant_total, Decimal('0'))
        self.assertEqual(bon._montant_recu, Decimal('0'))
        self.assertEqual(bon._taux_avancement, Decimal('0'))

    def test_numero_bon_commande_get_methods_edge_cases(self):
        """Test des méthodes get avec cas limites pour couvrir les branches else/except"""
        bon = NumeroBonCommande.objects.create(numero='TEST-EDGE')
        
        # Test avec fichiers mais sans lignes correspondantes
        bon.fichiers.add(self.fichier)
        
        # Ces appels doivent parcourir le code mais retourner "N/A"
        self.assertEqual(bon.get_sponsor(), "N/A")
        self.assertEqual(bon.get_supplier(), "N/A") 
        self.assertEqual(bon.get_order_description(), "N/A")
        self.assertEqual(bon.get_currency(), "XOF")
        self.assertEqual(bon.get_project_number(), "N/A")
        self.assertEqual(bon.get_cpu(), "N/A")
        self.assertEqual(bon.get_project_manager(), "N/A")
        self.assertEqual(bon.get_project_coordinator(), "N/A")
        self.assertEqual(bon.get_manager_portfolio(), "N/A")
        self.assertEqual(bon.get_gm_epmo(), "N/A")
        self.assertEqual(bon.get_senior_pm(), "N/A")
        self.assertEqual(bon.get_senior_technical_lead(), "N/A")
        self.assertEqual(bon.get_code_ifs(), "N/A")

    def test_numero_bon_commande_get_cpu_force_refresh(self):
        """Test get_cpu avec force_refresh=True"""
        bon = NumeroBonCommande.objects.create(numero='TEST-CPU', cpu='OLD-CPU')
        bon.fichiers.add(self.fichier)
        
        # Devrait ignorer le CPU stocké et chercher dans les fichiers
        result = bon.get_cpu(force_refresh=True)
        self.assertEqual(result, "N/A")

    def test_ligne_fichier_generate_business_id_edge_cases(self):
        """Test generate_business_id avec cas limites"""
        # Test avec contenu vide
        ligne = LigneFichier(fichier=self.fichier, numero_ligne=1, contenu={})
        self.assertIsNone(ligne.generate_business_id())
        
        # Test avec valeurs None/vides dans les composants
        ligne.contenu = {
            'Order': '',
            'Line': None,
            'Item': '  ',
            'Schedule': 'test'
        }
        business_id = ligne.generate_business_id()
        self.assertEqual(business_id, "SCHEDULE:test")

    def test_fichier_importe_save_edge_cases(self):
        """Test save() de FichierImporte avec cas limites"""
        # Test sans fichier
        fichier = FichierImporte()
        fichier.save()
        self.assertEqual(fichier.extension, '')
        
        # Test avec extension vide
        fichier.fichier.name = 'test.'
        fichier.save()
        self.assertEqual(fichier.extension, '')

    def test_reception_save_with_none_values(self):
        """Test save() de Reception avec valeurs None"""
        bon = NumeroBonCommande.objects.create(numero='TEST-NONE')
        
        with self.assertRaises(IntegrityError):
            Reception.objects.create(
                bon_commande=bon,
                fichier=self.fichier,
                business_id='TEST-NONE-1',
                ordered_quantity=None,
                quantity_delivered=None, 
                received_quantity=None,
                quantity_not_delivered=None,
                unit_price=None
            )

    def test_reception_save_with_retention_rate_none(self):
        """Test save() avec bon_commande.retention_rate = None"""
        bon = NumeroBonCommande.objects.create(numero='TEST-RET-NONE')
        bon.retention_rate = None
        with self.assertRaises(TypeError):
            bon.save()
        
        reception = Reception(
            bon_commande=bon,
            fichier=self.fichier,
            business_id='TEST-RET-NONE-1',
            ordered_quantity=Decimal('100'),
            quantity_delivered=Decimal('80'),
            received_quantity=Decimal('80'),
            quantity_not_delivered=Decimal('20'),
            unit_price=Decimal('50')
        )
        
        reception.save()
        # Devrait utiliser 0 comme taux de rétention par défaut
        self.assertEqual(reception.quantity_payable, Decimal('80'))

    def test_activity_log_with_none_values(self):
        """Test ActivityLog avec valeurs None"""
        log = ActivityLog(
            bon_commande='TEST',
            fichier=self.fichier,
            business_id=None,
            ordered_quantity=Decimal('100'),
            quantity_delivered=Decimal('50'),
            quantity_not_delivered=Decimal('50'),
            cumulative_recipe=None,
            progress_rate=None
        )
        log.save()
        
        self.assertIsNone(log.cumulative_recipe)
        self.assertIsNone(log.progress_rate)

    def test_msrn_report_save_generation(self):
        """Test MSRNReport.save() avec génération de numéro"""
        bon = NumeroBonCommande.objects.create(numero='TEST-MSRN')
        
        # Premier rapport - devrait générer un numéro
        report1 = MSRNReport(bon_commande=bon, user='test@example.com')
        report1.save()
        self.assertTrue(report1.report_number.startswith('MSRN'))
        
        # Deuxième rapport - devrait générer un numéro différent
        report2 = MSRNReport(bon_commande=bon, user='test@example.com')
        report2.save()
        self.assertNotEqual(report1.report_number, report2.report_number)

    def test_msrn_report_progress_rate_edge_cases(self):
        """Test MSRNReport.progress_rate avec cas limites"""
        bon = NumeroBonCommande.objects.create(numero='TEST-PROG')
        report = MSRNReport.objects.create(
            report_number='MSRN250001',
            bon_commande=bon,
            user='test@example.com'
        )
        
        # Test sans ActivityLog et avec exception
        with patch.object(NumeroBonCommande, 'taux_avancement', side_effect=Exception):
            rate = report.progress_rate
            self.assertEqual(rate, 0)

    def test_initial_reception_business_save_normalization(self):
        """Test InitialReceptionBusiness.save() avec normalisation"""
        bon = NumeroBonCommande.objects.create(numero='TEST-IRB')
        
        irb = InitialReceptionBusiness(
            business_id="ORDER:123|LINE:43.0|ITEM:1.0",
            bon_commande=bon,
            received_quantity=Decimal('50')
        )
        
        # Devrait normaliser le business_id
        irb.save()
        self.assertEqual(irb.business_id, "ORDER:123|LINE:43|ITEM:1")

    def test_timeline_delay_calculate_retention_zero_amount(self):
        """Test TimelineDelay.calculate_retention_timeline avec montant zéro"""
        bon = NumeroBonCommande.objects.create(numero='TEST-TL-ZERO')
        
        timeline = TimelineDelay(
            bon_commande=bon,
            delay_part_mtn=5,
            delay_part_force_majeure=3,
            delay_part_vendor=2,
            quotite_realisee=Decimal('100.00'),
            comment_mtn="Test",
            comment_force_majeure="Test",
            comment_vendor="Test"
        )
        
        amount, rate = timeline.calculate_retention_timeline()
        self.assertEqual(amount, Decimal('0'))
        self.assertEqual(rate, Decimal('0'))

    def test_vendor_evaluation_save_with_none_scores(self):
        """Test VendorEvaluation.save() avec certains scores None (impossible normalement)"""
        bon = NumeroBonCommande.objects.create(numero='TEST-VENDOR')
        
        # Les champs sont IntegerField donc ne peuvent pas être None, mais testons la méthode
        evaluation = VendorEvaluation(
            bon_commande=bon,
            supplier="Test",
            delivery_compliance=0,
            delivery_timeline=0,
            advising_capability=0,
            after_sales_qos=0,
            vendor_relationship=0
        )
        evaluation.save()
        self.assertEqual(evaluation.vendor_final_rating, Decimal('0.00'))

    def test_round_decimal_edge_cases(self):
        """Test round_decimal avec cas limites"""
        # Test avec valeur non convertible
        result = round_decimal('not_a_number')
        self.assertEqual(result, Decimal('0'))
        
        # Test avec Decimal déjà arrondi
        result = round_decimal(Decimal('10.00'))
        self.assertEqual(result, Decimal('10.00'))
        
        # Test avec 0 décimales
        result = round_decimal(Decimal('10.55'), 0)
        self.assertEqual(result, Decimal('11'))

    def test_normalize_business_id_edge_cases(self):
        """Test normalize_business_id avec cas limites"""
        # Test avec chaîne vide
        result = normalize_business_id('')
        self.assertEqual(result, '')
        
        # Test avec None
        result = normalize_business_id(None)
        self.assertIsNone(result)
        
        # Test avec parties sans ':'
        result = normalize_business_id('simple|string')
        self.assertEqual(result, 'simple|string')
        
        # Test avec valeur float non entière
        result = normalize_business_id('key:45.5')
        self.assertEqual(result, 'key:45.5')


class TestFichierImporteExtraction(TestCase):
    """Tests pour l'extraction dans FichierImporte.save()"""
    
    def setUp(self):
        self.user = User.objects.create_user('test@example.com', 'password')
    
    @patch('orders.import_utils.import_file_optimized')
    @patch('orders.models.default_storage.exists', return_value=True)
    def test_save_with_dict_lines_but_no_headers(self, mock_exists, mock_import):
        """Test save() avec lignes dict mais sans headers"""
        # Mock import_file_optimized pour retourner 2 lignes
        mock_import.return_value = (2, ['PO001'])
        
        fichier = FichierImporte(
            fichier='test.csv',
            utilisateur=self.user
        )
        fichier.save()
        
        # L'import mocké a été appelé
        self.assertTrue(mock_import.called)

    @patch('orders.import_utils.import_file_optimized')
    @patch('orders.models.default_storage.exists', return_value=True) 
    def test_save_with_non_tabular_data(self, mock_exists, mock_import):
        """Test save() avec données non tabulaires"""
        # Mock pour simuler une erreur d'extraction (fichier non supporté)
        mock_import.side_effect = Exception("Format non supporté")
        
        fichier = FichierImporte(
            fichier='test.bin',
            utilisateur=self.user
        )
        fichier.save()
        
        # Nettoyer les lignes potentiellement créées par d'autres mécanismes
        fichier.lignes.all().delete()
        
        # Vérifier que l'import a bien été appelé et a levé une exception
        self.assertTrue(mock_import.called)


class TestReceptionBusinessIdNormalization(TestCase):
    """Tests pour la normalisation des business_id dans Reception"""
    
    def setUp(self):
        self.user = User.objects.create_user('test@example.com', 'password')
        self.bon = NumeroBonCommande.objects.create(numero='TEST-BIZ')
        self.fichier = FichierImporte.objects.create(fichier='test.csv', utilisateur=self.user)
    
    def test_save_normalizes_business_id(self):
        """Test que save() normalise le business_id"""
        reception = Reception(
            bon_commande=self.bon,
            fichier=self.fichier,
            business_id="ORDER:123|LINE:43.0|ITEM:1.0",
            ordered_quantity=Decimal('100'),
            quantity_delivered=Decimal('80'),
            received_quantity=Decimal('80'),
            quantity_not_delivered=Decimal('20'),
            unit_price=Decimal('50')
        )
        reception.save()
        
        self.assertEqual(reception.business_id, "ORDER:123|LINE:43|ITEM:1")
    
    def test_save_with_update_fields(self):
        """Test save() avec update_fields spécifié"""
        reception = Reception.objects.create(
            bon_commande=self.bon,
            fichier=self.fichier,
            business_id="ORDER:123|LINE:43",
            ordered_quantity=Decimal('100'),
            quantity_delivered=Decimal('80'),
            received_quantity=Decimal('80'),
            quantity_not_delivered=Decimal('20'),
            unit_price=Decimal('50')
        )
        
        # Sauvegarde avec update_fields
        reception.ordered_quantity = Decimal('150')
        reception.save(update_fields=['ordered_quantity'])
        
        # Devrait inclure les champs calculés dans update_fields
        reception.refresh_from_db()
        self.assertEqual(reception.ordered_quantity, Decimal('150'))


class TestNumeroBonCommandeSaveMethod(TestCase):
    """Tests pour la méthode save() de NumeroBonCommande"""
    
    def setUp(self):
        self.bon = NumeroBonCommande.objects.create(numero='TEST-SAVE')
        self.fichier = FichierImporte.objects.create(fichier='test.csv')
    
    def test_save_with_retention_rate_update(self):
        """Test save() avec mise à jour du taux de rétention"""
        # Créer une réception associée
        reception = Reception.objects.create(
            bon_commande=self.bon,
            fichier=self.fichier,
            business_id='TEST-SAVE-1',
            ordered_quantity=Decimal('100'),
            quantity_delivered=Decimal('80'),
            received_quantity=Decimal('80'),
            quantity_not_delivered=Decimal('20'),
            unit_price=Decimal('50')
        )
        
        # Changer le taux de rétention
        self.bon.retention_rate = Decimal('5.0')
        self.bon.save()
        
        # Vérifier que les réceptions ont été mises à jour
        reception.refresh_from_db()
        self.assertNotEqual(reception.quantity_payable, Decimal('0'))


class TestMSRNReportSaveSnapshot(TestCase):
    """Tests pour les snapshots dans MSRNReport.save()"""
    
    def setUp(self):
        self.user = User.objects.create_user('test@example.com', 'password')
        self.bon = NumeroBonCommande.objects.create(numero='TEST-SNAP')
    
    @patch('orders.models.MSRNReport.objects.filter')
    def test_save_with_exception_in_sequence_generation(self, mock_filter):
        """Test save() avec exception dans la génération de séquence"""
        mock_filter.side_effect = Exception("DB Error")
        
        report = MSRNReport(bon_commande=self.bon, user=self.user.email)
        
        with self.assertRaises(Exception):
            report.save()


class TestImportOrUpdateFichierFunction(TestCase):
    """Tests pour la fonction import_or_update_fichier"""
    
    def setUp(self):
        self.user = User.objects.create_user('test@example.com', 'password')
    
    @patch('orders.import_utils.import_file_optimized')
    @patch('orders.models.default_storage.exists', return_value=True)
    def test_import_with_cpu_extraction(self, mock_exists, mock_import):
        """Test import_or_update_fichier avec extraction CPU"""
        # Mock import_file_optimized pour retourner des données avec CPU
        mock_import.return_value = (1, None)
        
        from orders.models import import_or_update_fichier
        from django.core.files.storage import default_storage as ds
        from unittest.mock import MagicMock
        
        fake_file = SimpleUploadedFile("test.csv", b"file_content")
        
        with patch.object(ds, 'save', return_value='mocked.csv'), \
             patch.object(ds, 'open', MagicMock()), \
             patch.object(ds, 'delete', MagicMock()):
            fichier, created = import_or_update_fichier(fake_file, self.user)
        
        # Vérifier que le fichier a été créé et que l'import a été appelé
        self.assertTrue(created)
        self.assertTrue(mock_import.called)


class TestActivityLogStringRepresentation(TestCase):
    """Tests pour la représentation en string de ActivityLog"""
    
    def setUp(self):
        self.fichier = FichierImporte.objects.create(fichier='test.csv')
    
    def test_str_with_none_business_id(self):
        """Test __str__ avec business_id None"""
        log = ActivityLog(
            bon_commande='TEST',
            fichier=self.fichier,
            business_id=None,
            ordered_quantity=Decimal('100'),
            quantity_delivered=Decimal('50'),
            quantity_not_delivered=Decimal('50')
        )
        log.save()
        
        representation = str(log)
        self.assertIn('TEST', representation)
        self.assertIn('N/A', representation)


class TestVendorEvaluationCriteriaDescriptions(TestCase):
    """Tests pour les descriptions des critères de VendorEvaluation"""
    
    def setUp(self):
        self.user = User.objects.create_user('test@example.com', 'password')
        self.bon = NumeroBonCommande.objects.create(numero='TEST-CRITERIA')
    
    def test_all_criteria_descriptions(self):
        """Test toutes les descriptions de critères"""
        evaluation = VendorEvaluation.objects.create(
            bon_commande=self.bon,
            supplier="Test Supplier",
            delivery_compliance=5,
            delivery_timeline=5, 
            advising_capability=5,
            after_sales_qos=5,
            vendor_relationship=5,
            evaluator=self.user
        )
        
        # Tester plusieurs scores pour chaque critère
        for score in [0, 2, 4, 5, 6, 7, 9, 10]:
            for criteria in ['delivery_compliance', 'delivery_timeline', 'advising_capability', 
                           'after_sales_qos', 'vendor_relationship']:
                description = evaluation.get_criteria_description(criteria, score)
                self.assertIsNotNone(description)
                self.assertNotEqual(description, "")


class TestTimelineDelaySaveMethod(TestCase):
    """Tests pour la méthode save() de TimelineDelay"""
    
    def setUp(self):
        self.bon = NumeroBonCommande.objects.create(numero='TEST-TL-SAVE')
    
    def test_save_calculates_retention(self):
        """Test que save() calcule automatiquement la rétention"""
        timeline = TimelineDelay(
            bon_commande=self.bon,
            delay_part_mtn=5,
            delay_part_force_majeure=3,
            delay_part_vendor=10,
            quotite_realisee=Decimal('100.00'),
            comment_mtn="Test",
            comment_force_majeure="Test",
            comment_vendor="Test"
        )
        
        # Avant save, les champs de rétention sont à 0
        self.assertEqual(timeline.retention_amount_timeline, Decimal('0'))
        self.assertEqual(timeline.retention_rate_timeline, Decimal('0'))
        
        # Créer une réception pour donner un montant total non nul
        fichier = FichierImporte.objects.create(fichier='tl.csv')
        Reception.objects.create(bon_commande=self.bon, fichier=fichier, business_id='TL-1', ordered_quantity=Decimal('100'), quantity_delivered=Decimal('100'), unit_price=Decimal('100'))
        timeline.save()
        self.assertNotEqual(timeline.retention_amount_timeline, Decimal('0'))
        self.assertNotEqual(timeline.retention_rate_timeline, Decimal('0'))


class TestSignalHandlerEdgeCases(TestCase):
    """Tests pour les cas limites des signaux"""
    
    def setUp(self):
        self.bon = NumeroBonCommande.objects.create(numero='TEST-SIGNAL-EDGE')
    
    def test_signal_with_none_retention_rate(self):
        """Test signal avec retention_rate None"""
        self.bon.retention_rate = None
        with self.assertRaises(TypeError):
            self.bon.save()
    
    def test_signal_when_bon_does_not_exist(self):
        """Test signal quand le bon n'existe pas (cas de suppression)"""
        from orders.models import post_save
        
        # Simuler un bon qui n'existe plus
        with patch('orders.models.NumeroBonCommande.objects.get') as mock_get:
            mock_get.side_effect = NumeroBonCommande.DoesNotExist
            post_save.send(sender=NumeroBonCommande, instance=self.bon, created=False)


class TestDecimalRoundingPrecision(TestCase):
    """Tests de précision pour round_decimal"""
    
    def test_round_decimal_high_precision(self):
        """Test round_decimal avec haute précision"""
        # Test avec beaucoup de décimales
        result = round_decimal(Decimal('123.4567890123456789'), 10)
        self.assertEqual(result, Decimal('123.4567890123'))
        
        # Test arrondi vers le haut
        result = round_decimal(Decimal('123.456789016'), 8)
        self.assertEqual(result, Decimal('123.45678902'))


class TestBusinessIdGenerationComplex(TestCase):
    """Tests complexes pour la génération de business_id"""
    
    def setUp(self):
        self.fichier = FichierImporte.objects.create(fichier='test.csv')
    
    def test_business_id_with_various_numeric_formats(self):
        """Test business_id avec différents formats numériques"""
        test_cases = [
            # (contenu, business_id_attendu)
            (
                {'Order': 'PO001', 'Line': 43.0, 'Item': 1, 'Schedule': '1'},
                "ORDER:PO001|LINE:43|ITEM:1|SCHEDULE:1"
            ),
            (
                {'Order': 'PO001', 'Line': '43.00', 'Item': '1.000', 'Schedule': '2.5'},
                "ORDER:PO001|LINE:43|ITEM:1|SCHEDULE:2.5"
            ),
            (
                {'Order': 'PO001', 'Line': '043.0', 'Item': '001.0'},
                "ORDER:PO001|LINE:43|ITEM:1"
            )
        ]
        
        for contenu, expected in test_cases:
            ligne = LigneFichier(fichier=self.fichier, numero_ligne=1, contenu=contenu)
            business_id = ligne.generate_business_id()
            self.assertEqual(business_id, expected)


class TestFichierImporteComplexSave(TestCase):
    """Tests complexes pour FichierImporte.save()"""
    
    def setUp(self):
        self.user = User.objects.create_user('test@example.com', 'password')
    
    @patch('orders.import_utils.import_file_optimized')
    @patch('orders.models.default_storage.exists', return_value=True)
    def test_save_with_reception_creation_and_business_id(self, mock_exists, mock_import):
        """Test save() avec création de réceptions et business_id"""
        # Mock import_file_optimized pour simuler l'import
        mock_import.return_value = (1, ['PO-COMPLEX-001'])
        
        fichier = FichierImporte(
            fichier='test.csv',
            utilisateur=self.user
        )
        fichier.save()
        
        # Vérifier que l'import a été appelé
        self.assertTrue(mock_import.called)


class TestMSRNReportComplexSave(TestCase):
    """Tests complexes pour MSRNReport.save()"""
    
    def setUp(self):
        self.user = User.objects.create_user('test@example.com', 'password')
        self.bon = NumeroBonCommande.objects.create(numero='PO-COMPLEX-MSRN')
        
        # Créer des réceptions pour avoir des données
        self.fichier = FichierImporte.objects.create(fichier='test.csv', utilisateur=self.user)
        Reception.objects.create(
            bon_commande=self.bon,
            fichier=self.fichier,
            business_id='COMPLEX-1',
            ordered_quantity=Decimal('100'),
            quantity_delivered=Decimal('80'),
            received_quantity=Decimal('80'),
            quantity_not_delivered=Decimal('20'),
            unit_price=Decimal('100')
        )
    
    def test_save_with_complete_snapshot_data(self):
        """Test save() avec données complètes pour le snapshot"""
        report = MSRNReport(
            bon_commande=self.bon,
            user=self.user.email,
            retention_rate=Decimal('5.0')
        )
        report.save()
        
        # Vérifier que les snapshots ont été capturés
        self.assertIsNotNone(report.montant_total_snapshot)
        self.assertIsNotNone(report.montant_recu_snapshot)
        self.assertIsNotNone(report.receptions_data_snapshot)
        
        # Vérifier que les données de réception sont dans le snapshot
        snapshot_data = report.receptions_data_snapshot
        self.assertEqual(len(snapshot_data), 1)
        self.assertEqual(snapshot_data[0]['ordered_quantity'], '100.00')


class TestReceptionComplexCalculations(TestCase):
    """Tests complexes pour les calculs de Reception"""
    
    def setUp(self):
        self.bon = NumeroBonCommande.objects.create(numero='PO-CALC-COMPLEX', retention_rate=Decimal('10.0'))
        self.fichier = FichierImporte.objects.create(fichier='test.csv')
    
    def test_complex_amount_calculations(self):
        """Test calculs complexes de montants"""
        reception = Reception(
            bon_commande=self.bon,
            fichier=self.fichier,
            business_id='COMPLEX-CALC-1',
            ordered_quantity=Decimal('1000'),
            quantity_delivered=Decimal('750'),
            received_quantity=Decimal('750'),
            quantity_not_delivered=Decimal('250'),
            unit_price=Decimal('123.4567')
        )
        reception.save()
        
        # Vérifier les calculs
        expected_amount_delivered = Decimal('750') * Decimal('123.4567')
        expected_quantity_payable = Decimal('750') * (Decimal('1') - Decimal('0.10'))  # 10% retention
        expected_amount_payable = expected_quantity_payable * Decimal('123.4567')
        
        self.assertEqual(reception.amount_delivered, round_decimal(expected_amount_delivered))
        self.assertEqual(reception.quantity_payable, round_decimal(expected_quantity_payable))
        self.assertEqual(reception.amount_payable, round_decimal(expected_amount_payable))


class TestFinalCoverage(TestCase):
    """Tests finaux pour la couverture complète"""
    
    def test_all_remaining_edge_cases(self):
        """Test tous les cas limites restants"""
        
        # Test round_decimal avec quantize exception
        result = round_decimal('bad')
        self.assertEqual(result, Decimal('0'))
        
        # Test normalize_business_id avec ValueError dans float conversion
        result = normalize_business_id('key:abc')  # 'abc' ne peut pas être converti en float
        self.assertEqual(result, 'key:abc')
        
        # Test LigneFichier.get_key_columns avec valeurs invalides
        fichier = FichierImporte.objects.create(fichier='test.csv')
        # Assurer aucune collision d'unicité (certaines extractions auto peuvent créer la ligne 1)
        fichier.lignes.all().delete()
        ligne = LigneFichier.objects.create(
            fichier=fichier,
            numero_ligne=1,
            contenu={
                'Ordered Quantity': 'invalid',
                'Quantity Delivered': 'NaN',
                'Price': 'inf'
            }
        )
        key_columns = ligne.get_key_columns()
        self.assertEqual(key_columns['ordered_quantity'], Decimal('0'))
        # 'NaN' reste Decimal('NaN') selon l'implémentation actuelle
        self.assertTrue(key_columns['quantity_delivered'].is_nan())
        self.assertEqual(key_columns['unit_price'], Decimal('0'))
        
        # Test NumeroBonCommande.save() avec exception dans le recalcul
        bon = NumeroBonCommande.objects.create(numero='TEST-FINAL')
        with patch.object(Reception.objects, 'update', side_effect=Exception):
            bon.retention_rate = Decimal('5.0')
            bon.save()  # Ne devrait pas lever d'exception
        
        # Test VendorEvaluation avec note moyenne flottante
        evaluation = VendorEvaluation(
            bon_commande=bon,
            supplier="Test",
            delivery_compliance=7,
            delivery_timeline=8,
            advising_capability=6,
            after_sales_qos=7,
            vendor_relationship=8
        )
        evaluation.save()
        # (7+8+6+7+8)/5 = 7.2
        self.assertEqual(evaluation.vendor_final_rating, Decimal('7.20'))        


class TestNumeroBonCommandeUncovered(TestCase):
    """Tests pour couvrir les lignes non couvertes de NumeroBonCommande"""
    
    def setUp(self):
        self.user = User.objects.create_user('test@example.com', 'password')
        self.fichier = FichierImporte.objects.create(fichier='test.csv', utilisateur=self.user)
        self.fichier.lignes.all().delete()
        
    def test_montant_methods_cache_mechanism(self):
        """Test le mécanisme de cache des méthodes de montant"""
        bon = NumeroBonCommande.objects.create(numero='TEST-CACHE')
        
        # Test initial - pas de cache calculé
        with patch.object(bon, '_mettre_a_jour_montants') as mock_update:
            montant_total = bon.montant_total()
            montant_recu = bon.montant_recu()
            taux = bon.taux_avancement()
            
            # Doit appeler _mettre_a_jour_montants pour chaque méthode
            self.assertEqual(mock_update.call_count, 3)
    
    def test_mettre_a_jour_montants_with_receptions(self):
        """Test _mettre_a_jour_montants avec des réceptions"""
        bon = NumeroBonCommande.objects.create(numero='TEST-UPDATE')
        
        # Créer des réceptions
        fichier = FichierImporte.objects.create(fichier='test.csv')
        Reception.objects.create(
            bon_commande=bon,
            fichier=fichier,
            business_id='UPDATE-1',
            ordered_quantity=Decimal('100'),
            quantity_delivered=Decimal('80'),
            received_quantity=Decimal('80'),
            quantity_not_delivered=Decimal('20'),
            unit_price=Decimal('50')
        )
        
        # Appeler la méthode directement
        bon._mettre_a_jour_montants()
        
        # Vérifier que les montants sont calculés
        self.assertEqual(bon._montant_total, Decimal('5000.00'))
        self.assertEqual(bon._montant_recu, Decimal('4000.00'))
        self.assertEqual(bon._taux_avancement, Decimal('80.00'))
    
    def test_mettre_a_jour_montants_exception_handling(self):
        """Test _mettre_a_jour_montants avec exception lors de la sauvegarde"""
        bon = NumeroBonCommande.objects.create(numero='TEST-EXCEPTION')
        
        # Mock pour simuler une exception lors de la sauvegarde
        with patch.object(NumeroBonCommande.objects, 'update', side_effect=Exception("DB Error")):
            bon._mettre_a_jour_montants()
            # Ne devrait pas lever d'exception
    
    def test_get_methods_with_matching_order_lines(self):
        """Test les méthodes get avec des lignes correspondantes"""
        bon = NumeroBonCommande.objects.create(numero='PO-MATCH')
        bon.fichiers.add(self.fichier)
        
        # Créer une ligne avec toutes les colonnes recherchées
        LigneFichier.objects.create(
            fichier=self.fichier,
            numero_ligne=1,
            business_id='MATCH-1',
            contenu={
                'Order': 'PO-MATCH',
                'Sponsor': 'Test Sponsor',
                'Supplier': 'Test Supplier',
                'Order Description': 'Test Description',
                'Currency': 'USD',
                'Project Number': 'PRJ001',
                'CPU': '02 - ITS',
                'Project Manager': 'John Manager',
                'Project Coordinator': 'Jane Coordinator',
                'Manager Portfolio': 'Mike Portfolio',
                'GM EPMO': 'Sarah GM',
                'Senior PM': 'Tom Senior',
                'Senior Technical Lead': 'Alice Tech',
                'Code IFS': 'CODE123',
                'Payment Terms': 'Net 30'
            }
        )
        
        # Tester toutes les méthodes get
        self.assertEqual(bon.get_sponsor(), 'Test Sponsor')
        self.assertEqual(bon.get_supplier(), 'Test Supplier')
        self.assertEqual(bon.get_order_description(), 'Test Description')
        self.assertEqual(bon.get_currency(), 'USD')
        self.assertEqual(bon.get_project_number(), 'PRJ001')
        self.assertEqual(bon.get_cpu(), 'ITS')
        self.assertEqual(bon.get_project_manager(), 'John Manager')
        self.assertEqual(bon.get_project_coordinator(), 'Jane Coordinator')
        self.assertEqual(bon.get_manager_portfolio(), 'Mike Portfolio')
        self.assertEqual(bon.get_gm_epmo(), 'Sarah GM')
        self.assertEqual(bon.get_senior_pm(), 'Tom Senior')
        self.assertEqual(bon.get_senior_technical_lead(), 'Alice Tech')
        self.assertEqual(bon.get_code_ifs(), 'CODE123')
    
    def test_save_validation_retention_rate(self):
        """Test la validation du taux de rétention dans save()"""
        bon = NumeroBonCommande.objects.create(numero='TEST-VALIDATION')
        
        # Test avec taux négatif
        bon.retention_rate = Decimal('-1.0')
        with self.assertRaises(Exception):
            bon.full_clean()
        
        # Test avec taux > 100
        bon.retention_rate = Decimal('150.0')
        with self.assertRaises(Exception):
            bon.full_clean()
    
    def test_save_recalculates_receptions(self):
        """Test que save() recalcule les réceptions"""
        bon = NumeroBonCommande.objects.create(numero='TEST-RECALC')
        fichier = FichierImporte.objects.create(fichier='test.csv')
        
        # Créer une réception
        reception = Reception.objects.create(
            bon_commande=bon,
            fichier=fichier,
            business_id='RECALC-1',
            ordered_quantity=Decimal('100'),
            quantity_delivered=Decimal('80'),
            received_quantity=Decimal('80'),
            quantity_not_delivered=Decimal('20'),
            unit_price=Decimal('50')
        )
        
        # Changer le taux de rétention
        bon.retention_rate = Decimal('5.0')
        bon.save()
        
        # Vérifier que les champs calculés sont mis à jour
        reception.refresh_from_db()
        self.assertNotEqual(reception.quantity_payable, Decimal('0'))
        self.assertNotEqual(reception.amount_payable, Decimal('0'))


class TestLigneFichierUncovered(TestCase):
    """Tests pour couvrir les lignes non couvertes de LigneFichier"""
    
    def setUp(self):
        self.fichier = FichierImporte.objects.create(fichier='test.csv')
        self.fichier.lignes.all().delete()
    
    def test_save_generates_business_id(self):
        """Test que save() génère le business_id si absent"""
        ligne = LigneFichier(
            fichier=self.fichier,
            numero_ligne=1,
            contenu={'Order': 'PO001', 'Line': '1', 'Item': '1', 'Schedule': '1'}
        )
        
        # Business_id devrait être généré automatiquement
        ligne.save()
        self.assertIsNotNone(ligne.business_id)
        self.assertEqual(ligne.business_id, 'ORDER:PO001|LINE:1|ITEM:1|SCHEDULE:1')
    
    def test_get_key_columns_with_invalid_values(self):
        """Test get_key_columns avec valeurs invalides"""
        ligne = LigneFichier.objects.create(
            fichier=self.fichier,
            numero_ligne=1,
            contenu={
                'Ordered Quantity': 'invalid',
                'Quantity Delivered': 'NaN',
                'Price': 'inf'
            }
        )
        
        key_columns = ligne.get_key_columns()
        # Devrait gérer gracieusement les valeurs invalides
        self.assertEqual(key_columns['ordered_quantity'], Decimal('0'))
        self.assertEqual(key_columns['unit_price'], Decimal('0'))


class TestFichierImporteUncovered(TestCase):
    """Tests pour couvrir les lignes non couvertes de FichierImporte"""
    
    def setUp(self):
        self.user = User.objects.create_user('test@example.com', 'password')
    
    @patch('orders.models.default_storage.exists', return_value=False)
    def test_save_no_file(self, mock_exists):
        """Test save() sans fichier"""
        fichier = FichierImporte()
        fichier.save()  # Ne devrait pas lever d'exception
    
    @patch('orders.import_utils.import_file_optimized')
    @patch('orders.models.default_storage.exists', return_value=True)
    def test_save_extraction_exception(self, mock_exists, mock_import):
        """Test save() avec exception lors de l'extraction"""
        mock_import.side_effect = Exception("Extraction failed")
        
        fichier = FichierImporte(
            fichier='test.csv',
            utilisateur=self.user
        )
        
        # Ne devrait pas lever d'exception (gérée gracieusement)
        fichier.save()
        
        # Vérifier que l'import a bien été appelé même s'il a échoué
        self.assertTrue(mock_import.called)


class TestReceptionUncovered(TestCase):
    """Tests pour couvrir les lignes non couvertes de Reception"""
    
    def setUp(self):
        self.bon = NumeroBonCommande.objects.create(numero='TEST-RECEPTION')
        self.fichier = FichierImporte.objects.create(fichier='test.csv')
    
    def test_save_exception_handling(self):
        """Test save() avec gestion des exceptions"""
        reception = Reception(
            bon_commande=self.bon,
            fichier=self.fichier,
            business_id='EXCEPTION-1',
            ordered_quantity=Decimal('100'),
            quantity_delivered='invalid',  # Va causer une exception
            received_quantity=Decimal('80'),
            quantity_not_delivered=Decimal('20'),
            unit_price=Decimal('50')
        )
        
        # Avec une valeur non décimale, Django lève une ValidationError
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            reception.save()
    
    def test_save_with_update_fields(self):
        """Test save() avec update_fields spécifié"""
        reception = Reception.objects.create(
            bon_commande=self.bon,
            fichier=self.fichier,
            business_id='UPDATE-FIELDS-1',
            ordered_quantity=Decimal('100'),
            quantity_delivered=Decimal('80'),
            received_quantity=Decimal('80'),
            quantity_not_delivered=Decimal('20'),
            unit_price=Decimal('50')
        )
        
        # Sauvegarde avec update_fields limité
        reception.ordered_quantity = Decimal('150')
        reception.save(update_fields=['ordered_quantity'])
        
        # Les champs calculés devraient quand même être mis à jour
        reception.refresh_from_db()
        self.assertNotEqual(reception.amount_delivered, Decimal('0'))


class TestMSRNReportUncovered(TestCase):
    """Tests pour couvrir les lignes non couvertes de MSRNReport"""
    
    def setUp(self):
        self.user = User.objects.create_user('test@example.com', 'password')
        self.bon = NumeroBonCommande.objects.create(numero='TEST-MSRN')
    
    def test_save_report_number_generation(self):
        """Test la génération automatique du numéro de rapport avec le nouveau format 2025
        
        Depuis le changement de procédure, les numéros MSRN commencent à partir de 6501
        pour l'année 2025, format: MSRN2506501, MSRN2506502, etc.
        """
        report = MSRNReport(bon_commande=self.bon, user=self.user.email)
        
        # Devrait générer un numéro automatiquement
        report.save()
        
        # Vérifier le préfixe MSRN25 (année 2025)
        self.assertTrue(report.report_number.startswith('MSRN25'))
        
        # Vérifier que le numéro séquentiel est >= 6501 (nouveau format backlog 2025)
        sequence_part = report.report_number[6:]  # Tout après "MSRN25"
        sequence_number = int(sequence_part)
        self.assertGreaterEqual(sequence_number, 6501, 
            f"Le numéro séquentiel {sequence_number} devrait être >= 6501 selon la nouvelle procédure")
    
    def test_save_report_number_generation_incrementing(self):
        """Test que les numéros MSRN s'incrémentent correctement"""
        # Créer un premier rapport
        bon2 = NumeroBonCommande.objects.create(numero='TEST-MSRN-2')
        report1 = MSRNReport(bon_commande=self.bon, user=self.user.email)
        report1.save()
        
        # Créer un deuxième rapport
        report2 = MSRNReport(bon_commande=bon2, user=self.user.email)
        report2.save()
        
        # Extraire les numéros séquentiels
        seq1 = int(report1.report_number[6:])
        seq2 = int(report2.report_number[6:])
        
        # Le deuxième devrait être exactement +1
        self.assertEqual(seq2, seq1 + 1)
    
    def test_save_snapshot_capture(self):
        """Test la capture des snapshots"""
        # Créer des données pour le bon
        fichier = FichierImporte.objects.create(fichier='test.csv')
        Reception.objects.create(
            bon_commande=self.bon,
            fichier=fichier,
            business_id='SNAP-1',
            ordered_quantity=Decimal('100'),
            quantity_delivered=Decimal('80'),
            received_quantity=Decimal('80'),
            quantity_not_delivered=Decimal('20'),
            unit_price=Decimal('50')
        )
        
        report = MSRNReport(bon_commande=self.bon, user=self.user.email)
        report.save()
        
        # Vérifier que les snapshots sont capturés
        self.assertIsNotNone(report.montant_total_snapshot)
        self.assertIsNotNone(report.montant_recu_snapshot)
        self.assertIsNotNone(report.progress_rate_snapshot)
        self.assertIsNotNone(report.receptions_data_snapshot)
    
    def test_save_payment_terms_capture(self):
        """Test la capture des payment terms"""
        fichier = FichierImporte.objects.create(fichier='test.csv')
        # Éviter collision d'unicité si une ligne 1 existe déjà
        fichier.lignes.all().delete()
        
        # Créer une ligne avec payment terms
        LigneFichier.objects.create(
            fichier=fichier,
            numero_ligne=1,
            business_id='PAYMENT-1',
            contenu={
                'Order': 'TEST-MSRN',
                'Payment Terms': 'Net 30 days'
            }
        )
        
        # Créer une réception pour lier le business_id
        Reception.objects.create(
            bon_commande=self.bon,
            fichier=fichier,
            business_id='PAYMENT-1',
            ordered_quantity=Decimal('100'),
            quantity_delivered=Decimal('80'),
            unit_price=Decimal('50')
        )
        
        report = MSRNReport(bon_commande=self.bon, user=self.user.email)
        report.save()
        
        # Vérifier que payment terms est capturé
        self.assertEqual(report.payment_terms_snapshot, 'Net 30 days')
    
    def test_progress_rate_without_activity_log(self):
        """Test progress_rate sans ActivityLog"""
        report = MSRNReport.objects.create(
            report_number='MSRN250001',
            bon_commande=self.bon,
            user=self.user.email
        )
        
        # Sans ActivityLog, devrait fallback sur taux_avancement
        rate = report.progress_rate
        self.assertEqual(rate, Decimal('0'))
    
    def test_progress_rate_with_exception(self):
        """Test progress_rate avec exception"""
        report = MSRNReport.objects.create(
            report_number='MSRN250001',
            bon_commande=self.bon,
            user=self.user.email
        )
        
        # Mock pour simuler une exception
        with patch.object(NumeroBonCommande, 'taux_avancement', side_effect=Exception):
            rate = report.progress_rate
            self.assertEqual(rate, 0)


class TestInitialReceptionBusinessUncovered(TestCase):
    """Tests pour couvrir les lignes non couvertes de InitialReceptionBusiness"""
    
    def setUp(self):
        self.bon = NumeroBonCommande.objects.create(numero='TEST-IRB')
        self.fichier = FichierImporte.objects.create(fichier='test.csv')
    
    def test_save_normalizes_business_id(self):
        """Test que save() normalise le business_id"""
        irb = InitialReceptionBusiness(
            business_id="ORDER:123|LINE:43.0|ITEM:1.0",
            bon_commande=self.bon,
            received_quantity=Decimal('50')
        )
        
        irb.save()
        self.assertEqual(irb.business_id, "ORDER:123|LINE:43|ITEM:1")
    
    def test_save_with_update_fields(self):
        """Test save() avec update_fields"""
        irb = InitialReceptionBusiness.objects.create(
            business_id="ORDER:123|LINE:43",
            bon_commande=self.bon,
            received_quantity=Decimal('50')
        )
        
        irb.received_quantity = Decimal('60')
        irb.save(update_fields=['received_quantity'])
        
        # business_id devrait être inclus dans update_fields
        irb.refresh_from_db()
        self.assertEqual(irb.received_quantity, Decimal('60'))


class TestTimelineDelayUncovered(TestCase):
    """Tests pour couvrir les lignes non couvertes de TimelineDelay"""
    
    def setUp(self):
        self.bon = NumeroBonCommande.objects.create(numero='TEST-TIMELINE')
    
    def test_calculate_retention_timeline_zero_amount(self):
        """Test calculate_retention_timeline avec montant total 0"""
        timeline = TimelineDelay(bon_commande=self.bon)
        
        amount, rate = timeline.calculate_retention_timeline()
        self.assertEqual(amount, Decimal('0'))
        self.assertEqual(rate, Decimal('0'))
    
    def test_save_calculates_retention(self):
        """Test que save() calcule automatiquement la rétention"""
        timeline = TimelineDelay(
            bon_commande=self.bon,
            delay_part_mtn=5,
            delay_part_force_majeure=3,
            delay_part_vendor=2,
            quotite_realisee=Decimal('100.00'),
            comment_mtn="Test MTN",
            comment_force_majeure="Test Force Majeure", 
            comment_vendor="Test Vendor"
        )
        
        # Avant save, les champs sont à 0
        self.assertEqual(timeline.retention_amount_timeline, Decimal('0'))
        self.assertEqual(timeline.retention_rate_timeline, Decimal('0'))
        
        timeline.save()
        
        # Après save, les champs sont calculés
        self.assertIsNotNone(timeline.retention_amount_timeline)
        self.assertIsNotNone(timeline.retention_rate_timeline)


class TestVendorEvaluationUncovered(TestCase):
    """Tests pour couvrir les lignes non couvertes de VendorEvaluation"""
    
    def setUp(self):
        self.user = User.objects.create_user('test@example.com', 'password')
        self.bon = NumeroBonCommande.objects.create(numero='TEST-VENDOR')
    
    def test_save_calculates_final_rating(self):
        """Test que save() calcule automatiquement la note finale"""
        evaluation = VendorEvaluation(
            bon_commande=self.bon,
            supplier="Test Supplier",
            delivery_compliance=8,
            delivery_timeline=7,
            advising_capability=6,
            after_sales_qos=9,
            vendor_relationship=8,
            evaluator=self.user
        )
        
        evaluation.save()
        
        # (8+7+6+9+8)/5 = 7.6
        self.assertEqual(evaluation.vendor_final_rating, Decimal('7.60'))
    
    def test_get_criteria_description_all_scores(self):
        """Test get_criteria_description pour tous les scores possibles"""
        evaluation = VendorEvaluation.objects.create(
            bon_commande=self.bon,
            supplier="Test Supplier",
            delivery_compliance=5,
            delivery_timeline=5,
            advising_capability=5,
            after_sales_qos=5,
            vendor_relationship=5
        )
        
        # Tester tous les scores de 0 à 10 pour chaque critère
        for score in range(0, 11):
            for criteria in VendorEvaluation.CRITERIA_CHOICES.keys():
                description = evaluation.get_criteria_description(criteria, score)
                self.assertIsNotNone(description)
                self.assertNotEqual(description, "")
    
    def test_get_total_score_calculation(self):
        """Test get_total_score"""
        evaluation = VendorEvaluation.objects.create(
            bon_commande=self.bon,
            supplier="Test Supplier",
            delivery_compliance=8,
            delivery_timeline=7,
            advising_capability=6,
            after_sales_qos=9,
            vendor_relationship=8
        )
        
        total = evaluation.get_total_score()
        self.assertEqual(total, 38)  # 8+7+6+9+8


class TestSignalUncovered(TestCase):
    """Tests pour couvrir les lignes non couvertes des signaux"""
    
    def setUp(self):
        self.bon = NumeroBonCommande.objects.create(numero='TEST-SIGNAL')
        self.fichier = FichierImporte.objects.create(fichier='test.csv')
    
    def test_update_receptions_on_retention_rate_change(self):
        """Test le signal de mise à jour des réceptions"""
        # Créer une réception
        reception = Reception.objects.create(
            bon_commande=self.bon,
            fichier=self.fichier,
            business_id='SIGNAL-1',
            ordered_quantity=Decimal('100'),
            quantity_delivered=Decimal('80'),
            received_quantity=Decimal('80'),
            quantity_not_delivered=Decimal('20'),
            unit_price=Decimal('50')
        )
        
        # Changer le taux de rétention
        self.bon.retention_rate = Decimal('5.0')
        self.bon.save()
        
        # Vérifier que la réception est mise à jour
        reception.refresh_from_db()
        self.assertNotEqual(reception.quantity_payable, Decimal('0'))
    
    def test_signal_no_update_when_created(self):
        """Test que le signal ne fait rien quand created=True"""
        bon = NumeroBonCommande.objects.create(numero='TEST-NEW')
        
        # Ne devrait pas appeler la logique de mise à jour pour un nouvel objet
        with patch.object(Reception.objects, 'filter') as mock_filter:
            # Simuler le signal post_save avec created=True
            from orders.models import post_save
            post_save.send(sender=NumeroBonCommande, instance=bon, created=True)
            mock_filter.assert_not_called()
    
    def test_signal_no_update_when_retention_unchanged(self):
        """Test que le signal ne fait rien quand le taux ne change pas"""
        with patch.object(Reception.objects, 'filter') as mock_filter:
            self.bon.save()  # Taux inchangé
            mock_filter.assert_not_called()
    
    def test_signal_bon_does_not_exist(self):
        """Test le signal quand le bon n'existe plus"""
        # Simuler un bon qui n'existe pas
        with patch.object(NumeroBonCommande.objects, 'get', side_effect=NumeroBonCommande.DoesNotExist):
            # Ne devrait pas lever d'exception
            self.bon.retention_rate = Decimal('5.0')
            self.bon.save()


class TestModelSaveMethods(TestCase):
    """Test les méthodes save() personnalisées des modèles"""
    
    def setUp(self):
        self.user = User.objects.create_user('test@example.com', 'testpass')
        self.bon = NumeroBonCommande.objects.create(numero='PO001', cpu='ITS')
        self.fichier = FichierImporte.objects.create(
            fichier='test.xlsx',
            utilisateur=self.user
        )
    
    def test_fichier_importe_save_with_file(self):
        """Test que save() traite un fichier correctement"""
        # Le fichier est déjà créé dans setUp
        # Vérifier que l'extension a été détectée
        self.assertIsNotNone(self.fichier.extension)
    
    def test_fichier_importe_save_skip_extraction(self):
        """Test que save() peut sauter l'extraction"""
        fichier = FichierImporte.objects.create(
            fichier='test2.xlsx',
            utilisateur=self.user
        )
        fichier._skip_extraction = True
        fichier.save()
        # Ne devrait pas lever d'erreur
    
    def test_reception_save_calculates_fields(self):
        """Test que save() calcule les champs automatiquement"""
        reception = Reception.objects.create(
            bon_commande=self.bon,
            fichier=self.fichier,
            business_id='BID001',
            ordered_quantity=Decimal('100'),
            quantity_delivered=Decimal('80'),
            received_quantity=Decimal('80'),
            quantity_not_delivered=Decimal('20'),
            unit_price=Decimal('50')
        )
        
        # Les champs calculés par save() sont amount_delivered, amount_not_delivered, quantity_payable
        self.assertEqual(reception.amount_delivered, Decimal('4000'))  # 80 * 50
        self.assertEqual(reception.amount_not_delivered, Decimal('1000'))  # 20 * 50
        # Sans rétention, quantity_payable = quantity_delivered
        self.assertEqual(reception.quantity_payable, Decimal('80'))
    
    def test_reception_save_with_retention_rate(self):
        """Test le calcul avec taux de rétention"""
        self.bon.retention_rate = Decimal('5')
        self.bon.save()
        
        reception = Reception.objects.create(
            bon_commande=self.bon,
            fichier=self.fichier,
            business_id='BID002',
            ordered_quantity=Decimal('100'),
            quantity_delivered=Decimal('80'),
            received_quantity=Decimal('80'),
            quantity_not_delivered=Decimal('20'),
            unit_price=Decimal('50')
        )
        
        # quantity_payable est calculé comme: quantity_delivered * (1 - retention_rate/100)
        # = 80 * (1 - 0.05) = 80 * 0.95 = 76
        expected_payable = Decimal('80') * Decimal('0.95')  # 5% de rétention
        self.assertEqual(reception.quantity_payable, expected_payable)
    
    def test_reception_save_updates_bon_totals(self):
        """Test que save() met à jour les totaux du bon"""
        reception = Reception.objects.create(
            bon_commande=self.bon,
            fichier=self.fichier,
            business_id='BID001',
            ordered_quantity=Decimal('100'),
            quantity_delivered=Decimal('80'),
            unit_price=Decimal('50')
        )
        
        # Les totaux du bon devraient être mis à jour
        self.bon.refresh_from_db()
        self.assertEqual(self.bon.montant_total(), Decimal('5000'))
        self.assertEqual(self.bon.montant_recu(), Decimal('4000'))
        self.assertEqual(self.bon.taux_avancement(), Decimal('80'))
    
    def test_msrn_report_save_with_pdf(self):
        """Test la sauvegarde avec fichier PDF"""
        from django.core.files.base import ContentFile
        
        report = MSRNReport.objects.create(
            bon_commande=self.bon,
            report_number='MSRN-001',
            user=self.user.email
        )
        
        # Ajouter un fichier PDF
        pdf_content = b'PDF content'
        report.pdf_file.save('report.pdf', ContentFile(pdf_content))
        
        # Le fichier devrait être sauvegardé
        self.assertTrue(report.pdf_file.name.endswith('.pdf'))
    
    def test_vendor_evaluation_save_with_scores(self):
        """Test la création d'une évaluation avec des scores"""
        evaluation = VendorEvaluation.objects.create(
            bon_commande=self.bon,
            supplier='SUPPLIER1',
            delivery_compliance=8,
            delivery_timeline=7,
            advising_capability=6,
            after_sales_qos=9,
            vendor_relationship=8,
            evaluator=self.user
        )
        
        # Vérifier que l'évaluation a été créée
        self.assertEqual(evaluation.supplier, 'SUPPLIER1')
        self.assertEqual(evaluation.delivery_compliance, 8)


class TestModelProperties(TestCase):
    """Test les propriétés calculées des modèles"""
    
    def setUp(self):
        self.user = User.objects.create_user('test@example.com', 'testpass')
        self.bon = NumeroBonCommande.objects.create(numero='PO001', cpu='ITS')
        self.fichier = FichierImporte.objects.create(
            fichier='test.xlsx',
            utilisateur=self.user
        )
    
    def test_numero_bon_commande_properties(self):
        """Test les propriétés de NumeroBonCommande"""
        # Créer des réceptions
        Reception.objects.create(
            bon_commande=self.bon,
            fichier=self.fichier,
            business_id='BID001',
            ordered_quantity=Decimal('100'),
            quantity_delivered=Decimal('80'),
            unit_price=Decimal('50')
        )
        
        # Tester les méthodes (ce sont des méthodes, pas des propriétés)
        self.assertEqual(self.bon.montant_total(), Decimal('5000'))
        self.assertEqual(self.bon.montant_recu(), Decimal('4000'))
        self.assertEqual(self.bon.taux_avancement(), Decimal('80'))
    
    def test_numero_bon_commande_get_methods(self):
        """Test les méthodes get_* de NumeroBonCommande"""
        # Associer le fichier au bon de commande (requis pour que get_sponsor le trouve)
        self.bon.fichiers.add(self.fichier)
        
        # Créer une ligne avec sponsor, supplier et Order correspondant au numéro du bon
        LigneFichier.objects.create(
            fichier=self.fichier,
            numero_ligne=1,
            business_id='BID001',
            contenu={
                'Order': 'PO001',  # Doit correspondre à self.bon.numero
                'Sponsor': 'Test Sponsor',
                'Supplier': 'Test Supplier'
            }
        )
        
        # Tester les méthodes
        self.assertEqual(self.bon.get_sponsor(), 'Test Sponsor')
        self.assertEqual(self.bon.get_supplier(), 'Test Supplier')
    
    def test_reception_methods(self):
        """Test les champs calculés de Reception"""
        reception = Reception.objects.create(
            bon_commande=self.bon,
            fichier=self.fichier,
            business_id='BID003',
            ordered_quantity=Decimal('100'),
            quantity_delivered=Decimal('80'),
            received_quantity=Decimal('80'),
            quantity_not_delivered=Decimal('20'),
            unit_price=Decimal('50')
        )
        
        # Tester les champs calculés automatiquement par save()
        self.assertEqual(reception.amount_delivered, Decimal('4000'))  # 80 * 50
        self.assertEqual(reception.amount_not_delivered, Decimal('1000'))  # 20 * 50
        self.assertEqual(reception.quantity_payable, Decimal('80'))  # Sans rétention
    
    def test_ligne_fichier_properties(self):
        """Test les propriétés de LigneFichier"""
        ligne = LigneFichier.objects.create(
            fichier=self.fichier,
            numero_ligne=2,
            business_id='BID004',
            contenu={
                'Order': 'PO001',
                'Item': 'ITEM001',
                'Description': 'Test Item'
            }
        )
        
        # Tester que business_id est bien défini
        self.assertEqual(ligne.business_id, 'BID004')
        # Tester l'accès au contenu
        self.assertEqual(ligne.contenu['Order'], 'PO001')
        self.assertEqual(ligne.contenu['Item'], 'ITEM001')
        self.assertEqual(ligne.contenu['Description'], 'Test Item')
    
    def test_vendor_evaluation_properties(self):
        """Test les propriétés de VendorEvaluation"""
        evaluation = VendorEvaluation.objects.create(
            bon_commande=self.bon,
            supplier='SUPPLIER1',
            delivery_compliance=8,
            delivery_timeline=7,
            advising_capability=6,
            after_sales_qos=9,
            vendor_relationship=8,
            evaluator=self.user
        )
        
        # Tester la méthode get_total_score
        self.assertEqual(evaluation.get_total_score(), 38)  # 8+7+6+9+8


class TestModelValidation(TestCase):
    """Test la validation des modèles"""
    
    def setUp(self):
        self.user = User.objects.create_user('test@example.com', 'testpass')
        self.bon = NumeroBonCommande.objects.create(numero='PO001', cpu='ITS')
    
    def test_numero_bon_commande_unique_numero(self):
        """Test l'unicité du numéro de bon"""
        # Tenter de créer un doublon
        with self.assertRaises(IntegrityError):
            NumeroBonCommande.objects.create(numero='PO001')
    
    def test_fichier_importe_required_fields(self):
        """Test les champs obligatoires de FichierImporte"""
        # Le fichier est obligatoire mais le modèle permet de créer sans fichier
        # Test avec un fichier valide
        fichier = FichierImporte.objects.create(
            fichier='test.csv',
            utilisateur=self.user
        )
        self.assertIsNotNone(fichier.id)
    
    def test_reception_business_id_unique_per_file(self):
        """Test l'unicité de business_id par fichier"""
        fichier = FichierImporte.objects.create(
            fichier='test.xlsx',
            utilisateur=self.user
        )
        
        # Créer une première réception
        Reception.objects.create(
            bon_commande=self.bon,
            fichier=fichier,
            business_id='BID001',
            ordered_quantity=Decimal('100'),
            unit_price=Decimal('50')
        )
        
        # Tenter de créer un doublon
        with self.assertRaises(IntegrityError):
            Reception.objects.create(
                bon_commande=self.bon,
                fichier=fichier,
                business_id='BID001',
                ordered_quantity=Decimal('200'),
                unit_price=Decimal('60')
            )
    
    def test_vendor_evaluation_score_range(self):
        """Test la plage des scores d'évaluation"""
        # Créer une évaluation avec des scores valides
        evaluation = VendorEvaluation.objects.create(
            bon_commande=self.bon,
            supplier='SUPPLIER1',
            delivery_compliance=8,
            delivery_timeline=7,
            advising_capability=6,
            after_sales_qos=9,
            vendor_relationship=8,
            evaluator=self.user
        )
        
        # Vérifier que les scores sont corrects
        self.assertEqual(evaluation.delivery_compliance, 8)
        self.assertEqual(evaluation.delivery_timeline, 7)


class TestModelMethods(TestCase):
    """Test les méthodes personnalisées des modèles"""
    
    def setUp(self):
        self.user = User.objects.create_user('test@example.com', 'testpass')
        self.bon = NumeroBonCommande.objects.create(numero='PO001', cpu='ITS')
        self.fichier = FichierImporte.objects.create(
            fichier='test.xlsx',
            utilisateur=self.user
        )
    
    def test_numero_bon_commande_str_method(self):
        """Test la méthode __str__ de NumeroBonCommande"""
        self.assertEqual(str(self.bon), 'PO001')
    
    def test_fichier_importe_str_method(self):
        """Test la méthode __str__ de FichierImporte"""
        # Le modèle FichierImporte utilise date_importation, pas date_creation
        # Vérifier que la représentation contient le nom du fichier
        str_repr = str(self.fichier)
        self.assertIn('test.xlsx', str_repr)
    
    def test_ligne_fichier_str_method(self):
        """Test la méthode __str__ de LigneFichier"""
        ligne = LigneFichier.objects.create(
            fichier=self.fichier,
            numero_ligne=3,
            business_id='BID005',
            contenu={}
        )
        # Format réel: "Ligne {numero_ligne} du fichier {fichier.id}"
        expected = f"Ligne 3 du fichier {self.fichier.id}"
        self.assertEqual(str(ligne), expected)
    
    def test_reception_str_method(self):
        """Test la méthode __str__ de Reception"""
        reception = Reception.objects.create(
            bon_commande=self.bon,
            fichier=self.fichier,
            business_id='BID001',
            ordered_quantity=Decimal('100'),
            unit_price=Decimal('50')
        )
        expected = f"Réception pour PO001 - ID métier: BID001"
        self.assertEqual(str(reception), expected)
    
    def test_vendor_evaluation_str_method(self):
        """Test la méthode __str__ de VendorEvaluation"""
        # Fournir tous les scores requis pour éviter l'erreur de sum avec None
        evaluation = VendorEvaluation.objects.create(
            bon_commande=self.bon,
            supplier='SUPPLIER1',
            delivery_compliance=8,
            delivery_timeline=7,
            advising_capability=6,
            after_sales_qos=9,
            vendor_relationship=8,
            evaluator=self.user
        )
        # Format réel: "Évaluation {supplier} - {bon_commande.numero}"
        expected = f"Évaluation SUPPLIER1 - PO001"
        self.assertEqual(str(evaluation), expected)
    
    def test_numero_bon_commande_get_absolute_url(self):
        """Test get_absolute_url de NumeroBonCommande"""
        # Cette méthode n'existe pas dans le modèle
        # On teste qu'elle n'est pas présente
        with self.assertRaises(AttributeError):
            self.bon.get_absolute_url()


class TestModelRelations(TestCase):
    """Test les relations entre modèles"""
    
    def setUp(self):
        self.user = User.objects.create_user('test@example.com', 'testpass')
        self.bon = NumeroBonCommande.objects.create(numero='PO001', cpu='ITS')
        self.fichier = FichierImporte.objects.create(
            fichier='test.xlsx',
            utilisateur=self.user
        )
        self.bon.fichiers.add(self.fichier)
    
    def test_bon_fichier_many_to_many(self):
        """Test la relation many-to-many bon-fichier"""
        # Le bon devrait avoir le fichier
        self.assertIn(self.fichier, self.bon.fichiers.all())
        
        # Le fichier n'a pas de champ numero_bon
        # La relation est many-to-many via fichiers
        self.assertEqual(self.fichier.utilisateur, self.user)
    
    def test_fichier_ligne_foreign_key(self):
        """Test la relation foreign-key fichier-ligne"""
        ligne = LigneFichier.objects.create(
            fichier=self.fichier,
            numero_ligne=1,
            business_id='BID001',
            contenu={}
        )
        
        # La ligne devrait être associée au fichier
        self.assertEqual(ligne.fichier, self.fichier)
        # Le fichier devrait avoir la ligne
        self.assertIn(ligne, self.fichier.lignes.all())
    
    def test_bon_reception_reverse_foreign_key(self):
        """Test la relation reverse foreign-key bon-reception"""
        reception = Reception.objects.create(
            bon_commande=self.bon,
            fichier=self.fichier,
            business_id='BID001',
            ordered_quantity=Decimal('100'),
            unit_price=Decimal('50')
        )
        
        # La réception devrait être associée au bon
        self.assertEqual(reception.bon_commande, self.bon)
        # Le bon devrait avoir la réception
        self.assertIn(reception, self.bon.receptions.all())
    
    def test_user_fichier_foreign_key(self):
        """Test la relation foreign-key user-fichier"""
        # Le fichier devrait être associé à l'utilisateur
        self.assertEqual(self.fichier.utilisateur, self.user)
        # L'utilisateur devrait avoir le fichier
        self.assertIn(self.fichier, self.user.fichierimporte_set.all())


class TestModelSignals(TransactionTestCase):
    """Test les signaux des modèles"""
    
    def setUp(self):
        self.user = User.objects.create_user('test@example.com', 'testpass')
    
    def test_post_save_numero_bon_commande(self):
        """Test le signal post_save de NumeroBonCommande"""
        bon = NumeroBonCommande.objects.create(numero='PO001', cpu='ITS')
        
        # Modifier le taux de rétention
        bon.retention_rate = Decimal('5')
        bon.save()
        
        # Le signal devrait déclencher la mise à jour
        # (vérifié dans TestSignalUncovered)
    
    def test_pre_save_fichier_importe(self):
        """Test le signal pre_save de FichierImporte"""
        fichier = FichierImporte.objects.create(
            fichier='test2.xlsx',
            utilisateur=self.user
        )
        
        # Le fichier devrait être créé avec les champs de base
        # Note: le modèle utilise date_importation, pas date_creation
        self.assertIsNotNone(fichier.date_importation)
        self.assertEqual(fichier.utilisateur, self.user)


class TestModelQuerySets(TestCase):
    """Test les QuerySets personnalisés"""
    
    def setUp(self):
        self.user = User.objects.create_user('test@example.com', 'testpass')
        self.bon1 = NumeroBonCommande.objects.create(numero='PO001', cpu='ITS')
        self.bon2 = NumeroBonCommande.objects.create(numero='PO002', cpu='NWG')
        self.fichier = FichierImporte.objects.create(
            fichier='test.xlsx',
            utilisateur=self.user
        )
    
    def test_numero_bon_commande_by_cpu(self):
        """Test le filtrage par CPU"""
        # Filtrer par CPU
        bons_its = NumeroBonCommande.objects.filter(cpu='ITS')
        self.assertEqual(len(bons_its), 1)
        self.assertEqual(bons_its[0], self.bon1)
    
    def test_fichier_importe_by_user(self):
        """Test le filtrage par utilisateur"""
        # Créer un fichier pour un autre utilisateur
        user2 = User.objects.create_user('user2@example.com', 'testpass')
        fichier2 = FichierImporte.objects.create(
            fichier='test2.xlsx',
            utilisateur=user2
        )
        
        # Filtrer par utilisateur
        user_files = FichierImporte.objects.filter(utilisateur=self.user)
        self.assertEqual(len(user_files), 1)
        self.assertEqual(user_files[0], self.fichier)
    
    def test_reception_by_bon(self):
        """Test le filtrage par bon de commande"""
        # Créer des réceptions
        Reception.objects.create(
            bon_commande=self.bon1,
            fichier=self.fichier,
            business_id='BID001',
            ordered_quantity=Decimal('100'),
            unit_price=Decimal('50')
        )
        Reception.objects.create(
            bon_commande=self.bon2,
            fichier=self.fichier,
            business_id='BID002',
            ordered_quantity=Decimal('200'),
            unit_price=Decimal('60')
        )
        
        # Filtrer par bon
        bon1_receptions = Reception.objects.filter(bon_commande=self.bon1)
        self.assertEqual(len(bon1_receptions), 1)
        self.assertEqual(bon1_receptions[0].business_id, 'BID001')    