"""
Vues de l'application `users`.

Ce module regroupe des vues très simples et orientées "interface" pour:
 - l'authentification (connexion/déconnexion),
 - l'activation de compte via un token,
 - la gestion des préférences de synthèse vocale,
 - l'ajout d'en-têtes anti-cache (pour éviter que le navigateur garde des pages
   sensibles en mémoire après déconnexion).

 Chaque vue précise:
 - Qui peut y accéder (anonyme / connecté).
 - La méthode HTTP attendue.
 - Les données d'entrée (form/JSON/URL).
 - La réponse renvoyée (HTML/JSON/redirect) et les effets de bord (session,
   cookies, base de données).
Aucune logique métier critique n'est implémentée ici.
"""
 
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from django.http import JsonResponse
from django.core.exceptions import ValidationError
from .models import User, UserVoicePreference
from functools import wraps
from django.views.decorators.csrf import csrf_protect
from .forms import CustomPasswordResetForm

# Import des tâches Celery pour le cache et les opérations asynchrones
from .tasks import cache_user_permissions, invalidate_user_cache, get_cached_user_permissions

# Mixin pour ajouter des en-têtes anti-cache aux CBV (Class-Based Views)
class NoCacheMixin:
    """Mixin qui ajoute des en-têtes anti-cache à la réponse.

    Utilisation: Hériter ce mixin dans une Class-Based View (CBV) pour forcer
    le navigateur à ne pas mettre la page en cache. C'est utile pour les pages
    sensibles (connexion, pages post-authentification) afin d'éviter qu'elles
    restent visibles via le bouton "Précédent" après déconnexion.

    Sortie: la même réponse HTTP que la CBV d'origine, mais avec les en-têtes:
    - Cache-Control: no-cache, no-store, must-revalidate
    - Pragma: no-cache
    - Expires: 0
    """
    def dispatch(self, *args, **kwargs):
        response = super().dispatch(*args, **kwargs)
        # Ajouter des en-têtes pour éviter la mise en cache
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response

# Décorateur pour ajouter des en-têtes anti-cache aux FBV (Function-Based Views)
def never_cache_view(view_func):
    """Décorateur qui ajoute des en-têtes anti-cache aux vues fonctionnelles.

    Utilisation: placer au-dessus d'une Function-Based View (FBV).
    Effet: modifie la réponse HTTP pour empêcher le cache navigateur, exactement
    comme le `NoCacheMixin`, mais pour les FBV.
    """
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
    """Déconnexion sécurisée de l'utilisateur.

    Accès: uniquement utilisateur connecté.
    Méthode: POST attendue. En GET, on redirige vers la page de connexion.
    Entrées: aucune donnée nécessaire.
    Effets de bord:
    - Met à jour des attributs utilisateur si disponibles (`is_online`,
      `date_derniere_connexion`).
    - Vide complètement la session côté serveur (`session.flush()`).
    - Déconnecte l'utilisateur (`logout`).
    - Supprime les cookies de session (custom `msrn_sessionid` et `sessionid`).
    Réponse: redirection HTTP vers `/connexion/` avec en-têtes anti-cache.
    """
    if request.method == 'POST':
        # Récupérer l'utilisateur avant la déconnexion
        if request.user.is_authenticated:
            user = request.user
            user_id = user.id  # Sauvegarder l'ID avant déconnexion
            
            # Mettre à jour le statut en ligne
            if hasattr(user, 'is_online'):
                user.is_online = False
            # Enregistrer la date de dernière connexion
            if hasattr(user, 'date_derniere_connexion'):
                user.date_derniere_connexion = timezone.now()
            user.save()
            
            # Invalider le cache utilisateur via Celery (async)
            try:
                invalidate_user_cache.delay(user_id)
            except Exception:
                # Celery non disponible, on continue
                pass
        
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

