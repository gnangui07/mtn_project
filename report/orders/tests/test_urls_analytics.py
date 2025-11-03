"""
Tests pour urls_analytics:
- Le nom 'orders:get_analytics_data' se résout.
"""
import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_get_analytics_data_url_resolves():
    url = reverse('orders:get_analytics_data')
    assert isinstance(url, str) and len(url) > 0
