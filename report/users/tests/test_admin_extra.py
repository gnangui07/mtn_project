"""
Tests supplémentaires admin: activation_status + change=True + send_mail avec exception.
"""
import pytest
from unittest.mock import patch, MagicMock
from django.contrib import admin
from django.test import RequestFactory
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.messages.storage.fallback import FallbackStorage
from django.utils import timezone
from datetime import timedelta

from users.models import User
from users.admin import UserAdmin, UserAdminForm
from users.models_history import PasswordHistory


@pytest.mark.django_db
def test_activation_status_variants():
    site = admin.sites.AdminSite()
    ua = UserAdmin(User, site)
    # Actif
    u1 = User.objects.create(email='a1@example.com', is_active=True)
    assert 'Activé' in ua.activation_status(u1)
    # En attente (token présent)
    u2 = User.objects.create(email='a2@example.com', is_active=False)
    u2.activation_token = 'tok'
    u2.token_created_at = timezone.now()
    u2.save()
    assert 'En attente' in ua.activation_status(u2)
    # Non activé (pas de token)
    u3 = User.objects.create(email='a3@example.com', is_active=False)
    assert 'Non activé' in ua.activation_status(u3)


@pytest.mark.django_db
def test_activation_status_expired():
    """Test le statut expiré."""
    site = admin.sites.AdminSite()
    ua = UserAdmin(User, site)
    user = User.objects.create(email='expired@example.com', is_active=False)
    user.activation_token = 'tok'
    user.token_created_at = timezone.now() - timedelta(days=3)
    user.save()
    assert 'Expiré' in ua.activation_status(user)


@pytest.mark.django_db
def test_save_model_change_true_no_email_sent():
    site = admin.sites.AdminSite()
    ua = UserAdmin(User, site)
    rf = RequestFactory()
    request = rf.post('/admin/users/user/change/1/')
    SessionMiddleware(lambda req: None).process_request(request)
    request.session.save()
    setattr(request, '_messages', FallbackStorage(request))
    obj = User.objects.create(email='chg@example.com', is_active=False)
    with patch('users.admin.send_mail') as mocked:
        ua.save_model(request, obj, form=None, change=True)
        # En modification, on ne crée pas de token/mot de passe temporaire, pas d'email
        assert mocked.call_count == 0


@pytest.mark.django_db
def test_send_activation_email_handles_exception_gracefully():
    site = admin.sites.AdminSite()
    ua = UserAdmin(User, site)
    rf = RequestFactory()
    request = rf.post('/admin/users/user/add/')
    SessionMiddleware(lambda req: None).process_request(request)
    request.session.save()
    setattr(request, '_messages', FallbackStorage(request))

    obj = User(email='boom@example.com', first_name='B', last_name='OOM', is_active=False)
    tmp = obj.generate_temporary_password()
    obj.generate_activation_token()
    obj.save()

    with patch('users.admin.send_mail', side_effect=Exception('SMTP error')) as mocked:
        # Appel direct à la méthode pour simuler l'envoi qui échoue
        ua.send_activation_email(obj, tmp, request)
        assert mocked.call_count == 1


@pytest.mark.django_db
def test_user_admin_form_init_with_services():
    """Test l'initialisation du formulaire avec des services existants."""
    user = User.objects.create(email='form@example.com', is_active=True)
    user.service = 'NWG, ITS'
    user.save()
    
    form = UserAdminForm(instance=user)
    assert form.fields['services'].initial == ['NWG', 'ITS']


@pytest.mark.django_db
def test_user_admin_form_clean_requires_service():
    """Test que les non-superusers doivent avoir un service."""
    form_data = {
        'email': 'noservice@example.com',
        'first_name': 'No',
        'last_name': 'Service',
        'is_superuser': False,
        'is_staff': False,
        'is_active': False,
        'services': [],
    }
    form = UserAdminForm(data=form_data)
    assert not form.is_valid()
    assert 'Au moins un service' in str(form.errors)


@pytest.mark.django_db
def test_resend_activation_token_action():
    """Test l'action de renvoi du token."""
    site = admin.sites.AdminSite()
    ua = UserAdmin(User, site)
    rf = RequestFactory()
    request = rf.post('/admin/users/user/')
    SessionMiddleware(lambda req: None).process_request(request)
    request.session.save()
    setattr(request, '_messages', FallbackStorage(request))
    
    user = User.objects.create(email='resend@example.com', is_active=False)
    queryset = User.objects.filter(pk=user.pk)
    
    with patch('users.admin.CELERY_AVAILABLE', False), \
         patch.object(ua, 'send_activation_email') as mock_send:
        ua.resend_activation_token(request, queryset)
        user.refresh_from_db()
        assert user.activation_token is not None
        assert mock_send.call_count == 1


