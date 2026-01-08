"""
Admin Django pour l'application `users`.

Contient les formulaires et personnalisations d'admin pour créer/éditer des
utilisateurs (`CustomUser`) avec génération de username et token d'activation.
"""
 
from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html, mark_safe
from django.urls import reverse
from django.contrib import messages
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
from django.core.mail import send_mail
import random
import string
import unicodedata
from .models import User

# Import de la tâche Celery pour l'envoi asynchrone d'emails
try:
    from .tasks import send_activation_email_task
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False


class UserAdminForm(forms.ModelForm):
    """Formulaire admin pour créer/éditer un utilisateur avec choix de services.

    Objectif:
    - L'admin montre une case à cocher par service (MultipleChoiceField) plutôt
      que d'éditer directement la chaîne `service` du modèle.
    - À l'enregistrement, on reconstruit la chaîne `service` ("NWG, ITS, ...").

    Remarque: le champ `service` du modèle est exclu du formulaire et remplacé
    par le champ virtuel `services` (liste), plus simple à utiliser.
    """
    
    services = forms.MultipleChoiceField(
        choices=User.SERVICE_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Services autorisés",
        help_text="Sélectionnez un ou plusieurs services. Laissez vide pour les superusers."
    )
    
    class Meta:
        model = User
        exclude = ['service']  # Exclure complètement le champ service
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Préparer le formulaire à l'édition d'un utilisateur existant
        # Pré-remplir les services sélectionnés si l'utilisateur existe
        if self.instance and self.instance.pk and self.instance.service:
            # Convertir la chaîne "NWG, ITS" en liste ['NWG', 'ITS']
            selected_services = [s.strip().upper() for s in self.instance.service.split(',') if s.strip()]
            self.fields['services'].initial = selected_services
    
    def clean(self):
        """Validation simple des services.

        Règle:
        - Pour un utilisateur standard (non superuser), au moins un service
          doit être coché. Les superusers peuvent laisser vide.
        """
        cleaned_data = super().clean()
        is_superuser = cleaned_data.get('is_superuser', False)
        services = cleaned_data.get('services', [])
        
        if not is_superuser and not services:
            raise forms.ValidationError(
                'Au moins un service doit être sélectionné pour les utilisateurs standards.'
            )
        
        return cleaned_data
    
    def save(self, commit=True):
        """Enregistre l'utilisateur en mappant les services cochés vers `service`.

        Détails:
        - Le champ `service` du modèle est une chaîne. On convertit la liste
          `services` du formulaire en une chaîne jointe par virgules.
        - On sauvegarde ensuite l'utilisateur; `save_m2m()` gère les relations
          ManyToMany (ex: permissions, groupes) si présentes.
        """
        # Ne pas appeler super().save() tout de suite car le champ service est exclu
        user = super().save(commit=False)
        
        # Convertir la liste de services sélectionnés en chaîne "NWG, ITS, FAC"
        selected_services = self.cleaned_data.get('services', [])
        if selected_services:
            user.service = ', '.join(selected_services)
        else:
            user.service = ''
        
        if commit:
            # Utiliser save() avec validate=False pour éviter la validation du modèle
            # car le formulaire a déjà validé les services
            user.save(update_fields=None if user.pk else None)
            self.save_m2m()  # Sauvegarder les relations many-to-many
        
        return user


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    """Configuration de l'administration pour le modèle `User`.

    Ce panneau permet de lister, filtrer, rechercher et éditer les utilisateurs.
    Les sections ci-dessous décrivent ce qui est affiché et comment l'activation
    est gérée lors de la création d'un compte.
    """
    
    form = UserAdminForm
    
    # Colonnes visibles dans la liste des utilisateurs
    list_display = ['email', 'first_name', 'last_name', 'service', 'is_active', 'activation_status', 'date_joined']
    # Filtres latéraux pour affiner l'affichage
    list_filter = ['is_active', 'is_staff', 'service', 'date_joined']
    # Champs indexés pour la recherche
    search_fields = ['email', 'first_name', 'last_name', 'service']
    # Tri par défaut: plus récents d'abord
    ordering = ['-date_joined']
    
    # Organisation du formulaire d'édition (onglets/sections)
    fieldsets = (
        ('Informations de base', {
            'fields': ('email', 'first_name', 'last_name', 'phone', 'services')
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ('collapse',)
        }),
        ("Informations d'activation", {
            'fields': ('activation_token', 'token_created_at', 'temporary_password'),
            'classes': ('collapse',)
        }),
        ('Dates', {
            'fields': ('last_login', 'date_joined'),
            'classes': ('collapse',)
        }),
    )
    
    # Champs non modifiables dans l'admin (lecture seule)
    readonly_fields = ['date_joined', 'last_login', 'activation_token', 'token_created_at', 'temporary_password']
    
    # Actions disponibles dans l'admin
    actions = ['resend_activation_token']
    
    def activation_status(self, obj):
        """Affiche le statut d'activation sous forme d'icône colorée.

        - Vert: compte activé (`is_active=True`).
        - Orange: en attente (token généré mais pas encore activé).
        - Rouge: token expiré (plus de 48h).
        - Gris: non activé (pas de token).
        """
        if obj.is_active:
            return mark_safe('<span style="color: green;">✓ Activé</span>')
        elif obj.activation_token:
            if obj.is_token_valid():
                return mark_safe('<span style="color: orange;">⏳ En attente</span>')
            else:
                return mark_safe('<span style="color: red;">⚠️ Expiré</span>')
        else:
            return mark_safe('<span style="color: gray;">✗ Non activé</span>')
    activation_status.short_description = 'Statut'
    
    def save_model(self, request, obj, form, change):
        """À la création d'un utilisateur, préparer l'activation et envoyer l'email.

        Création (obj.pk is None):
        - Génère un mot de passe temporaire (haché en base, le clair est envoyé par email).
        - Génère un token d'activation + horodatage.
        - Sauvegarde l'utilisateur puis envoie un email d'activation.

        Modification: sauvegarde simple, sans réémettre d'email.
        """
        is_new = obj.pk is None
        
        if is_new:
            # Génère le mot de passe temporaire et le token
            temp_password = obj.generate_temporary_password()
            obj.generate_activation_token()
            
            # Sauvegarde l'utilisateur sans appeler full_clean() car le formulaire a déjà validé
            obj.save()
            
            # Déterminer l'URL du site dynamiquement à partir de la requête
            # Cela permet d'avoir le bon IP:PORT (ex: 192.168.8.121:8000) même si l'IP change
            scheme = request.scheme
            host = request.get_host()
            site_url = f"{scheme}://{host}"
            
            # Envoie l'email d'activation (async si Celery disponible, sinon sync)
            if CELERY_AVAILABLE:
                try:
                    # Envoi asynchrone via Celery
                    send_activation_email_task.delay(obj.id, temp_password, site_url=site_url)
                    self.message_user(
                        request,
                        f"Utilisateur créé avec succès. Email d'activation en cours d'envoi à {obj.email}",
                        level='success'
                    )
                except Exception as e:
                    # Fallback: envoi synchrone si Celery échoue
                    self.send_activation_email(obj, temp_password, request, site_url)
                    self.message_user(
                        request,
                        f"Utilisateur créé avec succès. Email d'activation envoyé à {obj.email}",
                        level='success'
                    )
            else:
                # Envoi synchrone (Celery non disponible)
                self.send_activation_email(obj, temp_password, request, site_url)
                self.message_user(
                    request,
                    f"Utilisateur créé avec succès. Email d'activation envoyé à {obj.email}",
                    level='success'
                )
        else:
            # Pour les modifications, sauvegarder directement
            obj.save()
    
    def send_activation_email(self, user, temp_password, request, site_url=None):
        """Construit et envoie l'email d'activation au nouvel utilisateur.

        Contenu:
        - Lien d'activation absolu (basé sur `site_url` + reverse URL `users:activate`).
        - Sujet + version HTML (stylée) et texte brut (fallback).

        Résilience:
        - En cas d'erreur d'envoi, on log/print sans bloquer la création.
        """
        try:
            # Utiliser l'URL fournie ou celle par défaut des settings
            base_url = site_url or settings.SITE_URL
            
            # Construction du lien d'activation avec l'URL dynamique
            activation_path = reverse('users:activate', kwargs={'token': user.activation_token})
            activation_url = f"{base_url}{activation_path}"
            
            # Sujet de l'email
            subject = f"Activation de votre compte - {settings.SITE_NAME if hasattr(settings, 'SITE_NAME') else 'MTN CI'}"
            
            # Corps de l'email en HTML
            html_message = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background-color: #FFCC00; padding: 20px; text-align: center; }}
                    .content {{ background-color: #f9f9f9; padding: 30px; border-radius: 5px; }}
                    .credentials {{ background-color: #fff; padding: 15px; border-left: 4px solid #FFCC00; margin: 20px 0; }}
                    .requirements {{ background-color: #e9ecef; padding: 15px; margin: 20px 0; border-radius: 5px; }}
                    .button {{ display: inline-block; padding: 12px 30px; background-color: #FFCC00; color: #000; text-decoration: none; border-radius: 5px; font-weight: bold; }}
                    .footer {{ text-align: center; margin-top: 20px; font-size: 12px; color: #666; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1 style="margin: 0; color: #000;">Bienvenue !</h1>
                    </div>
                    <div class="content">
                        <p>Bonjour <strong>{user.first_name} {user.last_name}</strong>,</p>
                        
                        <p>Votre compte a été créé avec succès sur la plateforme CAPEX Works Valuation Tool de MTN Côte d'Ivoire.</p>
                        
                        <div class="credentials">
                            <p><strong>Vos identifiants temporaires :</strong></p>
                            <p>📧 <strong>Email :</strong> {user.email}</p>
                            <p>🔑 <strong>Mot de passe temporaire :</strong> {temp_password}</p>
                        </div>
                        
                        <div class="requirements">
                            <p><strong>🔐 Nouvelle politique de sécurité pour votre mot de passe :</strong></p>
                            <ul>
                                <li>✅ Au moins 12 caractères</li>
                                <li>✅ Au moins une lettre majuscule</li>
                                <li>✅ Au moins une lettre minuscule</li>
                                <li>✅ Au moins un chiffre</li>
                                <li>✅ Au moins un caractère spécial (* @ ! - _ /)</li>
                            </ul>
                        </div>
                        
                        <p>Pour activer votre compte, veuillez cliquer sur le bouton ci-dessous :</p>
                        
                        <p style="text-align: center; margin: 30px 0;">
                            <a href="{activation_url}" class="button">Activer mon compte</a>
                        </p>
                        
                        <p style="font-size: 12px; color: #666;">
                            Si le bouton ne fonctionne pas, copiez et collez ce lien dans votre navigateur :<br>
                            <a href="{activation_url}">{activation_url}</a>
                        </p>
                        
                        <p><strong>⚠️ Important :</strong></p>
                        <ul>
                            <li>Ce lien est valide pendant 48 heures</li>
                            <li>Vous devrez créer un nouveau mot de passe sécurisé selon les exigences ci-dessus</li>
                            <li>Ne partagez jamais vos identifiants</li>
                        </ul>
                    </div>
                    <div class="footer">
                        <p>© 2025 MTN Côte d'Ivoire - CAPEX Works Valuation Tool</p>
                        <p>Cet email a été envoyé automatiquement, merci de ne pas y répondre.</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # Corps de l'email en texte brut (fallback)
            plain_message = f"""
            Bonjour {user.first_name} {user.last_name},
            
            Votre compte a été créé avec succès sur la plateforme CAPEX Works Valuation Tool de MTN Côte d'Ivoire.
            
            Vos identifiants temporaires :
            Email : {user.email}
            Mot de passe temporaire : {temp_password}
            
            Pour activer votre compte, cliquez sur ce lien :
            {activation_url}
            
            Ce lien est valide pendant 48 heures.
            Vous devrez créer un nouveau mot de passe sécurisé lors de l'activation.
            
            © 2025 MTN Côte d'Ivoire
            """
            
            # Envoi de l'email
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=False,
            )
            
        except Exception as e:
            # Log l'erreur mais ne bloque pas la création
            print(f"Erreur lors de l'envoi de l'email : {str(e)}")
            # En production, utiliser un logger approprié
    
    def resend_activation_token(self, request, queryset):
        """Action admin pour renvoyer le token d'activation aux utilisateurs sélectionnés.
        
        Cette action permet de :
        - Régénérer un nouveau token d'activation pour les comptes non activés
        - Renvoyer l'email d'activation avec les nouveaux identifiants
        - Gérer les cas d'erreur (compte déjà activé, erreur d'envoi email)
        """
        success_count = 0
        error_count = 0
        already_active_count = 0
        
        # Déterminer l'URL du site dynamiquement
        scheme = request.scheme
        host = request.get_host()
        site_url = f"{scheme}://{host}"
        
        for user in queryset:
            try:
                # Vérifier si le compte est déjà activé
                if user.is_active:
                    already_active_count += 1
                    continue
                
                # Générer un nouveau mot de passe temporaire et token
                temp_password = user.generate_temporary_password()
                user.generate_activation_token()
                user.save()
                
                # Envoyer l'email d'activation
                if CELERY_AVAILABLE:
                    try:
                        # Envoi asynchrone via Celery
                        send_activation_email_task.delay(user.id, temp_password, site_url=site_url)
                        success_count += 1
                    except Exception:
                        # Fallback: envoi synchrone si Celery échoue
                        self.send_activation_email(user, temp_password, request, site_url)
                        success_count += 1
                else:
                    # Envoi synchrone (Celery non disponible)
                    self.send_activation_email(user, temp_password, request, site_url)
                    success_count += 1
                    
            except Exception as e:
                error_count += 1
                print(f"Erreur lors du renvoi du token pour {user.email}: {str(e)}")
        
        # Messages de retour à l'administrateur
        messages_list = []
        
        if success_count > 0:
            messages_list.append(f"{success_count} token(s) d'activation renvoyé(s) avec succès")
        
        if already_active_count > 0:
            messages_list.append(f"{already_active_count} compte(s) déjà activé(s) (ignoré(s))")
        
        if error_count > 0:
            messages_list.append(f"{error_count} erreur(s) lors de l'envoi")
        
        if messages_list:
            message = " | ".join(messages_list)
            if error_count > 0:
                self.message_user(request, message, level='warning')
            else:
                self.message_user(request, message, level='success')
        else:
            self.message_user(request, "Aucune action effectuée", level='info')
    
    resend_activation_token.short_description = "Renvoyer le token d'activation"
