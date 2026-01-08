"""
Test Admin – envoi d'email d'activation à la création d'un utilisateur (mocké).
Explication simple:
- On simule l'appel admin.save_model lors de la création d'un user.
- On vérifie que send_mail est bien appelé et que le token est généré.
"""
import pytest
from unittest.mock import patch
from django.contrib import admin
from django.test import RequestFactory
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test.utils import override_settings

from users.models import User
from users.admin import UserAdmin


@pytest.mark.django_db
@override_settings(DEFAULT_FROM_EMAIL='noreply@example.com', SITE_URL='http://testserver', SITE_NAME='TestSite')
def test_admin_save_model_sends_activation_email():
    # Préparer une instance d'admin et une requête factice
    site = admin.sites.AdminSite()
    user_admin = UserAdmin(User, site)
    rf = RequestFactory()
    request = rf.post('/admin/users/user/add/')
    # Attacher une session et un système de messages au request pour supporter message_user
    # Session
    SessionMiddleware(lambda req: None).process_request(request)
    request.session.save()
    # Messages (utilise un storage fallback basé sur la session)
    setattr(request, '_messages', FallbackStorage(request))

    # Nouvel utilisateur (change=False)
    obj = User(email='admin-new@example.com', first_name='Admin', last_name='Created', is_active=False)

    with patch('users.admin.CELERY_AVAILABLE', False), \
         patch('users.admin.UserAdmin.send_activation_email') as mocked_send:
        user_admin.save_model(request, obj, form=None, change=False)

        # L'utilisateur doit être sauvegardé avec un token et un mot de passe temporaire générés
        obj.refresh_from_db()
        assert obj.activation_token  # non vide
        assert obj.temporary_password  # hash stocké (non vide)
        # send_activation_email doit être appelé une fois
        assert mocked_send.call_count == 1

        
