"""
Formulaires de l'application `users`.

Définit les formulaires d'inscription, de modification et d'authentification
personnalisés pour `CustomUser`.
"""
 
from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm, AuthenticationForm
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from .models import CustomUser

class CustomUserCreationForm(UserCreationForm):
    """Formulaire pour la création d'un utilisateur personnalisé"""
    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'first_name', 'last_name', 'service')

class CustomUserChangeForm(UserChangeForm):
    """Formulaire pour la modification d'un utilisateur personnalisé"""
    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'first_name', 'last_name', 'service')

class FormulaireConnexion(AuthenticationForm):
    """Formulaire de connexion personnalisé"""
    username = forms.CharField(label="Nom d'utilisateur", widget=forms.TextInput(attrs={'class': 'form-control'}))
    password = forms.CharField(label="Mot de passe", widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    
    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')
        
        if username and password:
            # Tenter d'authentifier l'utilisateur
            self.user_cache = authenticate(self.request, username=username, password=password)
            
            # Si l'authentification a échoué
            if self.user_cache is None:
                # Vérifier si l'utilisateur existe mais est désactivé
                from django.contrib.auth import get_user_model
                UserModel = get_user_model()
                try:
                    user = UserModel.objects.get(username=username)
                    if not user.is_active:
                        raise ValidationError(
                            "Ce compte a été désactivé. Veuillez contacter l'administrateur pour plus d'informations.",
                            code='inactive',
                        )
                except UserModel.DoesNotExist:
                    # Laisser le message d'erreur standard pour les utilisateurs inexistants
                    pass
                
                # Message d'erreur standard pour les autres cas
                raise ValidationError(
                    self.error_messages['invalid_login'],
                    code='invalid_login',
                    params={'username': self.username_field.verbose_name},
                )
            else:
                self.confirm_login_allowed(self.user_cache)
                
        return self.cleaned_data
