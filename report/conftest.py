import pytest


@pytest.fixture(autouse=True)
def email_backend_and_notifications(settings):
    """Neutralise l'envoi d'emails pendant les tests.
    - Utilise le backend en mémoire.
    - Désactive les notifications email custom si paramètre présent.
    """
    settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
    # Si le projet utilise ce flag pour activer/désactiver les envois
    try:
        settings.ENABLE_EMAIL_NOTIFICATIONS = False
    except Exception:
        pass
