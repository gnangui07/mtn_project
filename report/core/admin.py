"""Configuration de l'interface d'administration pour l'app `core`.

Ce fichier est l'endroit où enregistrer les modèles pour qu'ils soient
visibles et gérables depuis le site d'administration Django.

Exemple d'enregistrement avec configuration personnalisée:

```python
from .models import MonModele

@admin.register(MonModele)
class MonModeleAdmin(admin.ModelAdmin):
    list_display = ("id", "nom", "date_creation")
    search_fields = ("nom",)
    list_filter = ("date_creation",)
```

Pour le moment, l'app `core` ne définit pas de modèles à exposer dans l'admin.
"""

from django.contrib import admin

# Aucun modèle de `core` n'est enregistré pour l'instant.
