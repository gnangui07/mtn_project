"""
Tests pour les formulaires de l'application users.
"""
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from users.forms import ChangePasswordForm

User = get_user_model()


class TestChangePasswordForm(TestCase):
    """Test le formulaire de changement de mot de passe."""
    
    def setUp(self):
        """Créer un utilisateur pour les tests."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='OldPassword123!'
        )
        # Mettre le mot de passe comme changé il y a 2 jours pour éviter la restriction d'âge
        from datetime import timedelta
        self.user.password_changed_at = timezone.now() - timedelta(days=2)
        self.user.save()
    
    def test_form_valid_with_correct_data(self):
        """Test que le formulaire est valide avec les bonnes données."""
        form_data = {
            'old_password': 'OldPassword123!',
            'new_password1': 'NewPassword123!',
            'new_password2': 'NewPassword123!'
        }
        form = ChangePasswordForm(self.user, data=form_data)
        self.assertTrue(form.is_valid())
    
    def test_form_invalid_wrong_old_password(self):
        """Test que le formulaire est invalide avec un mauvais ancien mot de passe."""
        form_data = {
            'old_password': 'WrongPassword123!',
            'new_password1': 'NewPassword123!',
            'new_password2': 'NewPassword123!'
        }
        form = ChangePasswordForm(self.user, data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('old_password', form.errors)
    
    def test_form_invalid_passwords_dont_match(self):
        """Test que le formulaire est invalide si les nouveaux mots de passe ne correspondent pas."""
        form_data = {
            'old_password': 'OldPassword123!',
            'new_password1': 'NewPassword123!',
            'new_password2': 'DifferentPassword123!'
        }
        form = ChangePasswordForm(self.user, data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('new_password2', form.errors)
    
    def test_form_invalid_too_short(self):
        """Test que le formulaire est invalide avec un mot de passe trop court."""
        form_data = {
            'old_password': 'OldPassword123!',
            'new_password1': 'Short1!',
            'new_password2': 'Short1!'
        }
        form = ChangePasswordForm(self.user, data=form_data)
        self.assertFalse(form.is_valid())
        # L'erreur peut être sur new_password1 ou new_password2 selon les validateurs
    
    def test_form_invalid_no_complexity(self):
        """Test que le formulaire est invalide sans complexité requise."""
        form_data = {
            'old_password': 'OldPassword123!',
            'new_password1': 'simplepassword',
            'new_password2': 'simplepassword'
        }
        form = ChangePasswordForm(self.user, data=form_data)
        self.assertFalse(form.is_valid())
    
    def test_form_fields_attributes(self):
        """Test que les champs ont les bons attributs."""
        form = ChangePasswordForm(self.user)
        
        # Vérifier les classes CSS
        self.assertEqual(
            form.fields['old_password'].widget.attrs['class'],
            'form-control form-control-lg'
        )
        self.assertEqual(
            form.fields['new_password1'].widget.attrs['class'],
            'form-control form-control-lg'
        )
        self.assertEqual(
            form.fields['new_password2'].widget.attrs['class'],
            'form-control form-control-lg'
        )
        
        # Vérifier les IDs
        self.assertEqual(
            form.fields['old_password'].widget.attrs['id'],
            'id_old_password'
        )
        self.assertEqual(
            form.fields['new_password1'].widget.attrs['id'],
            'id_new_password1'
        )
        self.assertEqual(
            form.fields['new_password2'].widget.attrs['id'],
            'id_new_password2'
        )
        
        # Vérifier les placeholders
        self.assertEqual(
            form.fields['old_password'].widget.attrs['placeholder'],
            'Entrez votre ancien mot de passe'
        )
        self.assertEqual(
            form.fields['new_password1'].widget.attrs['placeholder'],
            'Entrez le nouveau mot de passe'
        )
        self.assertEqual(
            form.fields['new_password2'].widget.attrs['placeholder'],
            'Confirmez le nouveau mot de passe'
        )
