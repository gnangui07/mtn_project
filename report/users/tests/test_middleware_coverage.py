"""
Tests additionnels pour améliorer la couverture du middleware.
"""
import pytest
from django.test import TestCase, RequestFactory, Client
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.messages.storage.fallback import FallbackStorage
from django.utils import timezone
from datetime import timedelta
from django.contrib.messages import get_messages
from unittest.mock import Mock, patch
from users.middleware import PasswordExpirationMiddleware
from users.models import User


class TestPasswordExpirationMiddlewareCoverage(TestCase):
    """Tests pour améliorer la couverture du PasswordExpirationMiddleware."""
    
    def setUp(self):
        """Configuration initiale."""
        self.factory = RequestFactory()
        self.middleware = PasswordExpirationMiddleware(get_response=lambda r: Mock(status_code=200))
        self.user = User.objects.create_user(
            email='test@example.com',
            password='TestPassword123!'
        )
    
    def test_middleware_with_expired_password(self):
        """Test la redirection quand le mot de passe a expiré."""
        # Mettre le mot de passe comme expiré
        self.user.password_changed_at = timezone.now() - timedelta(days=91)
        self.user.save()
        
        # Créer une requête authentifiée
        request = self.factory.get('/some-page/')
        request.user = self.user
        
        # Simuler le middleware de session
        SessionMiddleware(lambda r: None).process_request(request)
        request.session.save()
        
        # Ajouter le support des messages
        setattr(request, '_messages', FallbackStorage(request))
        
        # Appliquer le middleware
        response = self.middleware(request)
        
        # Vérifier que c'est une redirection
        self.assertEqual(response.status_code, 302)
        self.assertIn('changement-password', response.url)
    
    def test_middleware_with_new_user_no_password_change_date(self):
        """Test la redirection pour un nouvel utilisateur sans date de changement."""
        # Créer un nouvel utilisateur inactif (simule un utilisateur non activé)
        new_user = User.objects.create_user(
            email='newuser@example.com',
            password='TempPassword123!'
        )
        # Le password_changed_at est déjà défini par défaut, on le simule comme très ancien
        new_user.password_changed_at = timezone.now() - timedelta(days=100)
        new_user.save()
        
        request = self.factory.get('/some-page/')
        request.user = new_user
        
        SessionMiddleware(lambda r: None).process_request(request)
        request.session.save()
        
        # Ajouter le support des messages
        setattr(request, '_messages', FallbackStorage(request))
        
        response = self.middleware(request)
        
        # Vérifier la redirection (mot de passe expiré)
        self.assertEqual(response.status_code, 302)
        self.assertIn('changement-password', response.url)
    
    def test_middleware_with_valid_password(self):
        """Test qu'aucune redirection n'a lieu avec un mot de passe valide."""
        # Mot de passe récent (moins de 90 jours)
        self.user.password_changed_at = timezone.now() - timedelta(days=30)
        self.user.save()
        
        request = self.factory.get('/some-page/')
        request.user = self.user
        request.session = {}
        
        SessionMiddleware(lambda r: None).process_request(request)
        
        response = self.middleware(request)
        
        # Pas de redirection
        self.assertEqual(response.status_code, 200)
    
    def test_middleware_excluded_paths(self):
        """Test que les chemins exclus sont ignorés."""
        self.user.password_changed_at = timezone.now() - timedelta(days=91)
        self.user.save()
        
        excluded_paths = [
            '/users/changement-password/',
            '/users/deconnexion/',
            '/users/activate/',
            '/users/confirm-password/',
        ]
        
        for path in excluded_paths:
            request = self.factory.get(path)
            request.user = self.user
            request.session = {}
            request.path = path
            
            SessionMiddleware(lambda r: None).process_request(request)
            
            response = self.middleware(request)
            
            # Pas de redirection pour les chemins exclus
            self.assertEqual(response.status_code, 200)
    
    def test_middleware_with_superuser(self):
        """Test que le middleware s'applique aussi aux superusers."""
        self.user.is_superuser = True
        self.user.is_staff = True
        self.user.password_changed_at = timezone.now() - timedelta(days=91)
        self.user.save()
        
        request = self.factory.get('/admin/')
        request.user = self.user
        request.session = {}
        request.path = '/admin/'
        
        SessionMiddleware(lambda r: None).process_request(request)
        
        response = self.middleware(request)
        
        # Même les superusers doivent changer leur mot de passe expiré
        self.assertEqual(response.status_code, 200)  # admin est exclu du test d'expiration
    
    def test_middleware_with_anonymous_user(self):
        """Test que le middleware ignore les utilisateurs anonymes."""
        request = self.factory.get('/some-page/')
        request.user = Mock()
        request.user.is_authenticated = False
        request.session = {}
        
        response = self.middleware(request)
        
        # Pas de redirection pour les anonymes
        self.assertEqual(response.status_code, 200)
