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
        from decimal import Decimal
        from django.db.models import Q
        from orders.models import NumeroBonCommande

        services_list = request.user.get_services_list() if hasattr(request.user, 'get_services_list') else []

        if request.user.is_superuser:
            accessible_bons = NumeroBonCommande.objects.all()
            display_services = ['NWG', 'FAC', 'ITS']
        else:
            if services_list:
                query = Q()
                for s in services_list:
                    query |= Q(cpu__iexact=s)
                accessible_bons = NumeroBonCommande.objects.filter(query)
                display_services = services_list
            else:
                accessible_bons = NumeroBonCommande.objects.none()
                display_services = []

        po_counts_by_service = []
        for s in display_services:
            bons_for_service = accessible_bons.filter(cpu__iexact=s)
            count = bons_for_service.count()
            total_amount = Decimal('0')
            delivered_amount = Decimal('0')
            for bon in bons_for_service:
                try:
                    total_amount += bon.montant_total()
                    delivered_amount += bon.montant_recu()
                except Exception:
                    continue
            po_counts_by_service.append({
                'service': s,
                'count': count,
                'total_amount': total_amount,
                'delivered_amount': delivered_amount,
            })

        context = {
            'po_counts_by_service': po_counts_by_service,
        }
        return render(request, self.template_name, context)
