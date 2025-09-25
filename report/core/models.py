"""Modèles de l'application `core`.

Cette app ne définit pas de modèles pour le moment. Si vous ajoutez des
modèles à l'avenir, suivez les bonnes pratiques ci-dessous :

- Ajoutez une docstring de classe décrivant le rôle du modèle.
- Définissez __str__ pour un affichage lisible dans l'admin.
- Utilisez des verbose_name et verbose_name_plural dans Meta.
- Documentez les relations (ForeignKey, ManyToMany) avec des commentaires.

Exemple minimal::

    from django.db import models

    class Exemple(models.Model):
        "Représente un exemple minimal avec un nom et une date."

        nom = models.CharField(max_length=255, help_text="Nom lisible affiché à l'utilisateur")
        cree_le = models.DateTimeField(auto_now_add=True)

        class Meta:
            verbose_name = "Exemple"
            verbose_name_plural = "Exemples"
            ordering = ("-cree_le",)

        def __str__(self) -> str:
            return self.nom
"""

from django.db import models

# Aucun modèle défini pour l'instant.
