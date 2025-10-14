from django.urls import path
from . import analytics_api

urlpatterns = [
    path('', analytics_api.get_analytics_data, name='get_analytics_data'),
    # Route heatmap supprimée (carte thermique retirée)
]
