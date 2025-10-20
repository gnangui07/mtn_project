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


class UserAdminForm(forms.ModelForm):
    """Formulaire personnalisé pour l'admin avec sélection multiple des services"""
    
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
        
        # Pré-remplir les services sélectionnés si l'utilisateur existe
        if self.instance and self.instance.pk and self.instance.service:
            # Convertir la chaîne "NWG, ITS" en liste ['NWG', 'ITS']
            selected_services = [s.strip().upper() for s in self.instance.service.split(',') if s.strip()]
            self.fields['services'].initial = selected_services
    
    def clean(self):
        """Validation : services obligatoires pour les utilisateurs non-superusers"""
        cleaned_data = super().clean()
        is_superuser = cleaned_data.get('is_superuser', False)
        services = cleaned_data.get('services', [])
        
        if not is_superuser and not services:
            raise forms.ValidationError(
                'Au moins un service doit être sélectionné pour les utilisateurs standards.'
            )
        
        return cleaned_data
    
    def save(self, commit=True):
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
    """Administration personnalisée pour le modèle User"""
    
    form = UserAdminForm
    
    list_display = ['email', 'first_name', 'last_name', 'service', 'is_active', 'activation_status', 'date_joined']
    list_filter = ['is_active', 'is_staff', 'service', 'date_joined']
    search_fields = ['email', 'first_name', 'last_name', 'service']
    ordering = ['-date_joined']
    
    fieldsets = (
        ('Informations de base', {
            'fields': ('email', 'first_name', 'last_name', 'phone', 'services')
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ('collapse',)
        }),
        ('Informations d\'activation', {
            'fields': ('activation_token', 'token_created_at', 'temporary_password'),
            'classes': ('collapse',)
        }),
        ('Dates', {
            'fields': ('last_login', 'date_joined'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['date_joined', 'last_login', 'activation_token', 'token_created_at', 'temporary_password']
    
    def activation_status(self, obj):
        """Affiche le statut d'activation avec icône"""
        if obj.is_active:
            return format_html('<span style="color: green;">✓ Activé</span>')
        elif obj.activation_token:
            return format_html('<span style="color: orange;">⏳ En attente</span>')
        else:
            return format_html('<span style="color: red;">✗ Non activé</span>')
    activation_status.short_description = 'Statut'
    
    def save_model(self, request, obj, form, change):
        """Surcharge pour envoyer l'email d'activation lors de la création"""
        is_new = obj.pk is None
        
        if is_new:
            # Génère le mot de passe temporaire et le token
            temp_password = obj.generate_temporary_password()
            obj.generate_activation_token()
            
            # Sauvegarde l'utilisateur sans appeler full_clean() car le formulaire a déjà validé
            obj.save()
            
            # Envoie l'email d'activation
            self.send_activation_email(obj, temp_password, request)
            
            # Message de succès
            self.message_user(
                request,
                f"Utilisateur créé avec succès. Email d'activation envoyé à {obj.email}",
                level='success'
            )
        else:
            # Pour les modifications, sauvegarder directement
            obj.save()
    
    def send_activation_email(self, user, temp_password, request):
        """Envoie l'email d'activation à l'utilisateur"""
        try:
            # Construction du lien d'activation avec SITE_URL
            activation_path = reverse('users:activate', kwargs={'token': user.activation_token})
            activation_url = f"{settings.SITE_URL}{activation_path}"
            
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
                            <li>Vous devrez créer un nouveau mot de passe sécurisé lors de l'activation</li>
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
