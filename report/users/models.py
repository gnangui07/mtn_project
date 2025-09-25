from django.db import models
from django.contrib.auth.models import AbstractUser
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

class CustomUser(AbstractUser):
    """Modèle d'utilisateur personnalisé étendant l'AbstractUser de Django"""
    email = models.EmailField(_('email address'), unique=True)
    jeton_activation = models.CharField(max_length=100, blank=True, null=True, verbose_name=_('activation token'))
    active_manuellement = models.BooleanField(default=False, verbose_name=_('manually activated'))
    date_derniere_connexion = models.DateTimeField(null=True, blank=True, verbose_name=_('last connection date'))
    mot_de_passe_temporaire = models.CharField(max_length=100, blank=True, null=True, verbose_name=_('temporary password'))
    date_expiration_jeton = models.DateTimeField(null=True, blank=True, verbose_name=_('token expiration date'))
    email_envoye = models.BooleanField(default=False, verbose_name=_('activation email sent'))
    service = models.CharField(max_length=100, verbose_name=_('service'))
    USERNAME_FIELD = 'username'
    EMAIL_FIELD = 'email'
    REQUIRED_FIELDS = ['email', 'first_name', 'last_name']
    
    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['last_name', 'first_name']
        db_table = 'users_customuser'  # Changé de 'rapports_customuser' à 'users_customuser'
    
    def __str__(self):
        return self.get_full_name() or self.username
    
    def get_full_name(self):
        """Returns the first_name plus the last_name, with a space in between."""
        full_name = f"{self.first_name} {self.last_name}"
        return full_name.strip()
    
    def get_short_name(self):
        """Returns the short name for the user."""
        return self.first_name

    



class UserVoicePreference(models.Model):
    """Server-side persistence of welcome voice settings per user"""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='voice_prefs')
    enabled = models.BooleanField(default=True)
    lang = models.CharField(max_length=16, default='fr-FR')
    voice_name = models.CharField(max_length=128, blank=True, default='')

    class Meta:
        db_table = 'users_voice_preference'
        verbose_name = 'Voice Preference'
        verbose_name_plural = 'Voice Preferences'

    def __str__(self):
        return f"VoicePrefs({self.user_id}, {self.lang}, {self.voice_name or 'auto'})"
