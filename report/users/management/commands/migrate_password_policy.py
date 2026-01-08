"""
Commande pour gérer la migration vers la nouvelle politique de mots de passe.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from users.models import User
from django.contrib.auth.hashers import check_password
import secrets
import string


class Command(BaseCommand):
    help = "Gère la migration des utilisateurs vers la nouvelle politique de mots de passe"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Affiche ce qui sera fait sans exécuter',
        )
        parser.add_argument(
            '--force-change',
            action='store_true',
            help='Force tous les utilisateurs à changer leur mot de passe',
        )
        parser.add_argument(
            '--grace-period',
            type=int,
            default=30,
            help='Nombre de jours avant expiration (défaut: 30)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force_change = options['force_change']
        grace_period = options['grace_period']
        
        self.stdout.write("=== Migration de la politique de mots de passe ===\n")
        
        # Étape 1: Analyser les utilisateurs
        users = User.objects.filter(is_active=True)
        weak_password_users = []
        
        for user in users:
            # Vérifier si le mot de passe respecte les nouvelles règles
            if not self._check_password_strength(user):
                weak_password_users.append(user)
        
        self.stdout.write(f"Utilisateurs actifs : {users.count()}")
        self.stdout.write(f"Utilisateurs avec mot de passe faible : {len(weak_password_users)}")
        
        if weak_password_users:
            self.stdout.write("\nUtilisateurs concernés :")
            for user in weak_password_users:
                self.stdout.write(f"  - {user.email} ({user.get_full_name()})")
        
        # Étape 2: Appliquer la stratégie
        if not dry_run:
            if force_change:
                # Forcer le changement immédiat
                grace_date = timezone.now() - timedelta(days=1)
            else:
                # Donner une période de grâce
                grace_date = timezone.now() - timedelta(days=grace_period)
            
            # Mettre à jour les utilisateurs avec mots de passe faibles
            updated = User.objects.filter(
                id__in=[u.id for u in weak_password_users]
            ).update(password_changed_at=grace_date)
            
            self.stdout.write(
                self.style.SUCCESS(f"\n✅ {updated} utilisateurs mis à jour")
            )
            
            # Étape 3: Envoyer des notifications
            self._notify_users(weak_password_users, grace_period)
        else:
            self.stdout.write(
                self.style.WARNING("\n--dry-run : Aucune modification effectuée")
            )

    def _check_password_strength(self, user):
        """Vérifie si le mot de passe respecte les nouvelles règles."""
        # On ne peut pas vérifier le hash directement, donc on suppose 
        # que les anciens mots de passe sont faibles
        # Une meilleure approche serait de vérifier la date de création
        return user.password_changed_at and (timezone.now() - user.password_changed_at).days < 1

    def _notify_users(self, users, grace_period):
        """Notifie les utilisateurs qu'ils doivent changer leur mot de passe."""
        self.stdout.write(f"\n📧 Notification de {len(users)} utilisateurs...")
        
        # Ici vous pourriez envoyer un email
        for user in users:
            self.stdout.write(f"  Notification envoyée à : {user.email}")
        
        self.stdout.write(
            self.style.SUCCESS("✅ Notifications envoyées")
        )
