"""
Fixtures pytest pour l'app users (simples et réutilisables).
- user_active: utilisateur actif avec mot de passe valide.
- user_inactive_with_token: utilisateur inactif avec token + mot de passe temporaire.
- client_logged: client déjà connecté en tant que user_active.
"""
import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def user_active():
    user = User.objects.create(email='active@example.com', first_name='Active', last_name='User', is_active=True)
    user.set_password('Secret123!')
    user.save()
    return user


@pytest.fixture
def user_inactive_with_token():
    user = User.objects.create(email='inactive@example.com', first_name='In', last_name='Active', is_active=False)
    # Prépare mot de passe temporaire et token
    user.generate_temporary_password()
    token = user.generate_activation_token()
    user.save()  # Important: persister token/mot de passe temporaire
    return user, token


@pytest.fixture
def client_logged(client, user_active):
    client.login(username=user_active.email, password='Secret123!')
    return client
