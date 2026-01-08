"""
Tests simples pour valider la politique de mots de passe.
"""
from django.test import TestCase
from django.contrib.auth.hashers import check_password
from users.models import User
from users.validators import ComplexityValidator, AdminPasswordValidator
from django.core.exceptions import ValidationError


class TestPasswordBasics(TestCase):
    """Tests basiques de la politique de mots de passe."""
    
    def test_temporary_password_generation(self):
        """Test la génération de mot de passe temporaire."""
        user = User(email="test@test.com")
        temp_password = user.generate_temporary_password()
        
        # Vérifier la longueur (14 caractères)
        self.assertEqual(len(temp_password), 14)
        
        # Vérifier la complexité
        self.assertTrue(any(c.isupper() for c in temp_password))
        self.assertTrue(any(c.islower() for c in temp_password))
        self.assertTrue(any(c.isdigit() for c in temp_password))
        self.assertTrue(any(c in "@!-_" for c in temp_password))
        
        # Vérifier que le hash est stocké
        self.assertIsNotNone(user.temporary_password)
        self.assertNotEqual(user.temporary_password, temp_password)
    
    def test_complexity_validator(self):
        """Test le validateur de complexité."""
        validator = ComplexityValidator()
        
        # Mot de passe valide
        try:
            validator.validate("MonMotDePasse1!")
        except ValidationError:
            self.fail("Le validateur a levé une exception pour un mot de passe valide")
        
        # Mot de passe sans majuscule
        with self.assertRaises(ValidationError):
            validator.validate("monmotdepasse1!")
        
        # Mot de passe sans minuscule
        with self.assertRaises(ValidationError):
            validator.validate("MONMOTDEPASSE1!")
        
        # Mot de passe sans chiffre
        with self.assertRaises(ValidationError):
            validator.validate("MonMotDePasse!")
        
        # Mot de passe sans spécial
        with self.assertRaises(ValidationError):
            validator.validate("MonMotDePasse1")
    
    def test_admin_password_length(self):
        """Test l'exigence de longueur pour les admins."""
        validator = AdminPasswordValidator()
        
        # Utilisateur normal - 12 caractères OK
        normal_user = User(email="normal@test.com", is_superuser=False)
        try:
            validator.validate("MotDePasse1!", user=normal_user)
        except ValidationError:
            self.fail("Le validateur a levé une exception pour un utilisateur normal")
        
        # Admin - 12 caractères KO
        admin_user = User(email="admin@test.com", is_superuser=True)
        with self.assertRaises(ValidationError):
            validator.validate("MotDePasse1!", user=admin_user)
        
        # Admin - 14 caractères OK
        try:
            validator.validate("MotDePasse123!", user=admin_user)
        except ValidationError:
            self.fail("Le validateur a levé une exception pour un admin avec 14 caractères")
    
    def test_user_creation_flow(self):
        """Test le flux de création d'utilisateur."""
        # Créer un utilisateur
        user = User.objects.create_user(
            email="newuser@test.com",
            password="TestPassword123!"
        )
        
        # Vérifier que l'utilisateur peut se connecter
        self.assertTrue(user.check_password("TestPassword123!"))
        
        # Vérifier qu'il a une date de changement
        self.assertIsNotNone(user.password_changed_at)
    
    def test_password_change(self):
        """Test le changement de mot de passe."""
        user = User.objects.create_user(
            email="test@test.com",
            password="OldPassword123!"
        )
        
        # Changer le mot de passe
        user.set_password("NewPassword123!")
        user.save()
        
        # Vérifier le changement
        self.assertTrue(user.check_password("NewPassword123!"))
        self.assertFalse(user.check_password("OldPassword123!"))