@login_required
@csrf_protect
@never_cache_view
def get_voice_prefs(request):
    """Récupère les préférences de voix de l'utilisateur.

    Accès: utilisateur connecté.
    Méthode: GET uniquement; sinon -> 405.
    Entrées: aucune.
    Effets de bord: crée un enregistrement `UserVoicePreference` par défaut si
    inexistant pour cet utilisateur (get_or_create).
    Sortie: JSON {enabled, lang, voiceName}.
    """
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
    """Met à jour les préférences de voix de l'utilisateur.

    Accès: utilisateur connecté.
    Méthode: POST uniquement; sinon -> 405.
    Entrées acceptées:
    - Form POST classique (request.POST) ou JSON (`Content-Type: application/json`).
    - Champs: `enabled` (bool), `lang` (str, ex: 'fr-FR'), `voiceName` (str).
    Sécurité/Validation simple:
    - `lang` tronqué à 16 caractères; `voiceName` à 128 caractères.
    Effets de bord: persiste/maj le modèle `UserVoicePreference` lié à l'user.
    Sortie: JSON {'status': 'ok'} ou JSON d'erreur 400.
    """
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
    """Page d'activation du compte via un token unique.

    Accès: anonyme (avant connexion).
    Méthodes:
    - GET: affiche le formulaire demandant email + mot de passe temporaire.
    - POST: vérifie que l'email et le mot de passe temporaire correspondent à
      l'utilisateur associé au `token`, puis redirige vers la création du
      mot de passe définitif (`confirm_password`).
    Entrées: `token` (paramètre d'URL), et en POST: `email`, `temp_password`.
    Contrôles: validité du token et statut d'activation du compte.
    Sorties:
    - HTML: `users/activation.html` avec le contexte utilisateur.
    - Redirect: vers `users:login` si expiré/déjà actif, ou `users:confirm_password`.
    Effets de bord: aucun changement persistant ici (juste validations).
    """
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
    """Choix du nouveau mot de passe après validation du token.

    Accès: anonyme (via lien d'activation).
    Méthodes:
    - GET: affiche le formulaire de saisie du nouveau mot de passe (x2).
    - POST: valide, enregistre le mot de passe, et active définitivement le compte.
    Entrées: `token` (URL), en POST: `new_password`, `confirm_password`.
    Règles: mots de passe identiques et respectent la politique de sécurité.
    Sorties:
    - HTML: `users/confirmer_activation.html` avec messages d'erreur si besoin.
    - Redirect: `users:login` si succès ou si token invalide/déjà actif.
    Effets de bord: `set_password`, `activate_account()` sur le modèle User.
    """
    from django.contrib.auth import password_validation
    
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
        
        # Valider le mot de passe avec les validateurs Django
        try:
            password_validation.validate_password(new_password, user)
        except ValidationError as errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'users/confirmer_activation.html', {'user': user})
        
        # Définit le nouveau mot de passe et active le compte
        user.set_password(new_password)
        # NE PAS définir password_changed_at lors de la première activation
        # pour éviter que PasswordAgeValidator bloque immédiatement
        user.activate_account()
        
        messages.success(request, "Votre compte a été activé avec succès ! Vous pouvez maintenant vous connecter.")
        return redirect('users:login')
    
    return render(request, 'users/confirmer_activation.html', {'user': user})


