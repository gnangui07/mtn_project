from django.urls import path
from . import analytics_api

urlpatterns = [
    path('', analytics_api.get_analytics_data, name='get_analytics_data'),
    path('heatmap/', analytics_api.get_heatmap_data, name='get_heatmap_data'),
    
   
]
