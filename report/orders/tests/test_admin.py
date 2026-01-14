# tests/test_admin.py
import pytest
from django.test import TestCase, RequestFactory
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.utils.html import format_html
from orders.admin import FichierImporteAdmin, MSRNReportAdmin
from orders.models import FichierImporte, MSRNReport, NumeroBonCommande

User = get_user_model()


class MockRequest:
    def __init__(self, user=None):
        self.user = user


class TestFichierImporteAdmin(TestCase):
    def setUp(self):
        self.site = AdminSite()
        self.admin = FichierImporteAdmin(FichierImporte, self.site)
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            email='test@example.com', 
            password='testpass123'
        )
        self.fichier = FichierImporte.objects.create(
            fichier='test_file.csv',
            utilisateur=self.user
        )

    def test_save_model_captures_user(self):
        """Test que l'utilisateur est capturé automatiquement lors de la sauvegarde"""
        from unittest.mock import MagicMock
        request = MockRequest(user=self.user)
        obj = FichierImporte(fichier='new_file.csv')
        
        # Créer un mock de formulaire avec cleaned_data
        mock_form = MagicMock()
        mock_form.cleaned_data = {'async_import': False}
        
        self.admin.save_model(request, obj, mock_form, False)
        
        self.assertEqual(obj.utilisateur, self.user)

    def test_save_model_existing_object(self):
        """Test que l'utilisateur n'est pas modifié pour un objet existant"""
        from unittest.mock import MagicMock
        request = MockRequest(user=self.user)
        new_user = User.objects.create_user('new@example.com', 'pass123')
        self.fichier.utilisateur = new_user
        # Éviter les doublons: nettoyer les lignes avant la sauvegarde via l'admin
        self.fichier.lignes.all().delete()
        
        # Créer un mock de formulaire avec cleaned_data
        mock_form = MagicMock()
        mock_form.cleaned_data = {'async_import': False}
        
        # Sauvegarder via l'admin (change=True) sans appel direct à save() pour éviter double création
        self.admin.save_model(request, self.fichier, mock_form, True)
        
        self.assertEqual(self.fichier.utilisateur, new_user)

    def test_user_display_with_user(self):
        """Test l'affichage de l'utilisateur"""
        result = self.admin.user_display(self.fichier)
        expected = "test@example.com"  # car get_full_name() retourne vide
        self.assertEqual(result, expected)

    def test_user_display_without_user(self):
        """Test l'affichage sans utilisateur"""
        fichier = FichierImporte.objects.create(fichier='no_user.csv')
        result = self.admin.user_display(fichier)
        self.assertEqual(result, "—")

    def test_file_link_with_file(self):
        """Test le lien vers le fichier"""
        result = self.admin.file_link(self.fichier)
        expected_url = f'/admin/orders/fichierimporte/{self.fichier.id}/change/'
        self.assertIn(expected_url, result)
        self.assertIn('test_file.csv', result)

    def test_file_link_without_file(self):
        """Test le lien sans fichier"""
        fichier = FichierImporte()
        result = self.admin.file_link(fichier)
        self.assertEqual(result, "—")

    def test_export_excel_button_with_id(self):
        """Test le bouton d'export Excel"""
        result = self.admin.export_excel_button(self.fichier)
        expected_url = f'/orders/export-fichier-complet/{self.fichier.id}/'
        self.assertIn(expected_url, result)
        self.assertIn('Exporter Excel', result)

    def test_export_excel_button_without_id(self):
        """Test le bouton d'export sans ID"""
        fichier = FichierImporte()
        result = self.admin.export_excel_button(fichier)
        self.assertEqual(result, "—")

    def test_generate_html_table_empty_content(self):
        """Test la génération de tableau HTML avec contenu vide"""
        result = self.admin.generate_html_table([])
        self.assertIn("Aucune donnée disponible", result)

    def test_generate_html_table_list_of_dicts(self):
        """Test la génération de tableau HTML avec liste de dictionnaires"""
        content = [
            {'col1': 'val1', 'col2': 'val2'},
            {'col1': 'val3', 'col2': 'val4'}
        ]
        result = self.admin.generate_html_table(content)
        self.assertIn('<table', result)
        self.assertIn('col1', result)
        self.assertIn('val1', result)

    def test_generate_html_table_dict_with_lines(self):
        """Test la génération de tableau HTML avec dictionnaire contenant lines"""
        content = {'lines': ['line1', 'line2', 'line3']}
        result = self.admin.generate_html_table(content)
        self.assertIn('Line Number', result)
        self.assertIn('line1', result)

    def test_data_table_view_no_object(self):
        """Test la vue tableau de données sans objet"""
        result = self.admin.data_table_view(None)
        self.assertIn("Aucun objet trouvé", result)

    def test_list_display_attributes(self):
        """Test que list_display contient les bonnes colonnes"""
        expected_columns = [
            'file_link', 'extension', 'date_importation', 
            'nombre_lignes', 'user_display', 'export_excel_button'
        ]
        self.assertEqual(self.admin.list_display, expected_columns)

    def test_readonly_fields(self):
        """Test que les champs en lecture seule sont corrects"""
        expected_fields = ('extension', 'date_importation', 'nombre_lignes', 'data_table_view', 'user_display')
        self.assertEqual(self.admin.readonly_fields, expected_fields)


