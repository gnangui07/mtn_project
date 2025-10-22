"""
Django settings for reports project.
"""

from pathlib import Path
import os
from dotenv import load_dotenv  # AJOUT IMPORTANT

# Charge les variables d'environnement
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# ==================== CONFIGURATION DE BASE ====================

# Environnement (development/production)
DJANGO_ENV = os.environ.get('DJANGO_ENV', 'development')

# Clé secrète
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'clé-par-défaut-pour-dev-seulement')

# Mode debug selon l'environnement
DEBUG = (DJANGO_ENV == 'development')

if DJANGO_ENV == 'production':
    ALLOWED_HOSTS = ['ton-domaine.com', 'www.ton-domaine.com', '127.0.0.1']
    print("Mode PRODUCTION active")
else:
    ALLOWED_HOSTS = ['127.0.0.1', 'localhost', '192.168.8.122']
    print("Mode DEVELOPPEMENT active")

# ==================== APPLICATIONS ====================

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'django.contrib.humanize',
    'widget_tweaks',
    'users.apps.UsersConfig',
    'orders.apps.OrdersConfig',
    'core.apps.CoreConfig',
    'rest_framework',
]

SITE_ID = 1

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'core.middleware.UtilisateurActuelMiddleware',
    'core.middleware.NoCacheMiddleware',  # Anti-cache pour empêcher le retour après déconnexion
]

ROOT_URLCONF = 'reports.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates', BASE_DIR / 'core' / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'reports.wsgi.application'

# ==================== BASE DE DONNÉES ====================

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'report_db'),
        'USER': os.environ.get('DB_USER', 'postgres'),
        'PASSWORD': os.environ.get('DB_PASSWORD', 'aime'),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }
}

# ==================== VALIDATION MOTS DE PASSE ====================

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ==================== INTERNATIONALISATION ====================

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# ==================== FICHIERS STATIQUES ====================

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ==================== AUTHENTIFICATION ====================

LOGIN_URL = '/connexion/'
LOGIN_REDIRECT_URL = 'core:accueil'
LOGOUT_REDIRECT_URL = '/connexion/'
AUTH_USER_MODEL = 'users.User'

# ==================== CONFIGURATION DES SESSIONS ====================

# Expiration de la session après 3 heures d'inactivité (en secondes)
SESSION_COOKIE_AGE = 10800  # 3 heures = 3 * 60 * 60 = 10800 secondes

# La session expire quand le navigateur se ferme
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# Sauvegarder la session à chaque requête (pour mettre à jour le temps d'inactivité)
SESSION_SAVE_EVERY_REQUEST = True

# Nom du cookie de session
SESSION_COOKIE_NAME = 'msrn_sessionid'

# HttpOnly pour empêcher l'accès JavaScript au cookie de session
SESSION_COOKIE_HTTPONLY = True

# SameSite pour protection CSRF
SESSION_COOKIE_SAMESITE = 'Lax'

# Sécurité: empêcher la mise en cache des pages protégées
# (sera renforcé par le middleware)
CACHE_MIDDLEWARE_SECONDS = 0

# ==================== CONFIGURATION EMAIL ====================

# Configuration email unifiée pour dev et prod
# Les emails seront envoyés via Gmail SMTP dans les deux cas
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True').lower() in ('true', '1', 'yes')
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')

# Pour déboguer les emails en développement (optionnel)
if DJANGO_ENV == 'development':
    # Afficher les emails dans la console en plus de les envoyer
    import logging
    logging.getLogger('django.core.mail').setLevel(logging.DEBUG)

DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'msrn-notifications@mtn-ci.com')

# URL du site (pour les liens dans les emails)
SITE_URL = os.environ.get('SITE_URL', 'http://localhost:8000')

# Activer/désactiver les notifications email
ENABLE_EMAIL_NOTIFICATIONS = os.environ.get('ENABLE_EMAIL_NOTIFICATIONS', 'True').lower() in ('true', '1', 'yes')

# ==================== SÉCURITÉ PRODUCTION ====================

if DJANGO_ENV == 'production':
    # Sécurité renforcée
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    
    # HTTPS Strict Transport Security
    SECURE_HSTS_SECONDS = 31536000  # 1 an
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    
    # Protection CSRF
    CSRF_TRUSTED_ORIGINS = [
        'https://ton-domaine.com',
        'https://www.ton-domaine.com',
    ]
    
    # Optimisation des performances
    STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'