# tests/test_urls_analytics.py
from django.test import TestCase
from django.urls import reverse, resolve
from orders import analytics_api


class TestAnalyticsURLs(TestCase):
    def test_get_analytics_data_url(self):
        """Test l'URL des données analytiques"""
        url = reverse('orders:get_analytics_data')
        self.assertEqual(url, '/orders/api/analytics/')
        self.assertEqual(resolve(url).func, analytics_api.get_analytics_data)