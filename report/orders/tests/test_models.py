# tests/test_models.py
import pytest
from decimal import Decimal
from unittest.mock import patch
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

        self.user = User.objects.create_user('test@example.com', 'testpass')
        self.fichier = FichierImporte.objects.create(
            fichier='test.csv',
            utilisateur=self.user
        )
        self.bon_commande = NumeroBonCommande.objects.create(numero='TEST123')
        self.bon_commande.fichiers.add(self.fichier)
        
        # Nettoyer les lignes auto-créées
        self.fichier.lignes.all().delete()
        
        # Créer une ligne de fichier
        self.ligne = LigneFichier.objects.create(
            fichier=self.fichier,
            numero_ligne=1,
            business_id='TEST-L1',
            contenu={'Order': 'TEST123', 'Line': '1', 'Item': '1', 'Schedule': '1'}
        )

    def test_creation(self):
        """Test la création d'une ligne de fichier"""
        self.assertEqual(self.ligne.numero_ligne, 1)
        self.assertEqual(self.ligne.contenu['Order'], 'TEST123')
        self.assertIsNotNone(self.ligne.date_creation)

    def test_generate_business_id(self):
        """Test la génération du business_id"""
        business_id = self.ligne.generate_business_id()
        expected = "ORDER:TEST123|LINE:1|ITEM:1|SCHEDULE:1"
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
        self.assertEqual(self.fichier.nombre_lignes, 0)

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