"""But:
- Définir les modèles utilisateurs avec authentification par email et préférences vocales.

Étapes:
- Créer un User personnalisé avec email comme identifiant unique.
- Gérer l'activation de compte (mot de passe temporaire + token).
- Stocker les préférences de synthèse vocale par utilisateur.

Entrées:
- Email, mot de passe, prénom, nom, services autorisés.
- Token d'activation, mot de passe temporaire.

Sorties:
- Instances User et UserVoicePreference persistées.
- Validation de tokens et mots de passe temporaires."""

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
    """Gestionnaire personnalisé pour le modèle `User`.

    Rôle:
    - Créer des utilisateurs (standard et superutilisateurs) avec email comme
      identifiant unique.
    - Appliquer des valeurs par défaut et validations cohérentes.
    """
    
    def create_user(self, email, password=None, **extra_fields):
        """Crée et sauvegarde un utilisateur standard.

        Paramètres:
        - email (str): identifiant unique, obligatoire.
        - password (str|None): mot de passe en clair; sera haché via `set_password`.
        - extra_fields: attributs additionnels du modèle (ex: first_name, last_name).

        Retour:
        - User: instance persistée.

        Effets de bord:
        - Normalise l'email (lower/trim) avec `normalize_email`.
        - Stocke le hash du mot de passe, jamais le clair.
        """
        if not email:
            raise ValueError("L'adresse email est obligatoire")
        
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        """Crée et sauvegarde un superutilisateur.

        Contraintes:
        - is_staff=True et is_superuser=True sont imposés.
        - is_active=True pour permettre la connexion immédiate.
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Le superutilisateur doit avoir is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Le superutilisateur doit avoir is_superuser=True.')
        
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Modèle utilisateur personnalisé (auth par email).

    Principales caractéristiques:
    - Identifiant de connexion: `email` (unique).
    - Champs de profil simples (prénom, nom, téléphone).
    - Champ `service` (liste de valeurs séparées par virgules) pour restreindre
      des fonctionnalités par service, sauf pour les superusers.
    - Gestion d'activation: `temporary_password` (haché), `activation_token`,
      et `token_created_at` (pour calculer la validité).

    Méthodes utilitaires:
    - `get_services_list()`: parse la chaîne `service` en liste normalisée.
    - `generate_temporary_password()`: crée un mot de passe temporaire, le
      stocke haché et retourne le clair (à envoyer par email).
    - `check_temporary_password()`: vérifie un mot de passe temporaire saisi.
    - `generate_activation_token()`: génère un token URL-safe + timestamp.
    - `is_token_valid(max_age_hours=48)`: valide la fenêtre d'activation.
    - `activate_account()`: active le compte et purge les secrets temporaires.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._password_has_changed = False
        self._original_password = None
    
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
    
    # Champs pour la gestion de l'expiration des mots de passe
    # NOTE: default=None pour éviter que PasswordAgeValidator bloque lors de la première activation
    password_changed_at = models.DateTimeField(
        verbose_name="Date du dernier changement de mot de passe",
        null=True,
        blank=True,
        default=None,
        help_text="Date du dernier changement de mot de passe (pour expiration). NULL = premier mot de passe pas encore défini."
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
    
    # Champs pour la gestion de la désactivation automatique
    deactivation_reason = models.TextField(
        verbose_name="Raison de la désactivation",
        blank=True,
        null=True,
        help_text="Raison pour laquelle le compte a été désactivé (ex: inactivité, sécurité)"
    )
    deactivated_at = models.DateTimeField(
        verbose_name="Date de désactivation",
        blank=True,
        null=True,
        help_text="Date à laquelle le compte a été désactivé"
    )
    
    objects = UserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']
    
    class Meta:
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"
        ordering = ['-date_joined']
    
    def save(self, *args, **kwargs):
        """Normalise l'email et détecte les changements de mot de passe."""
        # Détecter si le mot de passe a changé
        if self.pk:
            try:
                old_instance = User.objects.get(pk=self.pk)
                self._original_password = old_instance.password
                if old_instance.password != self.password:
                    self._password_has_changed = True
            except User.DoesNotExist:
                pass
        
        # Normaliser l'email en minuscules
        if self.email:
            self.email = self.email.lower().strip()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.email})"
    
    def get_full_name(self):
        """Retourne le nom complet de l'utilisateur.

        Si prénom/nom sont vides, fallback sur l'email.
        """
        return f"{self.first_name} {self.last_name}".strip() or self.email
    
    def get_short_name(self):
        """Retourne le prénom de l'utilisateur.

        Fallback sur l'email si non renseigné.
        """
        return self.first_name or self.email
    
    def get_services_list(self):
        """Liste des services autorisés pour cet utilisateur.

        Lecture:
        - Le champ `service` contient une chaîne séparée par virgules.
        - On normalise: trim, filtre les vides, et majuscules.

        Retour:
        - list[str]: ex. ['NWG', 'ITS'].
        - [] si `service` est vide/non défini.
        """
        if not self.service:
            return []
        
        # Séparer par virgule et nettoyer les espaces
        services = [s.strip().upper() for s in self.service.split(',') if s.strip()]
        return services
    
    def generate_temporary_password(self):
        """Génère un mot de passe temporaire aléatoire et le stocke haché.

        Sécurité:
        - Retourne la valeur en clair (à envoyer par canal sécurisé: email interne).
        - Ne stocke que le hash (`temporary_password`).
        - Génère selon la nouvelle politique de sécurité (12+ caractères avec complexité).

        Retour:
        - str: le mot de passe temporaire en clair (respectant les nouvelles règles).
        """
        import random
        
        # Générer un mot de passe de 14 caractères avec complexité
        # Au moins une majuscule, une minuscule, un chiffre, un spécial
        uppercase = random.choice(string.ascii_uppercase)
        lowercase = random.choice(string.ascii_lowercase)
        digit = random.choice(string.digits)
        special = random.choice("@!-_")
        
        # Compléter avec 10 caractères aléatoires pour atteindre 14
        remaining_chars = ''.join(
            secrets.choice(string.ascii_letters + string.digits + "@!-_") 
            for _ in range(10)
        )
        
        # Mélanger tous les caractères
        all_chars = list(uppercase + lowercase + digit + special + remaining_chars)
        random.shuffle(all_chars)
        temp_password = ''.join(all_chars)
        
        # Hache le mot de passe avant de le stocker
        self.temporary_password = make_password(temp_password)
        
        return temp_password  # Retourne le mot de passe en clair pour l'envoi par email
    
    def check_temporary_password(self, raw_password):
        """Vérifie un mot de passe temporaire saisi par l'utilisateur.

        Paramètres:
        - raw_password (str): valeur en clair à vérifier.

        Retour:
        - bool: True si conforme au hash stocké, False sinon ou si absent.
        """
        if not self.temporary_password:
            return False
        return check_password(raw_password, self.temporary_password)
    
    def generate_activation_token(self):
        """Génère et mémorise un token d'activation unique.

        Détails:
        - Utilise `secrets.token_urlsafe(32)` (sûr pour URLs et aléatoire).
        - Sauvegarde aussi l'horodatage `token_created_at` (pour l'expiration).

        Retour:
        - str: le token généré.
        """
        self.activation_token = secrets.token_urlsafe(32)
        self.token_created_at = timezone.now()
        return self.activation_token
    
    def is_token_valid(self, max_age_hours=48):
        """Indique si le token d'activation est encore valide.

        Paramètres:
        - max_age_hours (int): durée de validité (48h par défaut).

        Retour:
        - bool: True si `token_created_at` est défini et non expiré.
        """
        if not self.token_created_at:
            return False
        
        age = timezone.now() - self.token_created_at
        return age.total_seconds() < (max_age_hours * 3600)
    
    def activate_account(self):
        """Active le compte utilisateur et purge les secrets temporaires.

        Effets de bord:
        - is_active=True
        - Efface `activation_token`, `temporary_password`, `token_created_at`
        - Sauvegarde en base (`save()`).
        """
        self.is_active = True
        self.activation_token = None
        self.temporary_password = None
        self.token_created_at = None
        self.save()

    



class UserVoicePreference(models.Model):
    """Préférences de synthèse vocale par utilisateur (persistées côté serveur).

    Utilité:
    - Permet de mémoriser les choix de l'utilisateur pour l'annonce de bienvenue
      (TTS): activation, langue, nom de voix.

    Champs:
    - user (OneToOne -> User): un seul profil de voix par utilisateur.
      CASCADE: si l'utilisateur est supprimé, ses préférences le sont aussi.
    - enabled (bool): activer/désactiver la lecture.
    - lang (str, max 16): ex. 'fr-FR'.
    - voice_name (str, max 128): nom spécifique d'une voix (sinon auto).
    """
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