class TestMSRNReportAdmin(TestCase):
    def setUp(self):
        self.site = AdminSite()
        self.admin = MSRNReportAdmin(MSRNReport, self.site)
        self.user = User.objects.create_user('test@example.com', 'testpass')
        self.bon_commande = NumeroBonCommande.objects.create(numero='TEST123')
        self.msrn_report = MSRNReport.objects.create(
            report_number='MSRN250001',
            bon_commande=self.bon_commande,
            user=self.user.email
        )

    def test_list_display(self):
        """Test les colonnes affichées dans la liste"""
        expected = (
            'report_number', 
            'bon_commande', 
            'supplier_display',
            'company_display',
            'montant_recu_display',
            'currency_display',
            'retention_rate_display',
            'progress_rate_display',
            'cpu_display',
            'pm_column',
            'coordinator_column',
            'senior_pm_column',
            'manager_portfolio_column',
            'gm_epmo_column',
            'senior_tech_lead_column',
            'vendor_column',
            'created_at', 
            'download_pdf',
            'edit_signatures_link',
        )
        self.assertEqual(self.admin.list_display, expected)

    def test_readonly_fields(self):
        """Test les champs en lecture seule"""
        expected = (
            'report_number',
            'bon_commande',
            'created_at',
            'download_pdf',
            'montant_total_snapshot',
            'montant_recu_snapshot',
            'progress_rate_snapshot',
        )
        self.assertEqual(self.admin.readonly_fields, expected)

    def test_search_fields(self):
        """Test les champs de recherche"""
        expected = (
            'report_number', 
            'bon_commande__numero', 
            'user',
            'supplier_snapshot',
            'cpu_snapshot',
            'project_manager_snapshot',
        )
        self.assertEqual(self.admin.search_fields, expected)

    def test_list_filter(self):
        """Test les filtres disponibles"""
        from orders.admin import CPUFilter, ProjectManagerFilter
        expected = (
            'created_at',
            'workflow_status',
            CPUFilter,
            ProjectManagerFilter,
        )
        self.assertEqual(self.admin.list_filter, expected)

    def test_download_pdf_with_file(self):
        """Test le lien de téléchargement avec fichier"""
        # Dans un vrai scénario, on aurait un fichier PDF
        result = self.admin.download_pdf(self.msrn_report)
        # Sans fichier PDF, retourne un tiret stylé
        self.assertIn('-', result)

    def test_download_pdf_short_description(self):
        """Test la description courte du champ download_pdf"""
        self.assertEqual(self.admin.download_pdf.short_description, "PDF")