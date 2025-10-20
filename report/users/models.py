from django.db import models
from django.contrib.auth.models import AbstractUser
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.hashers import make_password, check_password
import secrets
import string

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.contrib.auth.hashers import make_password, check_password
import secrets
import string


class UserManager(BaseUserManager):
    """Gestionnaire personnalisé pour le modèle User"""
    
    def create_user(self, email, password=None, **extra_fields):
        """Crée et sauvegarde un utilisateur standard"""
        if not email:
            raise ValueError("L'adresse email est obligatoire")
        
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        """Crée et sauvegarde un superutilisateur"""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Le superutilisateur doit avoir is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Le superutilisateur doit avoir is_superuser=True.')
        
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Modèle utilisateur personnalisé pour l'application"""
    
    # Informations de base
    email = models.EmailField(
        verbose_name="Adresse email",
        max_length=255,
        unique=True,
    )
    first_name = models.CharField(
        verbose_name="Prénom",
        max_length=150,
        blank=True
    )
    last_name = models.CharField(
        verbose_name="Nom",
        max_length=150,
        blank=True
    )
    phone = models.CharField(
        verbose_name="Téléphone",
        max_length=20,
        blank=True
    )
    
    # Choix de services basés sur le fichier Excel
    SERVICE_CHOICES = [
        ('NWG', 'NWG'),
        ('ITS', 'ITS'),
        ('FAC', 'FAC'),
    ]
    
    service = models.CharField(
        verbose_name="Services autorisés",
        max_length=255,
        blank=True,
        null=True,
        help_text="Services de l'utilisateur séparés par des virgules. Sélectionnez dans la liste. Laissez vide pour les superusers."
    )
    
    # Activation et mot de passe temporaire
    is_active = models.BooleanField(
        verbose_name="Compte actif",
        default=False,
        help_text="Indique si le compte est activé"
    )
    is_staff = models.BooleanField(
        verbose_name="Membre du staff",
        default=False
    )
    
    temporary_password = models.CharField(
        verbose_name="Mot de passe temporaire (haché)",
        max_length=255,
        blank=True,
        null=True,
        help_text="Mot de passe temporaire haché pour l'activation"
    )
    activation_token = models.CharField(
        verbose_name="Token d'activation",
        max_length=100,
        blank=True,
        unique=True,
        null=True
    )
    token_created_at = models.DateTimeField(
        verbose_name="Date de création du token",
        blank=True,
        null=True
    )
    
    # Dates
    date_joined = models.DateTimeField(
        verbose_name="Date d'inscription",
        default=timezone.now
    )
    last_login = models.DateTimeField(
        verbose_name="Dernière connexion",
        blank=True,
        null=True
    )
    
    objects = UserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']
    
    class Meta:
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"
        ordering = ['-date_joined']
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.email})"
    
    def get_full_name(self):
        """Retourne le nom complet de l'utilisateur"""
        return f"{self.first_name} {self.last_name}".strip() or self.email
    
    def get_short_name(self):
        """Retourne le prénom de l'utilisateur"""
        return self.first_name or self.email
    
    def get_services_list(self):
        """
        Retourne la liste des services autorisés pour cet utilisateur.
        
        Returns:
            list: Liste des services (ex: ['NWG', 'ITS', 'RAN'])
        """
        if not self.service:
            return []
        
        # Séparer par virgule et nettoyer les espaces
        services = [s.strip().upper() for s in self.service.split(',') if s.strip()]
        return services
    
    def generate_temporary_password(self):
        """Génère un mot de passe temporaire aléatoire et le stocke haché"""
        # Génère un mot de passe de 12 caractères avec lettres, chiffres et symboles
        characters = string.ascii_letters + string.digits + "!@#$%"
        temp_password = ''.join(secrets.choice(characters) for _ in range(12))
        
        # Hache le mot de passe avant de le stocker
        self.temporary_password = make_password(temp_password)
        
        return temp_password  # Retourne le mot de passe en clair pour l'envoi par email
    
    def check_temporary_password(self, raw_password):
        """Vérifie si le mot de passe temporaire fourni est correct"""
        if not self.temporary_password:
            return False
        return check_password(raw_password, self.temporary_password)
    
    def generate_activation_token(self):
        """Génère un token d'activation unique"""
        self.activation_token = secrets.token_urlsafe(32)
        self.token_created_at = timezone.now()
        return self.activation_token
    
    def is_token_valid(self, max_age_hours=48):
        """Vérifie si le token d'activation est encore valide (48h par défaut)"""
        if not self.token_created_at:
            return False
        
        age = timezone.now() - self.token_created_at
        return age.total_seconds() < (max_age_hours * 3600)
    
    def activate_account(self):
        """Active le compte utilisateur"""
        self.is_active = True
        self.activation_token = None
        self.temporary_password = None
        self.token_created_at = None
        self.save()

    



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
