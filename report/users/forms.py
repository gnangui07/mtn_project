"""
Formulaires pour l'application users.
"""
from django import forms
from django.contrib.auth.forms import PasswordChangeForm


class ChangePasswordForm(PasswordChangeForm):
    """
    Formulaire pour changer le mot de passe avec les nouvelles règles de sécurité.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Personnaliser les champs
        self.fields['old_password'].widget = forms.PasswordInput(
            attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Entrez votre ancien mot de passe',
                'id': 'id_old_password'
            }
        )
        
        self.fields['new_password1'].widget = forms.PasswordInput(
            attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Entrez le nouveau mot de passe',
                'id': 'id_new_password1'
            }
        )
        
        self.fields['new_password2'].widget = forms.PasswordInput(
            attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Confirmez le nouveau mot de passe',
                'id': 'id_new_password2'
            }
        )
        
        # Renommer les champs pour le template
        self.fields['new_password1'].label = "Nouveau mot de passe"
        self.fields['new_password2'].label = "Confirmer le nouveau mot de passe"


from django.contrib.auth.forms import PasswordResetForm
from django.core.mail import EmailMultiAlternatives
from django.template import loader
from django.utils.translation import gettext_lazy as _

class CustomPasswordResetForm(PasswordResetForm):
    """
    Formulaire de réinitialisation personnalisé pour ajouter des CC.
    """
    def save(self, domain_override=None,
             subject_template_name='registration/password_reset_subject.txt',
             email_template_name='registration/password_reset_email.html',
             use_https=False, token_generator=None,
             from_email=None, request=None, html_email_template_name=None,
             extra_email_context=None):
        """
        Surcharge de la méthode save pour forcer l'usage du domaine de la requête.
        Inspire de la logique d'activation dans admin.py.
        """
        if not domain_override and request:
            # Récupérer l'hôte depuis la requête (ex: 192.168.8.118:8000)
            # comme fait dans users/admin.py pour l'activation
            domain_override = request.get_host()
            
        return super().save(
            domain_override=domain_override,
            subject_template_name=subject_template_name,
            email_template_name=email_template_name,
            use_https=use_https,
            token_generator=token_generator,
            from_email=from_email,
            request=request,
            html_email_template_name=html_email_template_name,
            extra_email_context=extra_email_context
        )

    def send_mail(self, subject_template_name, email_template_name,
                  context, from_email, to_email, html_email_template_name=None):
        """
        Envoie un EmailMultiAlternatives à `to_email` avec un CC.
        """
        subject = loader.render_to_string(subject_template_name, context)
        # Email subject *must not* contain newlines
        subject = ''.join(subject.splitlines())
        body = loader.render_to_string(email_template_name, context)

        # Ajouter le CC
        cc_list = ['aimegnangui02@gmail.com']
        
        email_message = EmailMultiAlternatives(subject, body, from_email, [to_email], cc=cc_list)
        if html_email_template_name:
            html_email = loader.render_to_string(html_email_template_name, context)
            email_message.attach_alternative(html_email, 'text/html')

        email_message.send()