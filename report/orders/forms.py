from django import forms
from .models import FichierImporte


class UploadFichierForm(forms.ModelForm):
    """
    Formulaire simple pour permettre l’upload d’un fichier
    (ne conserve que le champ 'fichier').
    """

    class Meta:
        model = FichierImporte
        fields = ['fichier']
        labels = {
            'fichier': 'File',
        }
        help_texts = {
            'fichier': 'Choisissez n’importe quel fichier pour importer.',
        }
