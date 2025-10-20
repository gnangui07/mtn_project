"""
URL configuration for reports project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from users import views as user_views

# Pas d'espace de noms pour les URLs principales

urlpatterns = [
    path('admin/', admin.site.urls),
    # Application existante (sera progressivement dépréciée)
    
    # Nouvelles applications
    path('', include('core.urls')),  # Application principale pour les fonctionnalités de base
    path('users/', include('users.urls')),  # Gestion des utilisateurs
    
    path('orders/', include('orders.urls')),  # Gestion des bons de commande
    
    # URL de connexion directe à la racine (redirection vers users:login)
    path('connexion/', user_views.login_view, name='connexion'),
    
    # URL de déconnexion directe à la racine
    path('deconnexion/', user_views.deconnexion_view, name='deconnexion')
]

# Favicon to avoid 404s (point to existing static logo as fallback)
urlpatterns += [
    re_path(r'^favicon\.ico$', RedirectView.as_view(url='/static/logo_mtn.jpeg', permanent=False)),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
