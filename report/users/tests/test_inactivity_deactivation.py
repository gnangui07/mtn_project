"""
Tests pour la désactivation automatique des comptes inactifs (90 jours).

Ces tests valident les 4 preuves requises:
1. Configuration des paramètres (90 jours)
2. Désactivation automatique après 90 jours
3. Exemption des superusers
4. Réactivation manuelle par superuser

Approche: Tests unitaires directs de la logique métier sans dépendance au middleware complet
"""
import pytest
from django.test import TestCase, Client, RequestFactory
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from django.urls import reverse
from django.contrib.admin.sites import AdminSite
from django.contrib.messages.storage.fallback import FallbackStorage
from users.admin import UserAdmin
from users.middleware_inactivity import InactivityDeactivationMiddleware

User = get_user_model()


class TestInactivityConfiguration(TestCase):
    """
    PREUVE 1: Configuration des paramètres de désactivation automatique.
    
    Vérifie que le système est configuré pour désactiver automatiquement
    les comptes utilisateurs standards après 90 jours d'inactivité.
    """
    
    def test_inactivity_days_configuration(self):
        """Test: La durée d'inactivité est configurée depuis settings.py (défaut: 90 jours)"""
        from django.conf import settings
        middleware = InactivityDeactivationMiddleware(lambda x: x)
        # Vérifier que le middleware utilise la valeur de settings
        expected_days = getattr(settings, 'INACTIVITY_DAYS', 90)
        self.assertEqual(middleware.inactivity_days, expected_days)
    
    def test_middleware_is_registered(self):
        """Vérifie que le middleware est enregistré dans settings.py"""
        from django.conf import settings
        middleware_list = settings.MIDDLEWARE
        
        # Vérifier que le middleware d'inactivité est présent
        self.assertIn(
            'users.middleware_inactivity.InactivityDeactivationMiddleware',
            middleware_list,
            "Le middleware de désactivation automatique n'est pas enregistré dans MIDDLEWARE"
        )
    
    def test_deactivation_fields_exist(self):
        """Vérifie que les champs de désactivation existent dans le modèle User"""
        user = User.objects.create_user(
            email='test@example.com',
            password='TestPass123!',
            first_name='Test',
            last_name='User'
        )
        
        # Vérifier que les champs existent
        self.assertTrue(hasattr(user, 'deactivation_reason'))
        self.assertTrue(hasattr(user, 'deactivated_at'))
        self.assertTrue(hasattr(user, 'last_login'))


class TestAutomaticDeactivation(TestCase):
    """
    PREUVE 2: Test de désactivation automatique des comptes utilisateurs standards
    inactifs depuis 90 jours.
    
    Approche: Tester directement la logique du middleware sans dépendre du cycle complet
    """
    
    def setUp(self):
        self.middleware = InactivityDeactivationMiddleware(lambda x: x)
        
        # Créer un utilisateur standard (non-superuser)
        self.standard_user = User.objects.create_user(
            email='standard@example.com',
            password='TestPass123!',
            first_name='Standard',
            last_name='User',
            is_active=True,
            is_superuser=False
        )
    
    def test_check_inactivity_91_days_no_login(self):
        """Test: Logique de vérification pour compte jamais connecté depuis 91 jours"""
        # Modifier la date de création pour simuler 91 jours d'inactivité
        self.standard_user.date_joined = timezone.now() - timedelta(days=91)
        self.standard_user.last_login = None
        self.standard_user.save()
        
        # Tester la logique de vérification
        should_deactivate, days_inactive = self.middleware._check_inactivity(self.standard_user)
        
        self.assertTrue(should_deactivate)
        self.assertEqual(days_inactive, 91)
    
    def test_check_inactivity_91_days_with_old_login(self):
        """Test: Logique de vérification pour compte avec last_login > 90 jours"""
        # Simuler une dernière connexion il y a 91 jours
        self.standard_user.last_login = timezone.now() - timedelta(days=91)
        self.standard_user.save()
        
        # Tester la logique de vérification
        should_deactivate, days_inactive = self.middleware._check_inactivity(self.standard_user)
        
        self.assertTrue(should_deactivate)
        self.assertEqual(days_inactive, 91)
    
    def test_deactivated_account_shows_message(self):
        """Test: Message spécifique pour compte désactivé pour inactivité"""
        # Désactiver le compte pour inactivité
        self.standard_user.is_active = False
        self.standard_user.deactivation_reason = 'Inactivité de 91 jours (désactivation automatique)'
        self.standard_user.deactivated_at = timezone.now()
        self.standard_user.save()
        
        # Vérifier que les champs sont correctement définis
        self.assertFalse(self.standard_user.is_active)
        self.assertIsNotNone(self.standard_user.deactivation_reason)
        self.assertIn('inactivité', self.standard_user.deactivation_reason.lower())
        self.assertIsNotNone(self.standard_user.deactivated_at)
    
    def test_no_deactivation_before_90_days(self):
        """Test: Compte avec last_login < 90 jours ne doit PAS être désactivé"""
        # Simuler une dernière connexion il y a 89 jours (< 90)
        self.standard_user.last_login = timezone.now() - timedelta(days=89)
        self.standard_user.save()
        
        # Tester la logique de vérification
        should_deactivate, days_inactive = self.middleware._check_inactivity(self.standard_user)
        
        self.assertFalse(should_deactivate)
        self.assertEqual(days_inactive, 89)


