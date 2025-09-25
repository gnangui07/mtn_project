"""Tests pour l'application `core`.

Bonnes pratiques:
- Nommer les classes de tests `Test...` et les méthodes `test_...`.
- Isoler les cas de test, éviter les dépendances entre eux.
- Utiliser setUp()/tearDown() pour préparer/ nettoyer les données.
"""

from django.test import TestCase


class TestAccueilView(TestCase):
    """Exemples de tests basiques pour la vue d'accueil.

    Remplacez/complétez ces exemples selon vos besoins.
    """

    def test_redirection_si_non_authentifie(self):
        """Un utilisateur anonyme doit être redirigé vers la page de connexion."""
        response = self.client.get("/accueil/", follow=False)
        # 302 attendu car LoginRequiredMixin redirige
        self.assertEqual(response.status_code, 302)

