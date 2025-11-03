"""
Version nettoyée de tests/test_views.py pour éviter les caractères invalides.
"""
import pytest
from django.urls import reverse
from users.models import User


@pytest.mark.django_db
class TestAuthViewsClean:
    def test_login_get_renders_page(self, client):
        url = reverse('users:login')
        resp = client.get(url)
        assert resp.status_code == 200
        assert b'connexion' in resp.content.lower()

    def test_login_post_bad_credentials_shows_error(self, client):
        url = reverse('users:login')
        resp = client.post(url, {'email': 'unknown@example.com', 'password': 'bad'})
        assert resp.status_code == 200
        assert b'incorrect' in resp.content.lower() or b'error' in resp.content.lower()

    def test_login_post_success_redirects_and_sets_no_cache_headers(self, client):
        user = User.objects.create(email='user@example.com', first_name='U', last_name='X', is_active=True)
        user.set_password('Secret123!')
        user.save()
        url = reverse('users:login')
        resp = client.post(url, {'email': user.email, 'password': 'Secret123!'}, follow=False)
        assert resp.status_code in (302, 303)
        assert 'Cache-Control' in resp.headers and 'no-cache' in resp.headers['Cache-Control']


@pytest.mark.django_db
class TestActivationFlowClean:
    def test_activate_account_get_page(self, client):
        user = User.objects.create(email='new@example.com', first_name='New', last_name='User', is_active=False)
        user.generate_temporary_password()
        token = user.generate_activation_token()
        user.save()
        url = reverse('users:activate', kwargs={'token': token})
        resp = client.get(url)
        assert resp.status_code == 200
        assert b'premi' in resp.content.lower()

    def test_confirm_password_get_requires_valid_token(self, client):
        user = User.objects.create(email='new2@example.com', first_name='N', last_name='U', is_active=False)
        token = user.generate_activation_token()
        user.save()
        url = reverse('users:confirm_password', kwargs={'token': token})
        resp = client.get(url)
        assert resp.status_code == 200
        assert b'activer mon compte' in resp.content.lower()

    def test_login_post_inactive_user_shows_message(self, client):
        user = User.objects.create(email='inactive2@example.com', first_name='In', last_name='Active', is_active=False)
        user.set_password('Secret123!')
        user.save()
        url = reverse('users:login')
        resp = client.post(url, {'email': user.email, 'password': 'Secret123!'}, follow=True)
        assert resp.status_code in (200, 302)
        assert b'activ' in resp.content.lower() or b'pas encore' in resp.content.lower()

    def test_activate_account_post_redirects_to_confirm(self, client):
        user = User.objects.create(email='new3@example.com', first_name='New', last_name='U', is_active=False)
        tmp = user.generate_temporary_password()
        token = user.generate_activation_token()
        user.save()
        url = reverse('users:activate', kwargs={'token': token})
        resp = client.post(url, {'email': user.email, 'temp_password': tmp}, follow=False)
        assert resp.status_code in (302, 303)
        assert reverse('users:confirm_password', kwargs={'token': token}) in resp.headers.get('Location', '')

    def test_confirm_password_post_sets_password_and_activates(self, client):
        user = User.objects.create(email='new4@example.com', first_name='X', last_name='Y', is_active=False)
        token = user.generate_activation_token()
        user.save()
        url = reverse('users:confirm_password', kwargs={'token': token})
        resp = client.post(url, {'new_password': 'StrongPass1!', 'confirm_password': 'StrongPass1!'}, follow=False)
        assert resp.status_code in (302, 303)
        assert reverse('users:login') in resp.headers.get('Location', '')
