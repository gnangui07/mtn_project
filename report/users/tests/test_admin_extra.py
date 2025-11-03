"""
Tests supplémentaires admin: activation_status + change=True + send_mail avec exception.
"""
import pytest
from unittest.mock import patch
from django.contrib import admin
from django.test import RequestFactory
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.messages.storage.fallback import FallbackStorage

from users.models import User
from users.admin import UserAdmin


@pytest.mark.django_db
def test_activation_status_variants():
    site = admin.sites.AdminSite()
    ua = UserAdmin(User, site)
    # Actif
    u1 = User.objects.create(email='a1@example.com', is_active=True)
    assert 'Activé' in ua.activation_status(u1)
    # En attente (token présent)
    u2 = User.objects.create(email='a2@example.com', is_active=False)
    u2.activation_token = 'tok'
    assert 'En attente' in ua.activation_status(u2)
    # Non activé (pas de token)
    u3 = User.objects.create(email='a3@example.com', is_active=False)
    assert 'Non activé' in ua.activation_status(u3)


@pytest.mark.django_db
def test_save_model_change_true_no_email_sent():
    site = admin.sites.AdminSite()
    ua = UserAdmin(User, site)
    rf = RequestFactory()
    request = rf.post('/admin/users/user/change/1/')
    SessionMiddleware(lambda req: None).process_request(request)
    request.session.save()
    setattr(request, '_messages', FallbackStorage(request))
    obj = User.objects.create(email='chg@example.com', is_active=False)
    with patch('users.admin.send_mail') as mocked:
        ua.save_model(request, obj, form=None, change=True)
        # En modification, on ne crée pas de token/mot de passe temporaire, pas d'email
        assert mocked.call_count == 0


@pytest.mark.django_db
def test_send_activation_email_handles_exception_gracefully():
    site = admin.sites.AdminSite()
    ua = UserAdmin(User, site)
    rf = RequestFactory()
    request = rf.post('/admin/users/user/add/')
    SessionMiddleware(lambda req: None).process_request(request)
    request.session.save()
    setattr(request, '_messages', FallbackStorage(request))

    obj = User(email='boom@example.com', first_name='B', last_name='OOM', is_active=False)
    tmp = obj.generate_temporary_password()
    obj.generate_activation_token()
    obj.save()

    with patch('users.admin.send_mail', side_effect=Exception('SMTP error')) as mocked:
        # Appel direct à la méthode pour simuler l'envoi qui échoue
        ua.send_activation_email(obj, tmp, request)
        assert mocked.call_count == 1