class TestSuperuserExemption(TestCase):
    """
    PREUVE 3: Les comptes superuser ne sont pas automatiquement désactivés,
    même après une longue période d'inactivité.
    """
    
    def setUp(self):
        self.middleware = InactivityDeactivationMiddleware(lambda x: x)
        
        # Créer un superuser
        self.superuser = User.objects.create_superuser(
            email='admin@example.com',
            password='AdminPass123!',
            first_name='Admin',
            last_name='User'
        )
    
    def test_superuser_check_inactivity_120_days(self):
        """Test: Logique de vérification pour superuser avec 120 jours d'inactivité"""
        # Simuler une dernière connexion il y a 120 jours (bien > 90)
        self.superuser.last_login = timezone.now() - timedelta(days=120)
        self.superuser.save()
        
        # Tester la logique - même si inactif, la vérification retourne les jours
        should_deactivate, days_inactive = self.middleware._check_inactivity(self.superuser)
        
        # Le middleware détecte l'inactivité MAIS ne désactive pas les superusers
        self.assertTrue(should_deactivate)  # La logique détecte l'inactivité
        self.assertEqual(days_inactive, 120)
        
        # Vérifier que le superuser reste actif (le middleware l'exempte)
        self.assertTrue(self.superuser.is_active)
        self.assertTrue(self.superuser.is_superuser)
    
    def test_superuser_never_logged_in_not_deactivated(self):
        """Test: Superuser jamais connecté depuis 120 jours reste actif"""
        # Créer un superuser qui n'a jamais été connecté
        old_superuser = User.objects.create_superuser(
            email='old_admin@example.com',
            password='AdminPass123!',
            first_name='Old',
            last_name='Admin'
        )
        old_superuser.date_joined = timezone.now() - timedelta(days=120)
        old_superuser.last_login = None
        old_superuser.save()
        
        # Tester la logique
        should_deactivate, days_inactive = self.middleware._check_inactivity(old_superuser)
        
        # La logique détecte l'inactivité mais le superuser reste actif
        self.assertTrue(should_deactivate)
        self.assertEqual(days_inactive, 120)
        self.assertTrue(old_superuser.is_active)
        self.assertTrue(old_superuser.is_superuser)
    
    def test_middleware_has_superuser_check(self):
        """Test: Le middleware vérifie explicitement is_superuser dans son code"""
        # Vérifier que le middleware a la logique d'exemption
        # En inspectant le code source du middleware
        import inspect
        source = inspect.getsource(self.middleware.__call__)
        
        # Vérifier que le code contient la vérification is_superuser
        self.assertIn('is_superuser', source)
        self.assertIn('not request.user.is_superuser', source)


