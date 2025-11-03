"""
Tests additionnels des vues pour augmenter la couverture:
- Méthodes non autorisées (405) sur prefs voix.
- JSON invalide pour set_voice_prefs.
- Branches d'activation/confirmation: token expiré, déjà actif, erreurs de formulaire.
- Déconnexion en GET (redirige).
"""
import json
import pytest
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from users.models import User, UserVoicePreference


@pytest.mark.django_db
def test_get_voice_prefs_post_method_not_allowed(client, user_active):
    client.login(username=user_active.email, password='Secret123!')
    resp = client.post(reverse('users:get_voice_prefs'))
    assert resp.status_code == 405


@pytest.mark.django_db
def test_set_voice_prefs_get_method_not_allowed(client, user_active):
    client.login(username=user_active.email, password='Secret123!')
    resp = client.get(reverse('users:set_voice_prefs'))
    assert resp.status_code == 405


@pytest.mark.django_db
def test_set_voice_prefs_invalid_json_returns_400(client, user_active):
    client.login(username=user_active.email, password='Secret123!')
    # JSON invalide (chaîne tronquée)
    resp = client.post(
        reverse('users:set_voice_prefs'),
        data='{"enabled": tru',
        content_type='application/json'
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_activate_account_with_expired_token_redirects_login(client):
    u = User.objects.create(email='exp@example.com', is_active=False)
    u.generate_temporary_password()
    token = u.generate_activation_token()
    # Expirer le token
    u.token_created_at = timezone.now() - timedelta(days=3)
    u.save()
    resp = client.get(reverse('users:activate', kwargs={'token': token}))
    assert resp.status_code in (302, 303)
    assert reverse('users:login') in resp.headers.get('Location', '')


@pytest.mark.django_db
def test_activate_account_already_active_redirects_login(client):
    u = User.objects.create(email='act@example.com', is_active=True)
    token = u.generate_activation_token()
    u.save()
    resp = client.get(reverse('users:activate', kwargs={'token': token}))
    assert resp.status_code in (302, 303)
    assert reverse('users:login') in resp.headers.get('Location', '')


@pytest.mark.django_db
def test_confirm_password_with_expired_token_redirects_login(client):
    u = User.objects.create(email='exp2@example.com', is_active=False)
    token = u.generate_activation_token()
    u.token_created_at = timezone.now() - timedelta(days=3)
    u.save()
    resp = client.get(reverse('users:confirm_password', kwargs={'token': token}))
    assert resp.status_code in (302, 303)
    assert reverse('users:login') in resp.headers.get('Location', '')


@pytest.mark.django_db
def test_confirm_password_post_missing_fields_shows_errors(client):
    u = User.objects.create(email='miss@example.com', is_active=False)
    token = u.generate_activation_token()
    u.save()
    resp = client.post(reverse('users:confirm_password', kwargs={'token': token}), {})
    # Reste sur la page avec un message
    assert resp.status_code == 200


@pytest.mark.django_db
def test_confirm_password_post_mismatch_shows_error(client):
    u = User.objects.create(email='mm@example.com', is_active=False)
    token = u.generate_activation_token()
    u.save()
    resp = client.post(
        reverse('users:confirm_password', kwargs={'token': token}),
        {'new_password': 'StrongPass1!', 'confirm_password': 'WrongPass2!'}
    )
    assert resp.status_code == 200


@pytest.mark.django_db
def test_confirm_password_post_too_short_shows_error(client):
    u = User.objects.create(email='short@example.com', is_active=False)
    token = u.generate_activation_token()
    u.save()
    resp = client.post(
        reverse('users:confirm_password', kwargs={'token': token}),
        {'new_password': 'short', 'confirm_password': 'short'}
    )
    assert resp.status_code == 200


@pytest.mark.django_db
def test_deconnexion_get_redirects(client, user_active):
    client.login(username=user_active.email, password='Secret123!')
    resp = client.get(reverse('users:deconnexion'))
    assert resp.status_code in (302, 303)
