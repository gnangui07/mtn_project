# tests/test_urls.py
from django.test import TestCase
from django.urls import reverse, resolve
from orders import views, views_export, api, reception_api, msrn_api, penalty_api


class TestURLs(TestCase):
    def test_accueil_url(self):
        """Test l'URL de la page d'accueil"""
        url = reverse('orders:accueil')
        self.assertEqual(url, '/orders/')
        self.assertEqual(resolve(url).func, views.accueil)

    def test_details_bon_url(self):
        """Test l'URL des détails d'un bon"""
        url = reverse('orders:details_bon', args=[1])
        self.assertEqual(url, '/orders/bons/1/')
        self.assertEqual(resolve(url).func, views.details_bon)

    def test_import_fichier_url(self):
        """Test l'URL d'import de fichier"""
        url = reverse('orders:import_fichier')
        self.assertEqual(url, '/orders/import/')
        self.assertEqual(resolve(url).func, views.import_fichier)

    def test_export_excel_url(self):
        """Test l'URL d'export Excel"""
        url = reverse('orders:export_bon_excel', args=[1])
        self.assertEqual(url, '/orders/export-excel/1/')
        self.assertEqual(resolve(url).func, views_export.export_bon_excel)

    def test_update_quantity_delivered_url(self):
        """Test l'URL de mise à jour des quantités"""
        url = reverse('orders:update_quantity_delivered', args=[1])
        self.assertEqual(url, '/orders/api/update-quantity-delivered/1/')
        self.assertEqual(resolve(url).func, reception_api.update_quantity_delivered)

    def test_get_activity_logs_url(self):
        """Test l'URL des logs d'activité"""
        url = reverse('orders:get_activity_logs')
        self.assertEqual(url, '/orders/api/activity-logs/')
        self.assertEqual(resolve(url).func, api.get_activity_logs)

    def test_generate_msrn_report_url(self):
        """Test l'URL de génération de rapport MSRN"""
        url = reverse('orders:generate_msrn_report_api', args=[1])
        self.assertEqual(url, '/orders/api/generate-msrn/1/')
        self.assertEqual(resolve(url).func, msrn_api.generate_msrn_report_api)

    def test_generate_penalty_report_url(self):
        """Test l'URL de génération de rapport de pénalité"""
        url = reverse('orders:generate_penalty_report_api', args=[1])
        self.assertEqual(url, '/orders/api/generate-penalty/1/')
        self.assertEqual(resolve(url).func, penalty_api.generate_penalty_report_api)

    def test_vendor_evaluation_url(self):
        """Test l'URL d'évaluation des fournisseurs"""
        url = reverse('orders:vendor_evaluation', args=[1])
        self.assertEqual(url, '/orders/vendor-evaluation/1/')
        self.assertEqual(resolve(url).func, views.vendor_evaluation)

    def test_timeline_delays_url(self):
        """Test l'URL des délais de timeline"""
        url = reverse('orders:timeline_delays', args=[1])
        self.assertEqual(url, '/orders/timeline-delays/1/')
        self.assertEqual(resolve(url).func, views.timeline_delays)