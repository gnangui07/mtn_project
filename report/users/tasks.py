"""
Tâches Celery pour l'application users.

Ce module contient les tâches asynchrones liées à la gestion des utilisateurs:
- Envoi d'emails d'activation
- Nettoyage des tokens expirés
- Cache des données utilisateur
"""
from celery import shared_task
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def send_activation_email_task(self, user_id: int, temp_password: str = None, site_url: str = None):
    """
    Envoie un email d'activation de compte de façon asynchrone.
    
    Args:
        user_id: ID de l'utilisateur à notifier
        temp_password: Mot de passe temporaire en clair (optionnel, pour l'email)
        site_url: URL de base du site (ex: http://192.168.8.121:8000)
        
    Returns:
        bool: True si l'email a été envoyé, False sinon
    """
    from django.core.mail import send_mail
    from django.conf import settings
    from django.urls import reverse
    from .models import User
    
    try:
        user = User.objects.get(pk=user_id)
        
        if user.is_active:
            logger.info(f"User {user.email} is already active, skipping email")
            return False
        
        # Générer le token si nécessaire
        if not user.activation_token:
            user.generate_activation_token()
        
        # Construction du lien d'activation avec l'URL fournie ou par défaut
        base_url = site_url or settings.SITE_URL
        activation_path = reverse('users:activate', kwargs={'token': user.activation_token})
        activation_url = f"{base_url}{activation_path}"
        
        # Sujet de l'email
        site_name = getattr(settings, 'SITE_NAME', 'MTN CI')
        subject = f"Activation de votre compte - {site_name}"
        
        # Message en texte brut
        plain_message = f"""
Bonjour {user.first_name} {user.last_name},

Votre compte a été créé avec succès sur la plateforme CAPEX Works Valuation Tool de MTN Côte d'Ivoire.

Vos identifiants temporaires :
Email : {user.email}
{f"Mot de passe temporaire : {temp_password}" if temp_password else ""}

Pour activer votre compte, cliquez sur ce lien :
{activation_url}

Ce lien est valide pendant 48 heures.
Vous devrez créer un nouveau mot de passe sécurisé lors de l'activation.

© 2025 MTN Côte d'Ivoire
        """
        
        # Message HTML
        html_message = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #FFCC00; padding: 20px; text-align: center; }}
                .content {{ background-color: #f9f9f9; padding: 30px; border-radius: 5px; }}
                .credentials {{ background-color: #fff; padding: 15px; border-left: 4px solid #FFCC00; margin: 20px 0; }}
                .button {{ display: inline-block; padding: 12px 30px; background-color: #FFCC00; color: #000; text-decoration: none; border-radius: 5px; font-weight: bold; }}
                .footer {{ text-align: center; margin-top: 20px; font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1 style="margin: 0; color: #000;">Bienvenue !</h1>
                </div>
                <div class="content">
                    <p>Bonjour <strong>{user.first_name} {user.last_name}</strong>,</p>
                    
                    <p>Votre compte a été créé avec succès sur la plateforme CAPEX Works Valuation Tool de MTN Côte d'Ivoire.</p>
                    
                    <div class="credentials">
                        <p><strong>Vos identifiants temporaires :</strong></p>
                        <p>📧 <strong>Email :</strong> {user.email}</p>
                        {f'<p>🔑 <strong>Mot de passe temporaire :</strong> {temp_password}</p>' if temp_password else ''}
                    </div>
                    
                    <p>Pour activer votre compte, veuillez cliquer sur le bouton ci-dessous :</p>
                    
                    <p style="text-align: center; margin: 30px 0;">
                        <a href="{activation_url}" class="button">Activer mon compte</a>
                    </p>
                    
                    <p style="font-size: 12px; color: #666;">
                        Si le bouton ne fonctionne pas, copiez et collez ce lien dans votre navigateur :<br>
                        <a href="{activation_url}">{activation_url}</a>
                    </p>
                    
                    <p><strong>⚠️ Important :</strong></p>
                    <ul>
                        <li>Ce lien est valide pendant 48 heures</li>
                        <li>Vous devrez créer un nouveau mot de passe sécurisé lors de l'activation</li>
                        <li>Ne partagez jamais vos identifiants</li>
                    </ul>
                </div>
                <div class="footer">
                    <p>© 2025 MTN Côte d'Ivoire - CAPEX Works Valuation Tool</p>
                    <p>Cet email a été envoyé automatiquement, merci de ne pas y répondre.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"Activation email sent to {user.email}")
        return True
        
    except User.DoesNotExist:
        logger.error(f"User with ID {user_id} not found")
        return False
    except Exception as exc:
        logger.error(f"Failed to send activation email: {exc}")
        # Réessayer en cas d'échec (max 3 fois, avec délai de 60s)
        raise self.retry(exc=exc, countdown=60)


@shared_task
def cleanup_expired_tokens():
    """
    Nettoie les tokens d'activation expirés (plus de 48 heures).
    
    Cette tâche peut être planifiée via Celery Beat pour s'exécuter
    périodiquement (ex: une fois par jour).
    
    Returns:
        int: Nombre de tokens nettoyés
    """
    from .models import User
    
    expiry_threshold = timezone.now() - timedelta(hours=48)
    
    # Trouver les utilisateurs avec des tokens expirés et non activés
    expired_users = User.objects.filter(
        is_active=False,
        token_created_at__lt=expiry_threshold,
        activation_token__isnull=False
    )
    
    count = expired_users.count()
    
    # Effacer les tokens expirés
    expired_users.update(
        activation_token=None,
        token_created_at=None,
        temporary_password=None
    )
    
    logger.info(f"Cleaned up {count} expired activation tokens")
    return count


@shared_task
def cache_user_permissions(user_id: int):
    """
    Met en cache les permissions d'un utilisateur pour accélérer les vérifications.
    
    Args:
        user_id: ID de l'utilisateur
        
    Returns:
        dict: Les permissions cachées
    """
    from .models import User
    
    try:
        user = User.objects.get(pk=user_id)
        
        permissions = {
            'is_active': user.is_active,
            'is_staff': user.is_staff,
            'is_superuser': user.is_superuser,
            'services': user.get_services_list(),
            'role': getattr(user, 'role', None),
        }
        
        # Cacher pendant 10 minutes
        cache_key = f"user_permissions_{user_id}"
        cache.set(cache_key, permissions, timeout=600)
        
        logger.debug(f"Cached permissions for user {user_id}")
        return permissions
        
    except User.DoesNotExist:
        logger.error(f"User with ID {user_id} not found")
        return None


def get_cached_user_permissions(user_id: int) -> dict | None:
    """
    Récupère les permissions en cache d'un utilisateur.
    
    Args:
        user_id: ID de l'utilisateur
        
    Returns:
        dict ou None: Les permissions en cache, ou None si non trouvées
    """
    cache_key = f"user_permissions_{user_id}"
    return cache.get(cache_key)


@shared_task
def invalidate_user_cache(user_id: int):
    """
    Invalide le cache d'un utilisateur après modification.
    
    Args:
        user_id: ID de l'utilisateur
    """
    cache_key = f"user_permissions_{user_id}"
    cache.delete(cache_key)
    logger.debug(f"Invalidated cache for user {user_id}")