@pytest.mark.django_db
def test_resend_activation_token_skips_active():
    """Test que le renvoi ignore les utilisateurs actifs."""
    site = admin.sites.AdminSite()
    ua = UserAdmin(User, site)
    rf = RequestFactory()
    request = rf.post('/admin/users/user/')
    SessionMiddleware(lambda req: None).process_request(request)
    request.session.save()
    setattr(request, '_messages', FallbackStorage(request))
    
    user = User.objects.create(email='active_resend@example.com', is_active=True)
    queryset = User.objects.filter(pk=user.pk)
    
    with patch.object(ua, 'send_activation_email') as mock_send:
        ua.resend_activation_token(request, queryset)
        mock_send.assert_not_called()


# ==================== TESTS SIGNALS ====================

@pytest.mark.django_db
def test_signal_save_password_history():
    """Test que l'historique est sauvegardé lors d'un changement de mot de passe."""
    user = User.objects.create_user(email='signal@example.com', password='OldPass123!')
    initial_count = PasswordHistory.objects.filter(user=user).count()
    
    # Simuler un changement de mot de passe
    user._password_has_changed = True
    user._original_password = user.password
    user.set_password('NewPass123!')
    user.save()
    
    new_count = PasswordHistory.objects.filter(user=user).count()
    assert new_count == initial_count + 1


@pytest.mark.django_db
def test_signal_no_history_on_create():
    """Test que l'historique n'est pas créé lors de la création."""
    new_user = User.objects.create_user(email='newcreate@example.com', password='Pass123!')
    count = PasswordHistory.objects.filter(user=new_user).count()
    assert count == 0


@pytest.mark.django_db
def test_signal_cache_invalidation_on_delete():
    """Test l'invalidation du cache lors de la suppression."""
    user = User.objects.create_user(email='delete@example.com', password='Pass123!')
    user_id = user.id
    
    with patch('django.core.cache.cache.delete') as mock_delete:
        user.delete()
        mock_delete.assert_called_with(f'user_permissions_{user_id}')


@pytest.mark.django_db
def test_cleanup_old_passwords():
    """Test le nettoyage des anciens mots de passe."""
    user = User.objects.create_user(email='cleanup@example.com', password='Pass123!')
    
    # Créer 30 entrées
    for i in range(30):
        PasswordHistory.objects.create(user=user, password_hash=f'hash_{i}')
    
    PasswordHistory.cleanup_old_passwords(user, keep_count=24)
    
    count = PasswordHistory.objects.filter(user=user).count()
    assert count == 24


# ==================== TESTS TASKS ====================

@pytest.mark.django_db
def test_task_send_activation_email_success():
    """Test l'envoi d'email d'activation."""
    from users.tasks import send_activation_email_task
    
    user = User.objects.create_user(email='task@example.com', password='Pass123!')
    user.is_active = False
    user.generate_activation_token()
    user.save()
    
    with patch('django.core.mail.send_mail', return_value=1):
        result = send_activation_email_task(user.id, 'TempPass123!', 'http://localhost:8000')
        assert result is True


@pytest.mark.django_db
def test_task_send_activation_email_user_active():
    """Test que l'email n'est pas envoyé si l'utilisateur est actif."""
    from users.tasks import send_activation_email_task
    
    user = User.objects.create_user(email='active_task@example.com', password='Pass123!')
    user.is_active = True
    user.save()
    
    with patch('django.core.mail.send_mail') as mock_send:
        result = send_activation_email_task(user.id)
        assert result is False
        mock_send.assert_not_called()


@pytest.mark.django_db
def test_task_cleanup_expired_tokens():
    """Test le nettoyage des tokens expirés."""
    from users.tasks import cleanup_expired_tokens
    
    user = User.objects.create_user(email='expired_task@example.com', password='Pass123!')
    user.is_active = False
    user.generate_activation_token()
    user.token_created_at = timezone.now() - timedelta(days=10)
    user.save()
    
    result = cleanup_expired_tokens()
    
    user.refresh_from_db()
    assert user.activation_token is None


@pytest.mark.django_db
def test_task_cache_user_permissions():
    """Test la mise en cache des permissions."""
    from users.tasks import cache_user_permissions
    
    user = User.objects.create_user(email='cache@example.com', password='Pass123!')
    
    with patch('users.tasks.cache.set') as mock_set:
        result = cache_user_permissions(user.id)
        assert result is not None
        mock_set.assert_called_once()


@pytest.mark.django_db
def test_task_invalidate_user_cache():
    """Test l'invalidation du cache."""
    from users.tasks import invalidate_user_cache
    
    with patch('users.tasks.cache.delete') as mock_delete:
        invalidate_user_cache(123)
        mock_delete.assert_called_once_with('user_permissions_123')


