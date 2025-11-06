"""But:
- Fournir un formulaire très simple pour téléverser un fichier.

Étapes:
- Afficher un champ unique pour choisir le fichier.
- Valider et sauvegarder via le modèle lié.

Entrées:
- Fichier sélectionné par l'utilisateur via le champ `fichier`.

Sorties:
- Instance `FichierImporte` créée/validée avec le fichier stocké.
"""
from django import forms
from .models import FichierImporte


class UploadFichierForm(forms.ModelForm):
    """But:
    - Permettre l’upload d’un seul fichier.

    Étapes:
    - Afficher un champ.
    - Vérifier et sauvegarder.

    Entrées:
    - `fichier`: fichier à importer.

    Sorties:
    - Form valide avec un objet `FichierImporte` prêt à sauvegarder.
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
        # Champ unique: on ne demande rien d'autre
        # L'enregistrement réel est géré par la vue qui appelle `form.save()`