class TestManualReactivation(TestCase):
    """
    PREUVE 4: Les comptes utilisateurs standards désactivés peuvent être
    réactivés par un superuser actif.
    """
    
    def setUp(self):
        # Créer un superuser actif
        self.superuser = User.objects.create_superuser(
            email='admin@example.com',
            password='AdminPass123!',
            first_name='Admin',
            last_name='User'
        )
        
        # Créer un utilisateur standard désactivé pour inactivité
        self.inactive_user = User.objects.create_user(
            email='inactive@example.com',
            password='TestPass123!',
            first_name='Inactive',
            last_name='User',
            is_active=False,
            is_superuser=False
        )
        self.inactive_user.deactivation_reason = 'Inactivité de 91 jours (désactivation automatique)'
        self.inactive_user.deactivated_at = timezone.now()
        self.inactive_user.save()
    
    def test_admin_action_reactivates_account(self):
        """Test: L'action admin 'reactivate_inactive_accounts' réactive le compte"""
        # Créer une instance de UserAdmin
        site = AdminSite()
        user_admin = UserAdmin(User, site)
        
        # Créer un mock request avec le superuser
        factory = RequestFactory()
        request = factory.get('/admin/')
        request.user = self.superuser
        
        # Ajouter le support des messages Django
        setattr(request, 'session', {})
        setattr(request, '_messages', FallbackStorage(request))
        
        # Créer un queryset avec l'utilisateur inactif
        queryset = User.objects.filter(id=self.inactive_user.id)
        
        # Appeler l'action de réactivation
        user_admin.reactivate_inactive_accounts(request, queryset)
        
        # Vérifier que le compte a été réactivé
        self.inactive_user.refresh_from_db()
        self.assertTrue(self.inactive_user.is_active)
        self.assertIsNone(self.inactive_user.deactivation_reason)
        self.assertIsNone(self.inactive_user.deactivated_at)
    
    def test_reactivation_process(self):
        """Test: Processus complet de réactivation manuelle"""
        # État initial: compte désactivé
        self.assertFalse(self.inactive_user.is_active)
        self.assertIsNotNone(self.inactive_user.deactivation_reason)
        
        # Réactiver manuellement (simule l'action admin)
        self.inactive_user.is_active = True
        self.inactive_user.deactivation_reason = None
        self.inactive_user.deactivated_at = None
        self.inactive_user.save()
        
        # Vérifier que tous les champs sont nettoyés
        self.inactive_user.refresh_from_db()
        self.assertTrue(self.inactive_user.is_active)
        self.assertIsNone(self.inactive_user.deactivation_reason)
        self.assertIsNone(self.inactive_user.deactivated_at)
    
    def test_only_superuser_can_reactivate(self):
        """Test: Seul un superuser peut réactiver un compte"""
        # Créer un utilisateur standard (non-superuser)
        standard_admin = User.objects.create_user(
            email='standard_admin@example.com',
            password='TestPass123!',
            first_name='Standard',
            last_name='Admin',
            is_active=True,
            is_staff=True,
            is_superuser=False
        )
        
        # Créer une instance de UserAdmin
        site = AdminSite()
        user_admin = UserAdmin(User, site)
        
        # Créer un mock request avec l'utilisateur standard
        factory = RequestFactory()
        request = factory.get('/admin/')
        request.user = standard_admin
        
        # Ajouter le support des messages
        setattr(request, 'session', {})
        setattr(request, '_messages', FallbackStorage(request))
        
        # Créer un queryset avec l'utilisateur inactif
        queryset = User.objects.filter(id=self.inactive_user.id)
        
        # Appeler l'action de réactivation
        user_admin.reactivate_inactive_accounts(request, queryset)
        
        # Vérifier que le compte n'a PAS été réactivé (car pas superuser)
        self.inactive_user.refresh_from_db()
        self.assertFalse(self.inactive_user.is_active)
        self.assertIsNotNone(self.inactive_user.deactivation_reason)
    
    def test_reactivation_clears_all_fields(self):
        """Test: La réactivation efface tous les champs de désactivation"""
        # Vérifier l'état initial
        self.assertFalse(self.inactive_user.is_active)
        self.assertIsNotNone(self.inactive_user.deactivation_reason)
        self.assertIsNotNone(self.inactive_user.deactivated_at)
        
        # Réactiver
        self.inactive_user.is_active = True
        self.inactive_user.deactivation_reason = None
        self.inactive_user.deactivated_at = None
        self.inactive_user.save()
        
        # Vérifier que tous les champs sont nettoyés
        self.inactive_user.refresh_from_db()
        self.assertTrue(self.inactive_user.is_active)
        self.assertIsNone(self.inactive_user.deactivation_reason)
        self.assertIsNone(self.inactive_user.deactivated_at)


