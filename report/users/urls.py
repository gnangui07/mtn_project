"""
Routage de l'application `users`.

Expose les URL d'authentification (déconnexion, activation), préférences vocales
et résumés d'activité.
"""
 
from django.urls import path
from . import views
from . import api
from django.contrib.auth import views as auth_views
from .forms import FormulaireConnexion

app_name = 'users'

urlpatterns = [
    # Authentification
    # L'URL de connexion est maintenant définie dans le fichier principal urls.py
    path('deconnexion/', views.deconnexion_view, name='deconnexion'),
    path('activation/', views.ActivationCompteView.as_view(), name='activation'),
    path('activation/confirmer/', views.ConfirmerActivationView.as_view(), name='confirmer_activation'),
    path('play-welcome-sound/', views.play_welcome_sound, name='play_welcome_sound'),
    # Voice preferences API
    path('voice-prefs/', views.get_voice_prefs, name='get_voice_prefs'),
    path('voice-prefs/set/', views.set_voice_prefs, name='set_voice_prefs'),
    # Activity summary API (for welcome TTS)
    path('activity-summary/', api.activity_summary, name='activity_summary'),
    
    # Activité utilisateur
    path('activite/', views.enregistrer_activite_utilisateur, name='enregistrer_activite'),
]
