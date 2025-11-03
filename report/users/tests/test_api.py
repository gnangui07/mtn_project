"""
Tests API Voix – explications simples:
- get_voice_prefs: doit demander la connexion et renvoyer des valeurs par défaut.
- set_voice_prefs: doit demander la connexion, accepter JSON/Form, et enregistrer les valeurs
  (avec limites de longueur pour éviter les abus).
"""
import json
import pytest
from django.urls import reverse
from users.models import User, UserVoicePreference


@pytest.mark.django_db
class TestVoicePrefsAPI:
    # -----------------------------
    # GET /users/voice-prefs/
    # -----------------------------
    def test_get_voice_prefs_requires_login(self, client):
        """Sans être connecté, on est redirigé vers la page de connexion."""
        url = reverse('users:get_voice_prefs')
        resp = client.get(url)
        # Django redirige vers /login/ par défaut pour login_required
        assert resp.status_code in (302, 301)
        assert 'login' in resp.headers.get('Location', '') or resp.url

    def test_get_voice_prefs_returns_defaults_when_logged_in(self, client):
        """Connecté: renvoie un JSON avec enabled/lang/voiceName. Crée l'entrée si absente."""
        user = User.objects.create(email='voice@example.com', first_name='V', last_name='O', is_active=True)
        user.set_password('Pwd123456!')
        user.save()
        client.login(username=user.email, password='Pwd123456!')
        url = reverse('users:get_voice_prefs')
        resp = client.get(url)
        assert resp.status_code == 200
        data = resp.json()
        assert set(data.keys()) == {'enabled', 'lang', 'voiceName'}
        # Une entrée doit exister en base
        assert UserVoicePreference.objects.filter(user=user).exists()

    # -----------------------------
    # POST /users/voice-prefs/set/
    # -----------------------------
    def test_set_voice_prefs_requires_login(self, client):
        """Sans être connecté, la mise à jour est refusée (redirigée)."""
        url = reverse('users:set_voice_prefs')
        resp = client.post(url, {'enabled': True, 'lang': 'fr-FR'})
        assert resp.status_code in (302, 301)
        assert 'login' in resp.headers.get('Location', '') or resp.url

    def test_set_voice_prefs_accepts_json_and_persists(self, client):
        """Connecté: accepte JSON, enregistre, et renvoie {'status': 'ok'}."""
        user = User.objects.create(email='json@example.com', first_name='J', last_name='S', is_active=True)
        user.set_password('Pwd123456!')
        user.save()
        client.login(username=user.email, password='Pwd123456!')
        url = reverse('users:set_voice_prefs')
        payload = {
            'enabled': False,
            'lang': 'en-US',
            'voiceName': 'Test Voice'
        }
        resp = client.post(url, data=json.dumps(payload), content_type='application/json')
        assert resp.status_code == 200
        assert resp.json().get('status') == 'ok'
        # Vérifier en base
        prefs = UserVoicePreference.objects.get(user=user)
        assert prefs.enabled is False
        assert prefs.lang == 'en-US'
        assert prefs.voice_name == 'Test Voice'

    def test_set_voice_prefs_truncates_long_values(self, client):
        """Les champs lang (<=16) et voiceName (<=128) sont tronqués côté serveur."""
        user = User.objects.create(email='long@example.com', first_name='L', last_name='G', is_active=True)
        user.set_password('Pwd123456!')
        user.save()
        client.login(username=user.email, password='Pwd123456!')
        url = reverse('users:set_voice_prefs')
        long_lang = 'fr-FR-SUPER-LONG-LANG-CODE'
        long_voice = 'V'*200
        resp = client.post(url, data=json.dumps({'enabled': True, 'lang': long_lang, 'voiceName': long_voice}), content_type='application/json')
        assert resp.status_code == 200
        prefs = UserVoicePreference.objects.get(user=user)
        assert len(prefs.lang) <= 16
        assert len(prefs.voice_name) <= 128
