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
from django.contrib.auth import views as auth_views
from . import views
from . import forms

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
    
    # Changement de mot de passe (connecté)
    # - GET: affiche le formulaire de changement (connecté)
    # - POST: valide et change le mot de passe (connecté)
    # Réponse: HTML (GET) / Redirect (POST)
    path('changement-password/', views.change_password_view, name='change_password'),
    
    # Activity summary API (deprecated): supprimée car non utilisée
    
    # ==========================
    # PASSWORD RESET
    # ==========================
    path('password-reset/', 
         auth_views.PasswordResetView.as_view(
             template_name='users/password_reset.html',
             email_template_name='users/password_reset_email.html',
             subject_template_name='users/password_reset_subject.txt',
             success_url='/users/password-reset/done/',
             form_class=forms.CustomPasswordResetForm
         ), 
         name='password_reset'),
         
    path('password-reset/done/', 
         auth_views.PasswordResetDoneView.as_view(
             template_name='users/password_reset_done.html'
         ), 
         name='password_reset_done'),
         
    path('password-reset/confirm/<uidb64>/<token>/', 
         auth_views.PasswordResetConfirmView.as_view(
             template_name='users/password_reset_confirm.html',
             success_url='/users/password-reset/complete/'
         ), 
         name='password_reset_confirm'),
         
    path('password-reset/complete/', 
         auth_views.PasswordResetCompleteView.as_view(
             template_name='users/password_reset_complete.html'
         ), 
         name='password_reset_complete'),
]
