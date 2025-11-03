"""
Tests supplémentaires pour le modèle User et son manager.
Objectif: couvrir les cas non testés (création, fallbacks, validations).
"""
import pytest
from django.utils import timezone
from users.models import User


@pytest.mark.django_db
def test_create_user_requires_email():
    with pytest.raises(ValueError):
        User.objects.create_user(email="", password="x")


@pytest.mark.django_db
def test_create_user_normalizes_email():
    u = User.objects.create_user(email="  JoHN.DOE@Example.Com  ", password="x", first_name="John", last_name="Doe")
    # Django normalise le domaine en minuscule mais peut garder la casse locale.
    # On vérifie que les espaces ont été retirés et que le domaine est en minuscule.
    assert u.email == u.email.strip()
    assert u.email.split('@')[1] == 'example.com'


@pytest.mark.django_db
def test_create_superuser_enforces_flags():
    su = User.objects.create_superuser(email="admin@example.com", password="x")
    assert su.is_staff is True and su.is_superuser is True and su.is_active is True
    # Si on tente d'override invalide, ValueError
    with pytest.raises(ValueError):
        User.objects.create_superuser(email="bad@example.com", password="x", is_staff=False)
    with pytest.raises(ValueError):
        User.objects.create_superuser(email="bad2@example.com", password="x", is_superuser=False)


@pytest.mark.django_db
def test_name_fallbacks_and_str():
    u = User.objects.create(email="noname@example.com")
    # full name et short name doivent retomber sur l'email si vides
    assert u.get_full_name() == "noname@example.com"
    assert u.get_short_name() == "noname@example.com"
    assert str(u).endswith(f"({u.email})")


@pytest.mark.django_db
def test_check_temp_password_without_any_returns_false():
    u = User.objects.create(email="tmp@example.com")
    assert u.check_temporary_password("anything") is False


@pytest.mark.django_db
def test_is_token_valid_false_when_no_timestamp():
    u = User.objects.create(email="tok@example.com")
    u.activation_token = "abc"
    # Pas de token_created_at → invalide
    assert u.is_token_valid() is False
