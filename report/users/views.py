"""
Vues de l'application `users`.

Contient les vues de gestion d'authentification/activation, préférences vocales
et utilitaires anti-cache, exposées via des FBV/CBV. Aucune logique
métiers critique n'est implémentée ici.
"""
 
from django.shortcuts import render, redirect
from django.views.generic import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages
from django.utils import timezone
from .models import CustomUser, UserVoicePreference
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from functools import wraps
from django.views.decorators.csrf import csrf_protect
from django.views.generic.edit import FormView
from django.contrib.auth.forms import SetPasswordForm
from django import forms
from django.http import JsonResponse

# Mixin pour ajouter des en-têtes anti-cache aux CBV (Class-Based Views)
class NoCacheMixin:
    """Mixin qui ajoute des en-têtes anti-cache à la réponse"""
    def dispatch(self, *args, **kwargs):
        response = super().dispatch(*args, **kwargs)
        # Ajouter des en-têtes pour éviter la mise en cache
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response

# Décorateur pour ajouter des en-têtes anti-cache aux FBV (Function-Based Views)
def never_cache_view(view_func):
    """Décorateur qui ajoute des en-têtes anti-cache à la réponse"""
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        response = view_func(request, *args, **kwargs)
        # Ajouter des en-têtes pour éviter la mise en cache
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response
    return wrapped_view

@login_required
@csrf_protect
@never_cache_view
def deconnexion_view(request):
    if request.method == 'POST':
        # Récupérer l'utilisateur avant la déconnexion
        if request.user.is_authenticated:
            user = request.user
            # Mettre à jour le statut en ligne
            if hasattr(user, 'is_online'):
                user.is_online = False
            # Enregistrer la date de dernière connexion
            if hasattr(user, 'date_derniere_connexion'):
                user.date_derniere_connexion = timezone.now()
            user.save()
        # Déconnecter l'utilisateur
        logout(request)
        # Ajouter des en-têtes pour éviter la mise en cache
        response = redirect('/connexion/')
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response
    return redirect('/connexion/')

@csrf_protect
@never_cache_view
def play_welcome_sound(request):
    if request.method == 'POST' and request.user.is_authenticated:
        # Préparer le texte à prononcer
        username = request.user.get_full_name() or request.user.username
        welcome_text = f"Bienvenue {username}"
        
        return JsonResponse({
            'status': 'success',
            'welcome_text': welcome_text,
            'username': username
        })
    return JsonResponse({'status': 'error'}, status=400)

@login_required
@csrf_protect
@never_cache_view
def get_voice_prefs(request):
    if request.method != 'GET':
        return JsonResponse({'detail': 'Method not allowed'}, status=405)
    prefs, _ = UserVoicePreference.objects.get_or_create(user=request.user)
    return JsonResponse({
        'enabled': prefs.enabled,
        'lang': prefs.lang,
        'voiceName': prefs.voice_name,
    })

@login_required
@csrf_protect
@never_cache_view
def set_voice_prefs(request):
    if request.method != 'POST':
        return JsonResponse({'detail': 'Method not allowed'}, status=405)
    try:
        data = request.POST
        # Support JSON body as well
        if request.content_type and 'application/json' in request.content_type.lower():
            import json
            data = json.loads(request.body.decode('utf-8') or '{}')
        enabled = bool(data.get('enabled', True))
        lang = str(data.get('lang', 'fr-FR'))[:16]
        voice_name = str(data.get('voiceName', ''))[:128]
        prefs, _ = UserVoicePreference.objects.get_or_create(user=request.user)
        prefs.enabled = enabled
        prefs.lang = lang
        prefs.voice_name = voice_name
        prefs.save()
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'detail': str(e)}, status=400)

