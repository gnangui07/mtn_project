"""
But:
- Définir les routes (URLs) pour l'API d'analytics de l'app orders.

Entrées:
- Aucune entrée directe ici (les vues sont dans analytics_api.py).

Sorties:
- Un motif d'URL: '' (racine du segment analytics) → get_analytics_data
"""
from django.urls import path
from . import analytics_api

urlpatterns = [
    path('', analytics_api.get_analytics_data, name='get_analytics_data'),
    # Route heatmap supprimée (carte thermique retirée)
]
