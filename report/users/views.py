"""
Vues de l'application `users`.

Contient les vues de gestion d'authentification/activation, préférences vocales
et utilitaires anti-cache, exposées via des FBV/CBV. Aucune logique
métiers critique n'est implémentée ici.
"""
 
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from django.http import JsonResponse
from .models import User, UserVoicePreference
from functools import wraps
from django.views.decorators.csrf import csrf_protect

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
        
        # Vider complètement la session avant la déconnexion
        request.session.flush()
        
        # Déconnecter l'utilisateur
        logout(request)
        
        # Créer la réponse de redirection avec en-têtes anti-cache renforcés
        response = redirect('/connexion/')
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0, private'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        
        # Supprimer explicitement le cookie de session
        response.delete_cookie('msrn_sessionid')
        response.delete_cookie('sessionid')  # Cookie par défaut de Django
        
        return response
    return redirect('/connexion/')

@csrf_protect
@never_cache_view
def play_welcome_sound(request):
    if request.method == 'POST' and request.user.is_authenticated:
        # Préparer le texte à prononcer
        username = request.user.get_full_name() or request.user.email
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


def activate_account(request, token):
    """Page d'activation du compte avec le token"""
    user = get_object_or_404(User, activation_token=token)
    
    # Vérifie si le token est encore valide
    if not user.is_token_valid():
        messages.error(request, "Ce lien d'activation a expiré. Veuillez contacter l'administrateur.")
        return redirect('users:login')
    
    # Vérifie si le compte est déjà activé
    if user.is_active:
        messages.info(request, "Votre compte est déjà activé. Vous pouvez vous connecter.")
        return redirect('users:login')
    
    if request.method == 'POST':
        email = request.POST.get('email')
        temp_password = request.POST.get('temp_password')
        
        # Vérifie les identifiants
        if email != user.email:
            messages.error(request, "L'adresse email ne correspond pas.")
            return render(request, 'users/activation.html', {'user': user})
        
        if not user.check_temporary_password(temp_password):
            messages.error(request, "Le mot de passe temporaire est incorrect.")
            return render(request, 'users/activation.html', {'user': user})
        
        # Redirige vers la page de confirmation pour créer le nouveau mot de passe
        return redirect('users:confirm_password', token=token)
    
    return render(request, 'users/activation.html', {'user': user})


def confirm_password(request, token):
    """Page de confirmation et création du nouveau mot de passe"""
    user = get_object_or_404(User, activation_token=token)
    
    # Vérifie si le token est encore valide
    if not user.is_token_valid():
        messages.error(request, "Ce lien d'activation a expiré. Veuillez contacter l'administrateur.")
        return redirect('users:login')
    
    # Vérifie si le compte est déjà activé
    if user.is_active:
        messages.info(request, "Votre compte est déjà activé. Vous pouvez vous connecter.")
        return redirect('users:login')
    
    if request.method == 'POST':
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        # Validation des mots de passe
        if not new_password or not confirm_password:
            messages.error(request, "Veuillez remplir tous les champs.")
            return render(request, 'users/confirmer_activation.html', {'user': user})
        
        if new_password != confirm_password:
            messages.error(request, "Les mots de passe ne correspondent pas.")
            return render(request, 'users/confirmer_activation.html', {'user': user})
        
        if len(new_password) < 8:
            messages.error(request, "Le mot de passe doit contenir au moins 8 caractères.")
            return render(request, 'users/confirmer_activation.html', {'user': user})
        
        # Définit le nouveau mot de passe et active le compte
        user.set_password(new_password)
        user.activate_account()
        
        messages.success(request, "Votre compte a été activé avec succès ! Vous pouvez maintenant vous connecter.")
        return redirect('users:login')
    
    return render(request, 'users/confirmer_activation.html', {'user': user})


@never_cache_view
def login_view(request):
    """Page de connexion"""
    if request.user.is_authenticated:
        return redirect('core:accueil')
    
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        # Authentification
        user = authenticate(request, username=email, password=password)
        
        if user is not None:
            if user.is_active:
                # Vider l'ancienne session si elle existe
                request.session.flush()
                
                # Connecter l'utilisateur (crée une nouvelle session)
                login(request, user)
                
                # Régénérer la clé de session pour sécurité
                request.session.cycle_key()
                
                messages.success(request, f"Bienvenue {user.get_full_name()} !")
                
                # Redirige vers la page demandée ou la page d'accueil
                next_url = request.GET.get('next', 'core:accueil')
                
                # Créer la réponse avec anti-cache
                response = redirect(next_url)
                response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
                response['Pragma'] = 'no-cache'
                response['Expires'] = '0'
                
                return response
            else:
                messages.error(request, "Votre compte n'est pas encore activé. Veuillez vérifier votre email.")
        else:
            messages.error(request, "Email ou mot de passe incorrect.")
    
    # Ajouter anti-cache à la page de connexion aussi
    response = render(request, 'users/connexion.html')
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response