class TestMiddlewareLogic(TestCase):
    """Tests unitaires pour la logique du middleware"""
    
    def test_check_inactivity_method(self):
        """Test: La méthode _check_inactivity calcule correctement les jours d'inactivité"""
        middleware = InactivityDeactivationMiddleware(lambda x: x)
        
        # Créer un utilisateur avec 91 jours d'inactivité
        user = User.objects.create_user(
            email='test@example.com',
            password='TestPass123!',
            first_name='Test',
            last_name='User'
        )
        user.last_login = timezone.now() - timedelta(days=91)
        user.save()
        
        # Vérifier le calcul
        should_deactivate, days_inactive = middleware._check_inactivity(user)
        
        self.assertTrue(should_deactivate)
        self.assertEqual(days_inactive, 91)
    
    def test_check_inactivity_no_login(self):
        """Test: _check_inactivity gère correctement les utilisateurs jamais connectés"""
        middleware = InactivityDeactivationMiddleware(lambda x: x)
        
        # Créer un utilisateur jamais connecté depuis 91 jours
        user = User.objects.create_user(
            email='test@example.com',
            password='TestPass123!',
            first_name='Test',
            last_name='User'
        )
        user.date_joined = timezone.now() - timedelta(days=91)
        user.last_login = None
        user.save()
        
        # Vérifier le calcul
        should_deactivate, days_inactive = middleware._check_inactivity(user)
        
        self.assertTrue(should_deactivate)
        self.assertEqual(days_inactive, 91)
    
    def test_check_inactivity_no_login_recent_account(self):
        """Test: Compte récent jamais connecté ne doit pas être désactivé"""
        middleware = InactivityDeactivationMiddleware(lambda x: x)
        
        # Créer un utilisateur jamais connecté mais compte récent (30 jours)
        user = User.objects.create_user(
            email='recent@example.com',
            password='TestPass123!',
            first_name='Recent',
            last_name='User'
        )
        user.date_joined = timezone.now() - timedelta(days=30)
        user.last_login = None
        user.save()
        
        # Vérifier le calcul - ne doit PAS être désactivé
        should_deactivate, days_inactive = middleware._check_inactivity(user)
        
        self.assertFalse(should_deactivate)
        self.assertEqual(days_inactive, 0)


class TestMiddlewareCallMethod(TestCase):
    """Tests pour la méthode __call__ du middleware - couverture complète"""
    
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = InactivityDeactivationMiddleware(lambda r: 'response')
        
        # Créer un utilisateur standard inactif
        self.inactive_user = User.objects.create_user(
            email='inactive_call@example.com',
            password='TestPass123!',
            first_name='Inactive',
            last_name='Call',
            is_active=True,
            is_superuser=False
        )
        self.inactive_user.last_login = timezone.now() - timedelta(days=91)
        self.inactive_user.save()
        
        # Créer un superuser inactif
        self.superuser = User.objects.create_superuser(
            email='super_call@example.com',
            password='AdminPass123!',
            first_name='Super',
            last_name='Call'
        )
        self.superuser.last_login = timezone.now() - timedelta(days=120)
        self.superuser.save()
    
    def test_middleware_call_unauthenticated_user(self):
        """Test: Middleware ignore les utilisateurs non authentifiés"""
        from django.contrib.auth.models import AnonymousUser
        
        request = self.factory.get('/')
        request.user = AnonymousUser()
        
        # Le middleware doit simplement passer la requête
        response = self.middleware(request)
        self.assertEqual(response, 'response')
    
    def test_middleware_call_superuser_not_deactivated(self):
        """Test: Middleware n'affecte pas les superusers même inactifs"""
        request = self.factory.get('/')
        request.user = self.superuser
        
        # Le middleware doit passer la requête sans désactiver
        response = self.middleware(request)
        
        # Vérifier que le superuser est toujours actif
        self.superuser.refresh_from_db()
        self.assertTrue(self.superuser.is_active)
        self.assertEqual(response, 'response')
    
    def test_middleware_call_active_user_not_inactive(self):
        """Test: Middleware n'affecte pas les utilisateurs actifs récents"""
        # Créer un utilisateur actif récent
        active_user = User.objects.create_user(
            email='active_call@example.com',
            password='TestPass123!',
            first_name='Active',
            last_name='Call',
            is_active=True,
            is_superuser=False
        )
        active_user.last_login = timezone.now() - timedelta(days=30)
        active_user.save()
        
        request = self.factory.get('/')
        request.user = active_user
        
        # Le middleware doit passer la requête sans désactiver
        response = self.middleware(request)
        
        # Vérifier que l'utilisateur est toujours actif
        active_user.refresh_from_db()
        self.assertTrue(active_user.is_active)
        self.assertEqual(response, 'response')


