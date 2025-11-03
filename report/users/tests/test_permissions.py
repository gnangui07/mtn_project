"""
Tests permissions et en-têtes cache – explications simples:
- Les endpoints protégés redirigent vers la page de connexion si on n'est pas connecté.
- Les pages sensibles ont des en-têtes anti-cache.
"""
import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_protected_voice_prefs_redirects_to_login(client):
    # Sans connexion, accès interdit → redirection
    resp_get = client.get(reverse('users:get_voice_prefs'))
    resp_post = client.post(reverse('users:set_voice_prefs'), {'enabled': True})
    assert resp_get.status_code in (301, 302)
    assert resp_post.status_code in (301, 302)


@pytest.mark.django_db
def test_login_page_has_anti_cache_headers(client):
    # La page de login ne doit pas être gardée en cache par le navigateur
    resp = client.get(reverse('users:login'))
    assert resp.status_code == 200
    assert 'Cache-Control' in resp.headers
    assert 'no-cache' in resp.headers['Cache-Control']
    assert 'Pragma' in resp.headers and 'no-cache' in resp.headers['Pragma']


@pytest.mark.django_db
def test_deconnexion_adds_anti_cache_headers(client, user_active):
    # On se connecte puis on appelle la déconnexion en POST
    client.login(username=user_active.email, password='Secret123!')
    resp = client.post(reverse('users:deconnexion'))
    # Redirection vers /connexion/ avec en-têtes anti-cache
    assert resp.status_code in (302, 303)
    assert 'Cache-Control' in resp.headers and 'no-cache' in resp.headers['Cache-Control']
    assert 'Pragma' in resp.headers and 'no-cache' in resp.headers['Pragma']
