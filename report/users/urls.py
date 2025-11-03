"""
Routage de l'application `users`.

Ce module définit les chemins (URLs) publics de l'app `users`. Chaque entrée
explique:
- La vue appelée (fonction dans `views.py` ou `api.py`).
- À quoi sert l'URL (connexion, déconnexion, activation, préférences voix, etc.).
- Le type d'accès habituel (anonyme ou connecté) et les méthodes HTTP typiques.
- Les paramètres d'URL (ex: `token`) et le type de réponse (HTML/JSON/redirect).
"""
 
from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    # Authentification
    # - GET: affiche la page de connexion (anonyme)
    # - POST: authentifie l'utilisateur puis redirige (anonyme)
    # Réponse: HTML (GET) / Redirect (POST)
    path('login/', views.login_view, name='login'),

    # Déconnexion sécurisée (connecté)
    # - POST attendu: vide la session, logout, supprime cookies, redirect
    # - GET: redirige vers /connexion/
    # Réponse: Redirect (toujours)
    path('deconnexion/', views.deconnexion_view, name='deconnexion'),
    
    # URLs d'activation avec token
    # - activate/<token>/:
    #   * GET: formulaire email + mot de passe temporaire (anonyme)
    #   * POST: vérifie les identifiants puis redirige vers confirm-password
    #   Réponse: HTML/Redirect
    path('activate/<str:token>/', views.activate_account, name='activate'),

    # - confirm-password/<token>/:
    #   * GET: formulaire nouveau mot de passe (x2) (anonyme)
    #   * POST: set_password + activation, puis redirect vers login
    #   Réponse: HTML/Redirect
    path('confirm-password/<str:token>/', views.confirm_password, name='confirm_password'),

    # Lecture simple pour TTS d'accueil: supprimée (gérée côté client uniquement)
    
    # Voice preferences API
    # - GET /voice-prefs/: récupère (ou crée par défaut) les préférences voix (connecté)
    #   Réponse: JSON {enabled, lang, voiceName}
    path('voice-prefs/', views.get_voice_prefs, name='get_voice_prefs'),
    # - POST /voice-prefs/set/: met à jour les préférences voix (form ou JSON) (connecté)
    #   Réponse: JSON {'status': 'ok'} ou erreur 400
    path('voice-prefs/set/', views.set_voice_prefs, name='set_voice_prefs'),
    
    # Activity summary API (deprecated): supprimée car non utilisée
]