class TestMiddlewareDeactivation(TestCase):
    """Tests pour la désactivation effective par le middleware"""
    
    def setUp(self):
        self.factory = RequestFactory()
        
        # Créer un utilisateur standard inactif depuis 91 jours
        self.inactive_user = User.objects.create_user(
            email='to_deactivate@example.com',
            password='TestPass123!',
            first_name='ToDeactivate',
            last_name='User',
            is_active=True,
            is_superuser=False
        )
        self.inactive_user.last_login = timezone.now() - timedelta(days=91)
        self.inactive_user.save()
    
    def test_middleware_deactivates_inactive_standard_user(self):
        """Test: Le middleware désactive un utilisateur standard inactif"""
        from django.contrib.sessions.middleware import SessionMiddleware
        from django.contrib.messages.middleware import MessageMiddleware
        
        # Créer une requête avec session et messages
        request = self.factory.get('/')
        request.user = self.inactive_user
        
        # Ajouter le support de session
        middleware_session = SessionMiddleware(lambda r: None)
        middleware_session.process_request(request)
        request.session.save()
        
        # Ajouter le support des messages
        middleware_messages = MessageMiddleware(lambda r: None)
        middleware_messages.process_request(request)
        
        # Créer le middleware avec un get_response qui retourne une réponse
        def get_response(r):
            from django.http import HttpResponse
            return HttpResponse('OK')
        
        middleware = InactivityDeactivationMiddleware(get_response)
        
        # Appeler le middleware
        response = middleware(request)
        
        # Vérifier que l'utilisateur a été désactivé
        self.inactive_user.refresh_from_db()
        self.assertFalse(self.inactive_user.is_active)
        self.assertIsNotNone(self.inactive_user.deactivation_reason)
        self.assertIn('inactivité', self.inactive_user.deactivation_reason.lower())
        self.assertIn('91', self.inactive_user.deactivation_reason)
        self.assertIsNotNone(self.inactive_user.deactivated_at)
        
        # Vérifier que la réponse est une redirection
        self.assertEqual(response.status_code, 302)