class FormulaireActivation(forms.Form):
    """Formulaire pour l'activation du compte utilisateur"""
    username = forms.CharField(
        label="Nom d'utilisateur", 
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': "Nom d'utilisateur"})
    )
    mot_de_passe_temporaire = forms.CharField(
        label="Mot de passe temporaire", 
        max_length=100,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Mot de passe temporaire'})
    )
    
    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get('username')
        mot_de_passe_temporaire = cleaned_data.get('mot_de_passe_temporaire')
        
        if username and mot_de_passe_temporaire:
            # Vérifier si l'utilisateur existe
            try:
                user = CustomUser.objects.get(username=username)
            except CustomUser.DoesNotExist:
                raise forms.ValidationError("Nom d'utilisateur invalide.")
            
            # Vérifier si le token d'activation est valide
            if not user.jeton_activation:
                raise forms.ValidationError("Ce compte n'a pas de jeton d'activation valide.")
                
            # Vérifier si le mot de passe temporaire correspond
            if not user.check_password(mot_de_passe_temporaire):
                raise forms.ValidationError("Mot de passe temporaire invalide.")
                
            # Vérifier si le compte est déjà activé
            if user.active_manuellement:
                raise forms.ValidationError("Ce compte a déjà été activé.")
                
            # Vérifier si le jeton n'a pas expiré
            if user.date_expiration_jeton and user.date_expiration_jeton < timezone.now():
                raise forms.ValidationError("Le jeton d'activation a expiré. Veuillez contacter l'administrateur.")
                
            # Stocker l'utilisateur pour l'utiliser dans form_valid
            self.user = user
            
        return cleaned_data

class ActivationCompteView(FormView):
    """Vue pour l'activation du compte utilisateur"""
    template_name = 'users/activation.html'  # Mis à jour vers le template dans users
    form_class = FormulaireActivation
    success_url = reverse_lazy('users:confirmer_activation')
    
    def get_initial(self):
        initial = super().get_initial()
        # Pré-remplir le nom d'utilisateur s'il est fourni dans l'URL
        username = self.request.GET.get('username', '')
        if username:
            initial['username'] = username
            # Ajouter un message pour indiquer à l'utilisateur qu'il doit saisir son mot de passe temporaire
            messages.info(self.request, "Veuillez saisir le mot de passe temporaire qui vous a été communiqué par email pour activer votre compte.")
        return initial
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Ajouter des informations supplémentaires au contexte
        context['activation_info'] = "Pour activer votre compte, vous devez saisir votre nom d'utilisateur et le mot de passe temporaire qui vous ont été communiqués par email."
        return context
    
    def form_valid(self, form):
        # Récupérer l'utilisateur du formulaire
        user = form.user
        
        # Stocker l'utilisateur dans la session pour la vue suivante
        self.request.session['activation_user_id'] = user.id
        
        # Marquer le jeton comme utilisé
        user.active_manuellement = True
        user.save()
        
        messages.success(self.request, "Compte vérifié avec succès. Veuillez définir votre nouveau mot de passe.")
        return super().form_valid(form)

class ConfirmerActivationView(FormView):
    """Vue pour confirmer l'activation et définir un nouveau mot de passe"""
    template_name = 'users/confirmer_activation.html'  # Mis à jour vers le template dans users
    form_class = SetPasswordForm
    success_url = '/connexion/'
    
    def dispatch(self, request, *args, **kwargs):
        # Vérifier si l'ID de l'utilisateur est dans la session
        if 'activation_user_id' not in request.session:
            messages.error(request, "Vous devez d'abord activer votre compte.")
            return redirect('users:activation')
        return super().dispatch(request, *args, **kwargs)
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # Récupérer l'utilisateur de la session
        user_id = self.request.session['activation_user_id']
        user = CustomUser.objects.get(id=user_id)
        kwargs['user'] = user
        return kwargs
    
    def form_valid(self, form):
        # Enregistrer le nouveau mot de passe
        form.save()
        
        # Nettoyer la session
        if 'activation_user_id' in self.request.session:
            del self.request.session['activation_user_id']
        
        messages.success(self.request, "Votre mot de passe a été défini avec succès. Vous pouvez maintenant vous connecter.")
        return super().form_valid(form)

@login_required
def enregistrer_activite_utilisateur(request):
    """Enregistre l'activité d'un utilisateur"""
    # Créer ou mettre à jour l'activité de l'utilisateur
    try:
        # Rechercher une activité active existante
        activite = UserActivity.objects.get(utilisateur=request.user, active=True)
        # Mettre à jour la date de dernière action
        activite.date_derniere_action = timezone.now()
        activite.save(update_fields=['date_derniere_action'])
    except UserActivity.DoesNotExist:
        # Créer une nouvelle activité
        UserActivity.objects.create(utilisateur=request.user)
    
    return JsonResponse({'status': 'success'})