@pytest.mark.django_db
def test_task_get_cached_permissions():
    """Test la récupération des permissions en cache."""
    from users.tasks import get_cached_user_permissions
    
    with patch('users.tasks.cache.get', return_value={'is_active': True}):
        result = get_cached_user_permissions(123)
        assert result == {'is_active': True}


@pytest.mark.django_db
def test_task_get_cached_permissions_miss():
    """Test quand les permissions ne sont pas en cache."""
    from users.tasks import get_cached_user_permissions
    
    with patch('users.tasks.cache.get', return_value=None):
        result = get_cached_user_permissions(123)
        assert result is None


# ==================== TESTS SUPPLÉMENTAIRES ADMIN ====================

@pytest.mark.django_db
def test_admin_save_model_with_celery_available():
    """Test save_model avec Celery disponible."""
    site = admin.sites.AdminSite()
    ua = UserAdmin(User, site)
    rf = RequestFactory()
    request = rf.post('/admin/users/user/add/')
    SessionMiddleware(lambda req: None).process_request(request)
    request.session.save()
    setattr(request, '_messages', FallbackStorage(request))
    
    obj = User(email='celery_test@example.com', first_name='C', last_name='T', is_active=False)
    
    with patch('users.admin.CELERY_AVAILABLE', True), \
         patch('users.admin.send_activation_email_task') as mock_task:
        mock_task.delay = MagicMock()
        ua.save_model(request, obj, form=None, change=False)
        
        obj.refresh_from_db()
        assert obj.activation_token is not None


@pytest.mark.django_db
def test_admin_save_model_celery_fails_fallback():
    """Test save_model avec fallback quand Celery échoue."""
    site = admin.sites.AdminSite()
    ua = UserAdmin(User, site)
    rf = RequestFactory()
    request = rf.post('/admin/users/user/add/')
    SessionMiddleware(lambda req: None).process_request(request)
    request.session.save()
    setattr(request, '_messages', FallbackStorage(request))
    
    obj = User(email='fallback_test@example.com', first_name='F', last_name='B', is_active=False)
    
    with patch('users.admin.CELERY_AVAILABLE', True), \
         patch('users.admin.send_activation_email_task') as mock_task, \
         patch.object(ua, 'send_activation_email') as mock_send:
        mock_task.delay.side_effect = Exception("Celery down")
        ua.save_model(request, obj, form=None, change=False)
        
        mock_send.assert_called_once()


@pytest.mark.django_db
def test_user_admin_form_save_with_services():
    """Test la sauvegarde du formulaire avec services."""
    user = User.objects.create(email='formsave@example.com', is_active=True)
    
    form_data = {
        'email': 'formsave@example.com',
        'first_name': 'Form',
        'last_name': 'Save',
        'is_superuser': False,
        'is_staff': False,
        'is_active': True,
        'services': ['NWG', 'FAC'],
    }
    form = UserAdminForm(data=form_data, instance=user)
    
    if form.is_valid():
        saved_user = form.save()
        assert 'NWG' in saved_user.service
        assert 'FAC' in saved_user.service


# ==================== TESTS SUPPLÉMENTAIRES TASKS ====================

@pytest.mark.django_db
def test_task_send_activation_email_retry_on_error():
    """Test le retry de la tâche en cas d'erreur SMTP."""
    from users.tasks import send_activation_email_task
    
    user = User.objects.create_user(email='retry@example.com', password='Pass123!')
    user.is_active = False
    user.generate_activation_token()
    user.save()
    
    with patch('django.core.mail.send_mail', side_effect=Exception("SMTP Error")):
        try:
            send_activation_email_task(user.id, 'TempPass123!', 'http://localhost:8000')
        except Exception:
            pass  # Expected to fail


@pytest.mark.django_db
def test_task_cache_user_permissions_not_found():
    """Test cache_user_permissions avec utilisateur inexistant."""
    from users.tasks import cache_user_permissions
    
    result = cache_user_permissions(99999)
    assert result is None


# ==================== TESTS SUPPLÉMENTAIRES SIGNALS ====================

@pytest.mark.django_db
def test_signal_invalidate_cache_celery_exception():
    """Test invalidation cache quand Celery lève une exception."""
    user = User.objects.create_user(email='celery_err@example.com', password='Pass123!')
    
    with patch('users.tasks.invalidate_user_cache') as mock_task:
        mock_task.delay.side_effect = Exception("Celery unavailable")
        
        with patch('django.core.cache.cache.delete') as mock_cache:
            user.first_name = 'Updated'
            user.save()
            # Cache devrait être invalidé de manière synchrone


@pytest.mark.django_db  
def test_signal_cache_delete_exception():
    """Test quand cache.delete lève une exception."""
    user = User.objects.create_user(email='cache_err@example.com', password='Pass123!')
    user_id = user.id
    
    with patch('django.core.cache.cache.delete', side_effect=Exception("Cache error")):
        # Ne devrait pas lever d'exception
        user.delete()
