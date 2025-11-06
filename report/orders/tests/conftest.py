# tests/test_conftest.py
import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def user_active(db):
    """Fixture créant un utilisateur actif avec mot de passe utilisable."""
    user = User.objects.create_user(
        email='orders-active@example.com',
        password='Secret123!',
        first_name='Orders',
        last_name='User'
    )
    user.is_active = True
    user.save()
    return user


class TestConftestFixtures:
    """Tests pour les fixtures du fichier conftest.py"""

    def test_user_active_fixture(self, user_active):
        """Test que la fixture user_active crée un utilisateur valide"""
        assert user_active.email == 'orders-active@example.com'
        assert user_active.first_name == 'Orders'
        assert user_active.last_name == 'User'
        assert user_active.is_active is True
        assert user_active.check_password('Secret123!') is True

    def test_user_active_has_password(self, user_active):
        """Test que l'utilisateur a un mot de passe défini"""
        assert user_active.has_usable_password() is True

    def test_user_active_is_saved(self, user_active):
        """Test que l'utilisateur est bien sauvegardé en base"""
        assert user_active.id is not None
        assert User.objects.filter(email='orders-active@example.com').exists() is True

    def test_user_active_can_login(self, user_active, client):
        """Test que l'utilisateur peut se connecter"""
        login_success = client.login(
            email='orders-active@example.com',
            password='Secret123!'
        )
        assert login_success is True