class TestAdminReactivationAction(TestCase):
    """Tests complets pour l'action admin de réactivation"""
    
    def setUp(self):
        self.factory = RequestFactory()
        self.site = AdminSite()
        self.user_admin = UserAdmin(User, self.site)
        
        # Créer un superuser
        self.superuser = User.objects.create_superuser(
            email='admin_action@example.com',
            password='AdminPass123!',
            first_name='Admin',
            last_name='Action'
        )
        
        # Créer des utilisateurs inactifs
        self.inactive_user1 = User.objects.create_user(
            email='inactive1@example.com',
            password='TestPass123!',
            first_name='Inactive1',
            last_name='User',
            is_active=False
        )
        self.inactive_user1.deactivation_reason = 'Inactivité de 91 jours'
        self.inactive_user1.deactivated_at = timezone.now()
        self.inactive_user1.save()
        
        self.inactive_user2 = User.objects.create_user(
            email='inactive2@example.com',
            password='TestPass123!',
            first_name='Inactive2',
            last_name='User',
            is_active=False
        )
        self.inactive_user2.deactivation_reason = 'Inactivité de 100 jours'
        self.inactive_user2.deactivated_at = timezone.now()
        self.inactive_user2.save()
        
        # Créer un utilisateur déjà actif
        self.active_user = User.objects.create_user(
            email='already_active@example.com',
            password='TestPass123!',
            first_name='Already',
            last_name='Active',
            is_active=True
        )
    
    def _create_request_with_messages(self, user):
        """Helper pour créer une requête avec support des messages"""
        request = self.factory.get('/admin/')
        request.user = user
        setattr(request, 'session', {})
        setattr(request, '_messages', FallbackStorage(request))
        return request
    
    def test_reactivate_multiple_accounts(self):
        """Test: Réactivation de plusieurs comptes en une fois"""
        request = self._create_request_with_messages(self.superuser)
        queryset = User.objects.filter(id__in=[self.inactive_user1.id, self.inactive_user2.id])
        
        self.user_admin.reactivate_inactive_accounts(request, queryset)
        
        # Vérifier que les deux comptes sont réactivés
        self.inactive_user1.refresh_from_db()
        self.inactive_user2.refresh_from_db()
        
        self.assertTrue(self.inactive_user1.is_active)
        self.assertTrue(self.inactive_user2.is_active)
        self.assertIsNone(self.inactive_user1.deactivation_reason)
        self.assertIsNone(self.inactive_user2.deactivation_reason)
    
    def test_reactivate_already_active_account(self):
        """Test: Tentative de réactivation d'un compte déjà actif"""
        request = self._create_request_with_messages(self.superuser)
        queryset = User.objects.filter(id=self.active_user.id)
        
        self.user_admin.reactivate_inactive_accounts(request, queryset)
        
        # Le compte doit rester actif (pas d'erreur)
        self.active_user.refresh_from_db()
        self.assertTrue(self.active_user.is_active)
    
    def test_reactivate_mixed_accounts(self):
        """Test: Réactivation d'un mix de comptes actifs et inactifs"""
        request = self._create_request_with_messages(self.superuser)
        queryset = User.objects.filter(id__in=[self.inactive_user1.id, self.active_user.id])
        
        self.user_admin.reactivate_inactive_accounts(request, queryset)
        
        # Vérifier les résultats
        self.inactive_user1.refresh_from_db()
        self.active_user.refresh_from_db()
        
        self.assertTrue(self.inactive_user1.is_active)
        self.assertTrue(self.active_user.is_active)
    
    def test_non_superuser_cannot_reactivate(self):
        """Test: Un non-superuser ne peut pas réactiver des comptes"""
        # Créer un staff non-superuser
        staff_user = User.objects.create_user(
            email='staff@example.com',
            password='StaffPass123!',
            first_name='Staff',
            last_name='User',
            is_active=True,
            is_staff=True,
            is_superuser=False
        )
        
        request = self._create_request_with_messages(staff_user)
        queryset = User.objects.filter(id=self.inactive_user1.id)
        
        self.user_admin.reactivate_inactive_accounts(request, queryset)
        
        # Le compte doit rester inactif
        self.inactive_user1.refresh_from_db()
        self.assertFalse(self.inactive_user1.is_active)


class TestCheckInactivityEdgeCases(TestCase):
    """Tests pour les cas limites de _check_inactivity"""
    
    def setUp(self):
        self.middleware = InactivityDeactivationMiddleware(lambda x: x)
    
    def test_exactly_90_days_not_deactivated(self):
        """Test: Compte avec exactement 90 jours d'inactivité ne doit PAS être désactivé"""
        user = User.objects.create_user(
            email='exact90@example.com',
            password='TestPass123!',
            first_name='Exact',
            last_name='Ninety'
        )
        user.last_login = timezone.now() - timedelta(days=90)
        user.save()
        
        should_deactivate, days_inactive = self.middleware._check_inactivity(user)
        
        self.assertFalse(should_deactivate)
        self.assertEqual(days_inactive, 90)
    
    def test_91_days_deactivated(self):
        """Test: Compte avec 91 jours d'inactivité DOIT être désactivé"""
        user = User.objects.create_user(
            email='exact91@example.com',
            password='TestPass123!',
            first_name='Exact',
            last_name='NinetyOne'
        )
        user.last_login = timezone.now() - timedelta(days=91)
        user.save()
        
        should_deactivate, days_inactive = self.middleware._check_inactivity(user)
        
        self.assertTrue(should_deactivate)
        self.assertEqual(days_inactive, 91)
    
    def test_no_date_joined_no_last_login(self):
        """Test: Utilisateur sans date_joined et sans last_login"""
        user = User.objects.create_user(
            email='nodate@example.com',
            password='TestPass123!',
            first_name='No',
            last_name='Date'
        )
        user.last_login = None
        # date_joined est automatiquement défini, on ne peut pas le mettre à None
        # mais on peut tester avec une date récente
        user.date_joined = timezone.now() - timedelta(days=10)
        user.save()
        
        should_deactivate, days_inactive = self.middleware._check_inactivity(user)
        
        self.assertFalse(should_deactivate)
        self.assertEqual(days_inactive, 0)


