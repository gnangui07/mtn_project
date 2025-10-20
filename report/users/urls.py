"""
Routage de l'application `users`.

Expose les URL d'authentification (déconnexion, activation), préférences vocales
et résumés d'activité.
"""
 
from django.urls import path
from . import views
from . import api

app_name = 'users'

urlpatterns = [
    # Authentification
    path('login/', views.login_view, name='login'),
    path('deconnexion/', views.deconnexion_view, name='deconnexion'),
    
    # URLs d'activation avec token
    path('activate/<str:token>/', views.activate_account, name='activate'),
    path('confirm-password/<str:token>/', views.confirm_password, name='confirm_password'),
    path('play-welcome-sound/', views.play_welcome_sound, name='play_welcome_sound'),
    # Voice preferences API
    path('voice-prefs/', views.get_voice_prefs, name='get_voice_prefs'),
    path('voice-prefs/set/', views.set_voice_prefs, name='set_voice_prefs'),
    # Activity summary API (for welcome TTS)
    path('activity-summary/', api.activity_summary, name='activity_summary'),
]
