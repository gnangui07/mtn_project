"""
Tests additionnels pour améliorer la couverture des validateurs.
"""
import pytest
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
from users.models import User
from users.validators import (
    ComplexityValidator,
    AdminPasswordValidator,
    PasswordHistoryValidator,
    PasswordAgeValidator
)


class TestValidatorsCoverage(TestCase):
    """Tests pour améliorer la couverture des validateurs."""
    
    def setUp(self):
        """Configuration initiale."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='TestPassword123!'
        )
        self.superuser = User.objects.create_user(
            email='admin@example.com',
            password='AdminPassword123!',
            is_superuser=True,
            is_staff=True
        )
    
    def test_complexity_validator_valid_password(self):
        """Test qu'un mot de passe complexe passe la validation."""
        validator = ComplexityValidator()
        try:
            validator.validate('ComplexPassword123!')
        except ValidationError:
            self.fail("ComplexityValidator a levé une erreur pour un mot de passe valide")
    
    def test_complexity_validator_no_uppercase(self):
        """Test l'erreur quand pas de majuscule."""
        validator = ComplexityValidator()
        with self.assertRaises(ValidationError) as cm:
            validator.validate('lowercase123!')
        self.assertIn('majuscule', str(cm.exception))
    
    def test_complexity_validator_no_lowercase(self):
        """Test l'erreur quand pas de minuscule."""
        validator = ComplexityValidator()
        with self.assertRaises(ValidationError) as cm:
            validator.validate('UPPERCASE123!')
        self.assertIn('minuscule', str(cm.exception))
    
    def test_complexity_validator_no_digit(self):
        """Test l'erreur quand pas de chiffre."""
        validator = ComplexityValidator()
        with self.assertRaises(ValidationError) as cm:
            validator.validate('NoDigits!')
        self.assertIn('chiffre', str(cm.exception))
    
    def test_complexity_validator_no_special(self):
        """Test l'erreur quand pas de caractère spécial."""
        validator = ComplexityValidator()
        with self.assertRaises(ValidationError) as cm:
            validator.validate('NoSpecialChar123')
        self.assertIn('spécial', str(cm.exception))
    
    def test_complexity_validator_help_text(self):
        """Test le texte d'aide du validateur de complexité."""
        validator = ComplexityValidator()
        help_text = validator.get_help_text()
        self.assertIn('majuscule', help_text)
        self.assertIn('minuscule', help_text)
        self.assertIn('chiffre', help_text)
        self.assertIn('spécial', help_text)
    
    def test_admin_password_validator_valid(self):
        """Test qu'un mot de passe admin valide passe."""
        validator = AdminPasswordValidator()
        try:
            validator.validate('ValidAdminPassword123!', self.superuser)
        except ValidationError:
            self.fail("AdminPasswordValidator a levé une erreur pour un mot de passe valide")
    
    def test_admin_password_validator_too_short(self):
        """Test l'erreur pour un mot de passe admin trop court."""
        validator = AdminPasswordValidator()
        with self.assertRaises(ValidationError) as cm:
            validator.validate('Short1!', self.superuser)
        self.assertIn('14', str(cm.exception))
    
    def test_admin_password_validator_normal_user(self):
        """Test que le validateur ne s'applique pas aux utilisateurs normaux."""
        validator = AdminPasswordValidator()
        try:
            validator.validate('Short1!', self.user)
        except ValidationError:
            self.fail("AdminPasswordValidator s'est appliqué à un utilisateur normal")
    
    def test_admin_password_validator_no_user(self):
        """Test que le validateur ne s'applique pas sans utilisateur."""
        validator = AdminPasswordValidator()
        try:
            validator.validate('AnyPassword')
        except ValidationError:
            self.fail("AdminPasswordValidator s'est appliqué sans utilisateur")
    
    def test_admin_password_validator_help_text(self):
        """Test le texte d'aide du validateur admin."""
        validator = AdminPasswordValidator()
        help_text = validator.get_help_text()
        self.assertIn('14', help_text)
        self.assertIn('administrateurs', help_text)
    
    def test_password_age_validator_valid(self):
        """Test qu'un mot de passe assez ancien passe."""
        validator = PasswordAgeValidator()
        self.user.password_changed_at = timezone.now() - timedelta(days=2)
        self.user.save()
        
        try:
            validator.validate('NewPassword123!', self.user)
        except ValidationError:
            self.fail("PasswordAgeValidator a refusé un changement après 2 jours")
    
    def test_password_age_validator_too_soon(self):
        """Test l'erreur quand le changement est trop tôt."""
        validator = PasswordAgeValidator()
        self.user.password_changed_at = timezone.now() - timedelta(hours=12)
        self.user.save()
        
        with self.assertRaises(ValidationError) as cm:
            validator.validate('NewPassword123!', self.user)
        self.assertIn('1 jour', str(cm.exception))
    
    def test_password_age_validator_first_time(self):
        """Test qu'un nouvel utilisateur peut changer son mot de passe."""
        validator = PasswordAgeValidator()
        # Créer un utilisateur mock sans password_changed_at
        from unittest.mock import Mock
        mock_user = Mock()
        mock_user.pk = 999
        mock_user.password_changed_at = None
        
        try:
            validator.validate('NewPassword123!', mock_user)
        except ValidationError:
            self.fail("PasswordAgeValidator a refusé le premier changement")
    
    def test_password_age_validator_no_user(self):
        """Test que le validateur ne s'applique pas sans utilisateur."""
        validator = PasswordAgeValidator()
        try:
            validator.validate('AnyPassword')
        except ValidationError:
            self.fail("PasswordAgeValidator s'est appliqué sans utilisateur")
    
    def test_password_age_validator_help_text(self):
        """Test le texte d'aide du validateur d'âge."""
        validator = PasswordAgeValidator()
        help_text = validator.get_help_text()
        self.assertIn('1 jour', help_text)
    
    def test_password_history_validator_first_password(self):
        """Test que le premier mot de passe est accepté."""
        validator = PasswordHistoryValidator()
        try:
            validator.validate('FirstPassword123!', self.user)
        except ValidationError:
            self.fail("PasswordHistoryValidator a refusé le premier mot de passe")
    
    def test_password_history_validator_reuse(self):
        """Test que la réutilisation est détectée via is_password_reused."""
        from users.models_history import PasswordHistory
        from unittest.mock import patch
        
        validator = PasswordHistoryValidator()
        
        # Mocker is_password_reused pour retourner True
        with patch.object(PasswordHistory, 'is_password_reused', return_value=True):
            with self.assertRaises(ValidationError) as cm:
                validator.validate('TestPassword123!', self.user)
            self.assertIn('24', str(cm.exception))
    
    def test_password_history_validator_help_text(self):
        """Test le texte d'aide du validateur d'historique."""
        validator = PasswordHistoryValidator()
        help_text = validator.get_help_text()
        self.assertIn('24', help_text)