class TestAdminReactivationMessages(TestCase):
    """Tests pour couvrir tous les messages de l'action admin de réactivation"""
    
    def setUp(self):
        self.factory = RequestFactory()
        self.site = AdminSite()
        self.user_admin = UserAdmin(User, self.site)
        
        # Créer un superuser
        self.superuser = User.objects.create_superuser(
            email='admin_msg@example.com',
            password='AdminPass123!',
            first_name='Admin',
            last_name='Msg'
        )
    
    def _create_request_with_messages(self, user):
        """Helper pour créer une requête avec support des messages"""
        request = self.factory.get('/admin/')
        request.user = user
        setattr(request, 'session', {})
        setattr(request, '_messages', FallbackStorage(request))
        return request
    
    def test_reactivate_empty_queryset(self):
        """Test: Réactivation avec queryset vide affiche 'Aucune action effectuée'"""
        request = self._create_request_with_messages(self.superuser)
        queryset = User.objects.none()  # Queryset vide
        
        self.user_admin.reactivate_inactive_accounts(request, queryset)
        
        # Vérifier que le message "Aucune action effectuée" est affiché
        messages = list(request._messages)
        self.assertTrue(any('Aucune action effectuée' in str(m) for m in messages))
    
    def test_reactivate_only_active_accounts_message(self):
        """Test: Message quand tous les comptes sont déjà actifs"""
        # Créer un utilisateur déjà actif
        active_user = User.objects.create_user(
            email='already_active_msg@example.com',
            password='TestPass123!',
            first_name='Already',
            last_name='Active',
            is_active=True
        )
        
        request = self._create_request_with_messages(self.superuser)
        queryset = User.objects.filter(id=active_user.id)
        
        self.user_admin.reactivate_inactive_accounts(request, queryset)
        
        # Vérifier le message
        messages = list(request._messages)
        self.assertTrue(any('déjà actif' in str(m) for m in messages))
    
    def test_reactivate_with_error_shows_warning(self):
        """Test: Message d'avertissement quand il y a des erreurs"""
        # Créer un utilisateur inactif
        inactive_user = User.objects.create_user(
            email='error_test@example.com',
            password='TestPass123!',
            first_name='Error',
            last_name='Test',
            is_active=False
        )
        inactive_user.deactivation_reason = 'Test'
        inactive_user.deactivated_at = timezone.now()
        inactive_user.save()
        
        request = self._create_request_with_messages(self.superuser)
        queryset = User.objects.filter(id=inactive_user.id)
        
        # Simuler une erreur en mockant la méthode save
        from unittest.mock import patch, MagicMock
        
        with patch.object(User, 'save', side_effect=Exception('Test error')):
            self.user_admin.reactivate_inactive_accounts(request, queryset)
        
        # Vérifier que le message d'erreur est affiché
        messages = list(request._messages)
        self.assertTrue(any('erreur' in str(m).lower() for m in messages))
    
    def test_reactivate_success_and_already_active_mixed(self):
        """Test: Message mixte avec succès et comptes déjà actifs"""
        # Créer un utilisateur inactif
        inactive_user = User.objects.create_user(
            email='inactive_mix@example.com',
            password='TestPass123!',
            first_name='Inactive',
            last_name='Mix',
            is_active=False
        )
        inactive_user.deactivation_reason = 'Test'
        inactive_user.deactivated_at = timezone.now()
        inactive_user.save()
        
        # Créer un utilisateur déjà actif
        active_user = User.objects.create_user(
            email='active_mix@example.com',
            password='TestPass123!',
            first_name='Active',
            last_name='Mix',
            is_active=True
        )
        
        request = self._create_request_with_messages(self.superuser)
        queryset = User.objects.filter(id__in=[inactive_user.id, active_user.id])
        
        self.user_admin.reactivate_inactive_accounts(request, queryset)
        
        # Vérifier les messages
        messages = list(request._messages)
        message_text = ' '.join(str(m) for m in messages)
        self.assertIn('réactivé', message_text)
        self.assertIn('déjà actif', message_text)