@never_cache_view
def login_view(request):
    """Page de connexion (authentification par email + mot de passe).

    Accès: anonyme. Si déjà connecté, redirige vers `core:accueil`.
    Méthodes:
    - GET: affiche la page `users/connexion.html` (avec anti-cache renforcé).
    - POST: tente d'authentifier via `authenticate(username=email, password=...)`.
    Protection: django-axes vérifie automatiquement les tentatives échouées et
    verrouille après 10 tentatives pendant 30 minutes.
    Succès:
    - Vide l'ancienne session, connecte l'utilisateur, régénère la clé de session
      (sécurité), ajoute un message de bienvenue et redirige vers `next` ou
      `core:accueil`.
    Échec:
    - Affiche des messages d'erreur (compte inactif, identifiants invalides, verrouillage).
    Sorties: HTML (GET) ou Redirect (POST). En-têtes anti-cache ajoutés dans
    tous les cas pour éviter l'historique de pages sensibles.
    """
    from axes.handlers.proxy import AxesProxyHandler
    from axes.models import AccessAttempt
    from django.conf import settings
    from datetime import timedelta
    
    # Récupérer la limite de tentatives depuis settings
    max_attempts = getattr(settings, 'AXES_FAILURE_LIMIT', 4)
    cooloff_setting = getattr(settings, 'AXES_COOLOFF_TIME', timedelta(minutes=30))
    # Convertir en minutes (gérer timedelta ou entier)
    if isinstance(cooloff_setting, timedelta):
        cooloff_time = int(cooloff_setting.total_seconds() // 60)
    else:
        cooloff_time = cooloff_setting // 60
    
    if request.user.is_authenticated:
        return redirect('core:accueil')
    
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password')
        ip_address = request.META.get('REMOTE_ADDR', '')
        
        # Vérifier si le compte est verrouillé par django-axes
        if AxesProxyHandler.is_locked(request, credentials={'username': email}):
            messages.error(
                request,
                f"🔒 Votre compte a été temporairement verrouillé pour des raisons de sécurité "
                f"en raison d'un trop grand nombre de tentatives de connexion échouées ({max_attempts} tentatives maximum). "
                f"Veuillez réessayer dans {cooloff_time} minutes ou contacter un administrateur."
            )
            response = render(request, 'users/connexion.html')
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
            return response
        
        # Fonction helper pour obtenir le nombre de tentatives échouées
        def get_failed_attempts_count():
            """Récupère le nombre de tentatives échouées pour cet email/IP."""
            try:
                # Chercher par username (email) ou par IP
                attempt = AccessAttempt.objects.filter(
                    username=email
                ).first()
                if attempt:
                    return attempt.failures_since_start
                # Si pas trouvé par email, chercher par IP
                attempt = AccessAttempt.objects.filter(
                    ip_address=ip_address
                ).first()
                if attempt:
                    return attempt.failures_since_start
            except Exception:
                pass
            return 0
        
        # Vérifier d'abord si l'utilisateur existe en base de données
        try:
            existing_user = User.objects.get(email=email)
            
            # Vérifier si le compte est désactivé AVANT l'authentification
            if not existing_user.is_active:
                # Compte désactivé - afficher un message spécifique selon la raison
                if hasattr(existing_user, 'deactivation_reason') and existing_user.deactivation_reason:
                    if 'inactivité' in existing_user.deactivation_reason.lower():
                        messages.error(
                            request, 
                            "Votre compte a été verrouillé pour cause d'inactivité. "
                            "Veuillez contacter un administrateur (superuser) pour le réactiver."
                        )
                    elif 'manuelle' in existing_user.deactivation_reason.lower():
                        messages.error(
                            request, 
                            "Votre compte a été désactivé par un administrateur. "
                            "Veuillez contacter un administrateur pour plus d'informations."
                        )
                    else:
                        messages.error(
                            request, 
                            f"Votre compte a été désactivé. Raison: {existing_user.deactivation_reason}. "
                            "Veuillez contacter un administrateur."
                        )
                else:
                    messages.error(request, "Votre compte n'est pas encore activé. Veuillez vérifier votre email.")
            else:
                # Compte actif - tenter l'authentification
                user = authenticate(request, username=email, password=password)
                
                if user is not None:
                    # Vider l'ancienne session si elle existe
                    request.session.flush()
                    
                    # Connecter l'utilisateur (crée une nouvelle session)
                    login(request, user)
                    
                    # Régénérer la clé de session pour sécurité
                    request.session.cycle_key()
                    
                    # Cache les permissions utilisateur via Celery (async)
                    try:
                        cache_user_permissions.delay(user.id)
                    except Exception:
                        # Celery non disponible, on continue sans cache
                        pass
                    
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
                    # Mot de passe incorrect - afficher le nombre de tentatives restantes
                    failed_count = get_failed_attempts_count() + 1  # +1 car cette tentative vient d'échouer
                    remaining = max_attempts - failed_count
                    
                    if remaining > 0:
                        messages.error(
                            request, 
                            f"⚠️ Email ou mot de passe incorrect. "
                            f"Il vous reste {remaining} tentative(s) avant le verrouillage du compte."
                        )
                    else:
                        messages.error(
                            request,
                            f"🔒 Votre compte a été verrouillé après {max_attempts} tentatives échouées. "
                            f"Veuillez réessayer dans {cooloff_time} minutes ou contacter un administrateur."
                        )
                    
        except User.DoesNotExist:
            # Email n'existe pas - afficher le nombre de tentatives restantes
            failed_count = get_failed_attempts_count() + 1
            remaining = max_attempts - failed_count
            
            if remaining > 0:
                messages.error(
                    request, 
                    f"⚠️ Email ou mot de passe incorrect. "
                    f"Il vous reste {remaining} tentative(s) avant le verrouillage du compte."
                )
            else:
                messages.error(
                    request,
                    f"🔒 Votre compte a été verrouillé après {max_attempts} tentatives échouées. "
                    f"Veuillez réessayer dans {cooloff_time} minutes ou contacter un administrateur."
                )
    
    # Ajouter anti-cache à la page de connexion aussi
    response = render(request, 'users/connexion.html')
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


@login_required
def change_password_view(request):
    """
    Vue pour changer le mot de passe d'un utilisateur connecté.
    
    GET: Affiche le formulaire de changement de mot de passe.
    POST: Valide et change le mot de passe avec les nouvelles règles de sécurité.
    """
    from .forms import ChangePasswordForm
    
    if request.method == 'POST':
        form = ChangePasswordForm(request.user, request.POST)
        
        if form.is_valid():
            # Le formulaire valide déjà le mot de passe avec les validateurs
            form.save()
            
            # Forcer la reconnexion avec le nouveau mot de passe
            update_session_auth_hash(request, request.user)
            
            messages.success(request, "Votre mot de passe a été changé avec succès.")
            return redirect('core:accueil')
        else:
            # Afficher les erreurs du formulaire
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, error)
    else:
        form = ChangePasswordForm(request.user)
    
    return render(request, 'users/changement_password.html', {'form': form})
