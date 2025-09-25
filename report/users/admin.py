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
import random
import string
import unicodedata
from .models import CustomUser

# Formulaire personnalisé pour la création d'utilisateurs
class FormulaireCreationUtilisateur(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ('first_name', 'last_name', 'email', 'service')
        
    def save(self, commit=True):
        user = super().save(commit=False)
        
        # Générer le nom d'utilisateur à partir du nom et prénom
        if user.first_name and user.last_name:
            # Prendre la première lettre du prénom et le nom complet, sans espaces ni accents
            prenom = unicodedata.normalize('NFKD', user.first_name).encode('ASCII', 'ignore').decode('utf-8')
            nom = unicodedata.normalize('NFKD', user.last_name).encode('ASCII', 'ignore').decode('utf-8')
            username_base = f"{prenom[0].lower()}{nom.lower().replace(' ', '')}"
            
            # Vérifier si ce nom d'utilisateur existe déjà
            username = username_base
            counter = 1
            while CustomUser.objects.filter(username=username).exists():
                username = f"{username_base}{counter}"
                counter += 1
            
            user.username = username
        
        # Générer un token d'activation unique
        token = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
        # Générer un mot de passe temporaire plus court pour faciliter la saisie
        temp_password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
        
        # Définir le mot de passe temporaire et le token d'activation
        user.set_password(temp_password)
        user.jeton_activation = token
        user.mot_de_passe_temporaire = temp_password
        user.active_manuellement = False
        user.date_expiration_jeton = timezone.now() + timedelta(days=7)  # Expiration dans 7 jours
        
        if commit:
            user.save()
        return user

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    add_form = FormulaireCreationUtilisateur
    list_display = ['username', 'email', 'first_name', 'last_name', 'is_active', 'service', 'bouton_envoi_email', 'bouton_modification']
    list_filter = ['is_active', 'is_staff', 'is_superuser', 'service']
    search_fields = ['username', 'first_name', 'last_name', 'email']
    actions = ['generer_mot_de_passe_temporaire', 'activer_utilisateurs', 'desactiver_utilisateurs']
    
    # Rendre le champ username en lecture seule
    readonly_fields = ('username',)
    
    fieldsets = UserAdmin.fieldsets + (
        ('Informations supplémentaires', {'fields': ('service', 'jeton_activation', 'active_manuellement', 
                                                 'date_derniere_connexion', 'mot_de_passe_temporaire', 
                                                 'date_expiration_jeton', 'email_envoye')}),
    )
    
    # Pour la création de nouveaux utilisateurs - simplifié sans les champs de statut
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('first_name', 'last_name', 'email', 'service'),
        }),
    )
    
    def bouton_envoi_email(self, obj):
        """Affiche des boutons pour envoyer un email d'activation"""
        if not obj.active_manuellement:
            # Construire l'URL complète avec le domaine
            from django.contrib.sites.shortcuts import get_current_site
            from django.urls import reverse
            from django.http import HttpRequest
            
            # Créer une requête factice pour obtenir le site actuel
            request = HttpRequest()
            request.META['SERVER_NAME'] = '127.0.0.1'
            request.META['SERVER_PORT'] = '8000'
            current_site = get_current_site(request)
            
            # Construire l'URL complète
            activation_path = f"{reverse('users:activation')}?username={obj.username}"
            activation_url = f"http:// 192.168.8.129:8000{activation_path}"

            
            # Utiliser un nom générique pour l'administrateur dans le mailto
            admin_name = "Administrateur du système"
            
            # Préparer le sujet et le corps de l'email
            subject = "Activation de votre compte"
            body = f"""Bonjour {obj.first_name},

Votre compte a été créé avec succès.

Voici vos informations de connexion :

- Nom d'utilisateur : {obj.username}
- Mot de passe temporaire : {obj.mot_de_passe_temporaire}

Pour activer votre compte et définir votre mot de passe personnel, veuillez cliquer sur le lien suivant :

{activation_url}


Si le lien ci-dessus ne fonctionne pas, vous pouvez le copier et le coller dans votre navigateur.

Ce lien est valable pendant 7 jours. Après cette période, vous devrez demander un nouveau lien d'activation.

Cordialement,
{admin_name}"""
            
            # Créer un bouton pour l'envoi via serveur
            url_serveur = reverse('admin:users_customuser_change', args=[obj.id]) + '?envoyer_email=1'
            # Utiliser un lien direct plutôt qu'un onclick pour éviter les problèmes de sécurité JavaScript
            
            # Remplacer example.com par localhost:8000 dans le corps de l'email pour le lien mailto
            body_mailto = body.replace('http://example.com', 'http://localhost:8000')
            # Créer un bouton pour l'envoi via mailto
            mailto_link = f"mailto:{obj.email}?subject={subject}&body={body_mailto}"
            
            # Retourner les deux boutons
            return format_html(
                '<div style="display: flex; gap: 10px;">' +
                '<a class="button" href="{}" style="background-color: #28a745; color: white;">Envoyer via serveur</a>' +
                '<a class="button" href="{}" style="background-color: #007bff; color: white;">Ouvrir dans client email</a>' +
                '</div>',
                url_serveur, mailto_link
            )
        return "Compte activé"
    bouton_envoi_email.short_description = "Email d'activation"
    
    def bouton_modification(self, obj):
        """Affiche un bouton pour modifier les informations de l'utilisateur"""
        url = reverse('admin:users_customuser_change', args=[obj.id])
        return format_html('<a class="button" href="{}" style="background-color: #007bff; color: white;">Modifier</a>', url)
    bouton_modification.short_description = "Modifier"
    
    def generer_mot_de_passe_temporaire(self, request, queryset):
        """Action pour générer un mot de passe temporaire pour les utilisateurs sélectionnés"""
        # Vérifier que l'utilisateur est un superutilisateur
        if not request.user.is_superuser:
            messages.error(request, "Seuls les superutilisateurs peuvent générer des mots de passe temporaires.")
            return
            
        for user in queryset:
            # Générer un token d'activation aléatoire
            token = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
            # Générer un mot de passe temporaire plus court pour faciliter la saisie
            temp_password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
            
            # Mettre à jour l'utilisateur
            user.jeton_activation = token
            user.mot_de_passe_temporaire = temp_password
            user.active_manuellement = False
            user.date_expiration_jeton = timezone.now() + timedelta(days=7)  # Expiration dans 7 jours
            
            # Définir le mot de passe temporaire
            user.set_password(temp_password)
            user.save()
        
        messages.success(request, f"{queryset.count()} utilisateur(s) ont reçu un nouveau mot de passe temporaire.")
        
        # Journaliser cette action sensible
        from django.contrib.admin.models import LogEntry, CHANGE
        from django.contrib.contenttypes.models import ContentType
        
        for user in queryset:
            LogEntry.objects.log_action(
                user_id=request.user.id,
                content_type_id=ContentType.objects.get_for_model(user).pk,
                object_id=user.id,
                object_repr=str(user),
                action_flag=CHANGE,
                change_message=f"Mot de passe temporaire généré par {request.user.username}"
            )
    generer_mot_de_passe_temporaire.short_description = "Générer un mot de passe temporaire"
    
    def activer_utilisateurs(self, request, queryset):
        """Action pour activer les utilisateurs sélectionnés"""
        # Vérifier que l'utilisateur est un superutilisateur
        if not request.user.is_superuser:
            messages.error(request, "Seuls les superutilisateurs peuvent activer des utilisateurs.")
            return
            
        nombre_utilisateurs = queryset.update(is_active=True)
        message = f"{nombre_utilisateurs} utilisateur(s) ont été activés avec succès."
        self.message_user(request, message, messages.SUCCESS)
        
        # Journaliser cette action
        from django.contrib.admin.models import LogEntry, CHANGE
        from django.contrib.contenttypes.models import ContentType
        
        for user in queryset:
            LogEntry.objects.log_action(
                user_id=request.user.id,
                content_type_id=ContentType.objects.get_for_model(user).pk,
                object_id=user.id,
                object_repr=str(user),
                action_flag=CHANGE,
                change_message=f"Utilisateur activé par {request.user.username}"
            )
    activer_utilisateurs.short_description = "Activer les utilisateurs sélectionnés"
    
    def desactiver_utilisateurs(self, request, queryset):
        """Action pour désactiver les utilisateurs sélectionnés et fermer leurs sessions"""
        # Vérifier que l'utilisateur est un superutilisateur
        if not request.user.is_superuser:
            messages.error(request, "Seuls les superutilisateurs peuvent désactiver des utilisateurs.")
            return
            
        # Empêcher la désactivation de son propre compte
        if queryset.filter(id=request.user.id).exists():
            messages.error(request, "Vous ne pouvez pas désactiver votre propre compte.")
            return
            
        from django.contrib.sessions.models import Session
        
        # Récupérer les IDs des utilisateurs sélectionnés
        user_ids = list(queryset.values_list('id', flat=True))
        
        # Désactiver les utilisateurs
        nombre_utilisateurs = queryset.update(is_active=False)
        
        # Supprimer les sessions des utilisateurs désactivés
        sessions_supprimees = 0
        for session in Session.objects.all():
            try:
                session_data = session.get_decoded()
                if session_data.get('_auth_user_id') and int(session_data['_auth_user_id']) in user_ids:
                    session.delete()
                    sessions_supprimees += 1
            except Exception as e:
                # Ignorer les erreurs de décodage de session
                pass
        
        message = f"{nombre_utilisateurs} utilisateur(s) ont été désactivés avec succès. {sessions_supprimees} session(s) active(s) ont été fermées."
        self.message_user(request, message, messages.SUCCESS)
        
        # Journaliser cette action sensible
        from django.contrib.admin.models import LogEntry, CHANGE
        from django.contrib.contenttypes.models import ContentType
        
        for user in queryset:
            LogEntry.objects.log_action(
                user_id=request.user.id,
                content_type_id=ContentType.objects.get_for_model(user).pk,
                object_id=user.id,
                object_repr=str(user),
                action_flag=CHANGE,
                change_message=f"Utilisateur désactivé par {request.user.username}"
            )
    desactiver_utilisateurs.short_description = "Désactiver les utilisateurs sélectionnés"
    
    def change_view(self, request, object_id, form_url='', extra_context=None):
        """Surcharge de la méthode change_view pour gérer l'envoi d'emails d'activation"""
        # Vérifier si le paramètre d'envoi d'email est présent dans l'URL
        if 'envoyer_email' in request.GET:
            # Récupérer l'utilisateur
            obj = self.get_object(request, object_id)
            
            # Vérifier si l'utilisateur n'est pas encore activé manuellement
            if obj and not obj.active_manuellement:
                # Construire l'URL complète avec le domaine
                from django.contrib.sites.shortcuts import get_current_site
                from django.core.mail import send_mail
                
                # Obtenir le site actuel
                current_site = get_current_site(request)
                
                # Construire l'URL complète
                try:
                    activation_path = f"{reverse('users:activation')}?username={obj.username}"
                    # Utiliser localhost:8000 pour le développement
                    activation_url = f"http://localhost:8000{activation_path}"
                except Exception as e:
                    # En cas d'erreur avec reverse, utiliser un chemin direct
                    messages.warning(request, f"Erreur lors de la génération de l'URL d'activation: {e}. Utilisation d'un chemin direct.")
                    activation_url = f"http://localhost:8000/users/activation/?username={obj.username}"
                
                # Préparer le sujet et le corps de l'email
                subject = "Activation de votre compte"
                # Inclure le nom du superuser dans le corps du message
                admin_name = f"{request.user.first_name} {request.user.last_name}" if request.user.first_name else request.user.username
                body = f"""Bonjour {obj.first_name},

Votre compte a été créé avec succès.

Voici vos informations de connexion :

- Nom d'utilisateur : {obj.username}
- Mot de passe temporaire : {obj.mot_de_passe_temporaire}

Pour activer votre compte et définir votre mot de passe personnel, veuillez cliquer sur le lien suivant :

{activation_url}

---

Si le lien ci-dessus ne fonctionne pas, vous pouvez le copier et le coller dans votre navigateur.

Ce lien est valable pendant 7 jours. Après cette période, vous devrez demander un nouveau lien d'activation.

Cordialement,
{admin_name}
Administrateur du système"""
                
                try:
                    # Vérifier si l'utilisateur a une adresse email
                    if not request.user.email:
                        messages.error(request, "Vous n'avez pas d'adresse email configurée. Veuillez mettre à jour votre profil.")
                        return super().change_view(request, object_id, form_url, extra_context)
                        
                    # Utiliser l'email du superuser comme expéditeur
                    from_email = request.user.email
                    
                    # Informations de débogage
                    import sys
                    messages.info(request, f"Backend d'email utilisé: {settings.EMAIL_BACKEND}")
                    
                    # Envoyer l'email
                    send_mail(
                        subject=subject,
                        message=body,
                        from_email=from_email,
                        recipient_list=[obj.email],
                        fail_silently=False,
                    )
                    
                    # Marquer l'email comme envoyé
                    obj.email_envoye = True
                    obj.save(update_fields=['email_envoye'])
                    
                    # Afficher un message de succès
                    messages.success(request, f"Un email d'activation a été envoyé à {obj.email} depuis votre adresse email ({from_email}).")
                    messages.info(request, "L'email a été affiché dans la console du serveur ET enregistré dans le dossier 'sent_emails' à la racine du projet.")
                except Exception as e:
                    # Gérer les erreurs d'envoi d'email avec plus de détails
                    import traceback
                    error_details = traceback.format_exc()
                    messages.error(request, f"Erreur lors de l'envoi de l'email: {e}")
                    messages.error(request, f"Détails de l'erreur: {error_details[:500]}...")
        
        # Continuer avec le comportement normal de la vue
        return super().change_view(request, object_id, form_url, extra_context)
    
    def save_model(self, request, obj, form, change):
        # Si c'est un nouvel utilisateur (pas de changement)
        if not change:
            # Générer un nom d'utilisateur basé sur le prénom et le nom
            if not obj.username:
                base_username = f"{obj.first_name.lower()}_{obj.last_name.lower()}"
                username = base_username
                counter = 1
                # Vérifier si le nom d'utilisateur existe déjà
                while CustomUser.objects.filter(username=username).exists():
                    username = f"{base_username}{counter}"
                    counter += 1
                obj.username = username
            
            # Générer un mot de passe temporaire
            temp_password = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
            obj.mot_de_passe_temporaire = temp_password
            obj.set_password(temp_password)
            
            # Générer un jeton d'activation
            import uuid
            obj.jeton_activation = str(uuid.uuid4())
            
            # Définir la date d'expiration du jeton (7 jours)
            obj.date_expiration_jeton = timezone.now() + timedelta(days=7)
            
            # Afficher un message de succès
            message_html = f"""
            <div style="padding: 10px; background-color: #f8f9fa; border: 1px solid #ddd; border-radius: 5px; margin-bottom: 15px;">
                <h4 style="color: #28a745; margin-top: 0;">Utilisateur créé avec succès!</h4>
                <p><strong>Nom d'utilisateur:</strong> {obj.username}</p>
                <p><strong>Mot de passe temporaire:</strong> {obj.mot_de_passe_temporaire}</p>
                <p style="margin-bottom: 0;">Utilisez le bouton 'Envoyer email d'activation' pour envoyer les informations d'activation à l'utilisateur.</p>
            </div>
            """
            messages.success(request, mark_safe(message_html))
        
        super().save_model(request, obj, form, change)
    