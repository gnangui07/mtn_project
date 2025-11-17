"""
Tests modèles (User) – explications simples:
- On vérifie que le token d'activation est bien créé et qu'il expire.
- On vérifie que le mot de passe temporaire marche, puis échoue avec une mauvaise valeur.
- On vérifie que l'activation active le compte et nettoie les champs temporaires.
- On vérifie que la liste des services est bien nettoyée.
"""
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from users.models import User, UserVoicePreference


class UserModelTests(TestCase):
    def setUp(self):
        # Crée un utilisateur de test simple
        self.user = User.objects.create(email="tester@example.com", first_name="Test", last_name="User")

    def test_generate_activation_token_and_validity(self):
        # Quand on génère un token
        token = self.user.generate_activation_token()
        # Alors: il existe, a une date, et il est encore valide maintenant
        self.assertTrue(token)
        self.assertTrue(self.user.activation_token)
        self.assertIsNotNone(self.user.token_created_at)
        self.assertTrue(self.user.is_token_valid())
        # On simule l'expiration: on recule la date de création de 3 jours
        self.user.token_created_at = timezone.now() - timedelta(days=3)
        self.user.save(update_fields=["token_created_at"])
        self.assertFalse(self.user.is_token_valid())

    def test_generate_and_check_temporary_password(self):
        # Quand on génère un mot de passe temporaire
        tmp_clear = self.user.generate_temporary_password()
        # Alors: on reçoit une valeur en clair et le hash est stocké en base
        self.assertTrue(tmp_clear)
        self.assertTrue(self.user.temporary_password)
        # La vérification réussit avec la bonne valeur
        self.assertTrue(self.user.check_temporary_password(tmp_clear))
        # Et échoue avec une mauvaise valeur
        self.assertFalse(self.user.check_temporary_password("wrong-pass"))

    def test_activate_account(self):
        # Préparation: token + mot de passe temporaire sur un compte inactif
        tmp_clear = self.user.generate_temporary_password()
        self.user.generate_activation_token()
        self.user.is_active = False
        self.user.save()
        # Quand on active le compte
        self.user.activate_account()
        # Alors: le compte est actif et les champs temporaires sont remis à zéro
        self.assertTrue(self.user.is_active)
        # temporary_password/activation_token sont mis à None par le modèle
        self.assertFalse(bool(self.user.temporary_password))
        self.assertFalse(bool(self.user.activation_token))
        self.assertIsNone(self.user.token_created_at)

    def test_get_services_list(self):
        # La chaîne "NWG, ITS ,  FAC" doit devenir une liste propre ["NWG", "ITS", "FAC"]
        self.user.service = "NWG, ITS ,  FAC"
        self.user.save()
        self.assertEqual(self.user.get_services_list(), ["NWG", "ITS", "FAC"]) 


class UserVoicePreferenceTests(TestCase):
    def test_voice_preference_str(self):
        """Test de la représentation en chaîne de UserVoicePreference"""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass',
            first_name='Test',
            last_name='User'
        )
        # Test avec un nom de voix spécifié
        prefs = UserVoicePreference.objects.create(
            user=user,
            lang='fr-FR',
            voice_name='fr-FR-Standard-A',
            enabled=True
        )
        # Le modèle utilise self.user_id, donc on compare avec l'ID utilisateur
        self.assertEqual(str(prefs), f"VoicePrefs({user.id}, fr-FR, fr-FR-Standard-A)")
        
        # Test avec voice_name vide (doit utiliser 'auto')
        prefs.voice_name = ''
        prefs.save()
        self.assertEqual(str(prefs), f"VoicePrefs({user.id}, fr-FR, auto)")
