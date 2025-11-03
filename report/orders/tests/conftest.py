"""
Fixtures simples pour l'app orders.
- user_active: utilisateur actif pouvant se connecter.
"""
import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def user_active(db):
    user = User.objects.create(email='orders-active@example.com', first_name='Orders', last_name='User', is_active=True)
    user.set_password('Secret123!')
    user.save()
    return user
