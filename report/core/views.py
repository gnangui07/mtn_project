"""
Vues de l'application `core`.

Ce module contient :
- RedirectionAccueilView: redirige vers la page d'accueil si l'utilisateur est authentifié,
  sinon vers la page de connexion.
- AccueilView: affiche la page d'accueil (protégée), avec un mixin pour empêcher le cache navigateur.

Ces vues sont volontairement simples pour servir de point d'entrée à l'application.
"""

from django.shortcuts import render, redirect
from django.views.generic import View
from django.contrib.auth.mixins import LoginRequiredMixin

# Mixin défini dans `users.views` qui ajoute des en-têtes anti-cache
from users.views import NoCacheMixin


class RedirectionAccueilView(View):
    """Redirige l'utilisateur selon son état d'authentification.

    - Si l'utilisateur est connecté, on l'envoie vers `core:accueil`.
    - Sinon, on le redirige vers la page `connexion`.
    """

    def get(self, request):
        # Vérifie l'authentification et redirige en conséquence
        if request.user.is_authenticated:
            return redirect('core:accueil')
        else:
            return redirect('connexion')


class AccueilView(LoginRequiredMixin, NoCacheMixin, View):
    """Affiche la page d'accueil de l'application.

    Hérite de:
    - LoginRequiredMixin: impose l'authentification.
    - NoCacheMixin: empêche le cache navigateur pour éviter d'afficher une page périmée
      après déconnexion/reconnexion.
    """

    # Template rendu pour la page d'accueil
    template_name = 'core/accueil.html'
    # Redirige explicitement vers la page de connexion si non authentifié
    login_url = '/connexion/'

    def get(self, request):
        """Retourne le contenu HTML de la page d'accueil.

        Aucun contexte spécifique n'est requis pour le moment, mais on peut
        enrichir le contexte plus tard (ex: statistiques rapides, raccourcis, etc.).
        """
        return render(request, self.template_name)
