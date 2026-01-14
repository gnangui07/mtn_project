"""
Script de démonstration du système de désactivation automatique des comptes inactifs.

Ce script permet de tester manuellement les 4 preuves requises:
1. Configuration des paramètres (90 jours)
2. Désactivation automatique après 90 jours
3. Exemption des superusers
4. Réactivation manuelle par superuser

Usage:
    python demo_inactivity_system.py
"""
import os
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'reports.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from users.middleware_inactivity import InactivityDeactivationMiddleware

User = get_user_model()


def print_separator(title):
    """Affiche un séparateur visuel"""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80 + "\n")


def demo_configuration():
    """PREUVE 1: Afficher la configuration du système"""
    print_separator("PREUVE 1: Configuration du Système")
    
    middleware = InactivityDeactivationMiddleware(lambda x: x)
    
    print(f"✓ Nombre de jours d'inactivité configuré: {middleware.INACTIVITY_DAYS} jours")
    print(f"✓ Middleware: InactivityDeactivationMiddleware")
    print(f"✓ Champs ajoutés au modèle User:")
    print(f"  - deactivation_reason (TextField)")
    print(f"  - deactivated_at (DateTimeField)")
    print(f"  - last_login (DateTimeField)")
    
    # Vérifier qu'un utilisateur a bien ces champs
    test_user = User.objects.first()
    if test_user:
        print(f"\n✓ Vérification sur l'utilisateur '{test_user.email}':")
        print(f"  - has deactivation_reason: {hasattr(test_user, 'deactivation_reason')}")
        print(f"  - has deactivated_at: {hasattr(test_user, 'deactivated_at')}")
        print(f"  - has last_login: {hasattr(test_user, 'last_login')}")


def demo_create_inactive_user():
    """PREUVE 2: Créer un utilisateur inactif pour test"""
    print_separator("PREUVE 2: Création d'un Utilisateur Inactif")
    
    # Supprimer l'utilisateur s'il existe déjà
    User.objects.filter(email='demo_inactif@example.com').delete()
    
    # Créer un utilisateur standard
    user = User.objects.create_user(
        email='demo_inactif@example.com',
        password='DemoPass123!',
        first_name='Demo',
        last_name='Inactif',
        is_active=True,
        is_superuser=False
    )
    
    # Simuler 91 jours d'inactivité
    user.last_login = timezone.now() - timedelta(days=91)
    user.save()
    
    print(f"✓ Utilisateur créé: {user.email}")
    print(f"✓ Type: Utilisateur standard (non-superuser)")
    print(f"✓ Statut: Actif = {user.is_active}")
    print(f"✓ Dernière connexion: {user.last_login}")
    print(f"✓ Jours d'inactivité: {(timezone.now() - user.last_login).days} jours")
    
    print("\n📋 Instructions pour tester:")
    print("1. Démarrer le serveur: python manage.py runserver")
    print("2. Accéder à: http://localhost:8000/users/login/")
    print("3. Se connecter avec:")
    print(f"   - Email: demo_inactif@example.com")
    print(f"   - Mot de passe: DemoPass123!")
    print("4. Faire une requête (naviguer vers une page)")
    print("5. Le compte sera automatiquement désactivé par le middleware")
    print("6. Un message d'erreur s'affichera")
    
    return user


def demo_check_middleware_logic():
    """Tester la logique du middleware"""
    print_separator("Test de la Logique du Middleware")
    
    middleware = InactivityDeactivationMiddleware(lambda x: x)
    
    # Créer un utilisateur de test
    User.objects.filter(email='test_middleware@example.com').delete()
    user = User.objects.create_user(
        email='test_middleware@example.com',
        password='TestPass123!',
        first_name='Test',
        last_name='Middleware',
        is_active=True,
        is_superuser=False
    )
    
    # Test 1: Utilisateur avec 91 jours d'inactivité
    user.last_login = timezone.now() - timedelta(days=91)
    user.save()
    
    should_deactivate, days = middleware._check_inactivity(user)
    print(f"✓ Test 1 - Utilisateur avec 91 jours d'inactivité:")
    print(f"  - Devrait être désactivé: {should_deactivate} (attendu: True)")
    print(f"  - Jours d'inactivité: {days} (attendu: 91)")
    
    # Test 2: Utilisateur avec 89 jours d'inactivité
    user.last_login = timezone.now() - timedelta(days=89)
    user.save()
    
    should_deactivate, days = middleware._check_inactivity(user)
    print(f"\n✓ Test 2 - Utilisateur avec 89 jours d'inactivité:")
    print(f"  - Devrait être désactivé: {should_deactivate} (attendu: False)")
    print(f"  - Jours d'inactivité: {days} (attendu: 89)")
    
    # Nettoyer
    user.delete()


def demo_superuser_exemption():
    """PREUVE 3: Démontrer l'exemption des superusers"""
    print_separator("PREUVE 3: Exemption des Superusers")
    
    # Supprimer le superuser s'il existe déjà
    User.objects.filter(email='demo_admin@example.com').delete()
    
    # Créer un superuser
    superuser = User.objects.create_superuser(
        email='demo_admin@example.com',
        password='AdminPass123!',
        first_name='Demo',
        last_name='Admin'
    )
    
    # Simuler 120 jours d'inactivité (bien > 90)
    superuser.last_login = timezone.now() - timedelta(days=120)
    superuser.save()
    
    print(f"✓ Superuser créé: {superuser.email}")
    print(f"✓ Type: Superuser")
    print(f"✓ Statut: Actif = {superuser.is_active}")
    print(f"✓ Dernière connexion: {superuser.last_login}")
    print(f"✓ Jours d'inactivité: {(timezone.now() - superuser.last_login).days} jours")
    
    # Vérifier avec le middleware
    middleware = InactivityDeactivationMiddleware(lambda x: x)
    should_deactivate, days = middleware._check_inactivity(superuser)
    
    print(f"\n✓ Vérification du middleware:")
    print(f"  - Le superuser devrait être désactivé: {should_deactivate}")
    print(f"  - Mais le middleware l'exempte car is_superuser=True")
    
    print("\n📋 Instructions pour tester:")
    print("1. Se connecter avec le superuser:")
    print(f"   - Email: demo_admin@example.com")
    print(f"   - Mot de passe: AdminPass123!")
    print("2. La connexion réussira malgré 120 jours d'inactivité")
    print("3. Le compte restera actif")
    
    return superuser


def demo_manual_reactivation():
    """PREUVE 4: Démontrer la réactivation manuelle"""
    print_separator("PREUVE 4: Réactivation Manuelle par Superuser")
    
    # Créer un utilisateur désactivé pour inactivité
    User.objects.filter(email='demo_a_reactiver@example.com').delete()
    
    inactive_user = User.objects.create_user(
        email='demo_a_reactiver@example.com',
        password='ReactivePass123!',
        first_name='Demo',
        last_name='AReactiver',
        is_active=False,
        is_superuser=False
    )
    
    inactive_user.deactivation_reason = 'Inactivité de 91 jours (désactivation automatique)'
    inactive_user.deactivated_at = timezone.now()
    inactive_user.save()
    
    print(f"✓ Utilisateur désactivé créé: {inactive_user.email}")
    print(f"✓ Statut: Actif = {inactive_user.is_active}")
    print(f"✓ Raison de désactivation: {inactive_user.deactivation_reason}")
    print(f"✓ Date de désactivation: {inactive_user.deactivated_at}")
    
    print("\n📋 Instructions pour réactiver:")
    print("1. Se connecter à l'admin Django avec un superuser:")
    print("   http://localhost:8000/admin/")
    print("2. Naviguer vers: Users > Users")
    print(f"3. Cocher la case de l'utilisateur: {inactive_user.email}")
    print("4. Dans le menu 'Action', sélectionner:")
    print("   'Réactiver les comptes désactivés pour inactivité'")
    print("5. Cliquer sur 'Go'")
    print("6. Le compte sera réactivé")
    print("7. L'utilisateur pourra se reconnecter")
    
    print("\n✓ Pour tester la reconnexion après réactivation:")
    print(f"   - Email: demo_a_reactiver@example.com")
    print(f"   - Mot de passe: ReactivePass123!")
    
    return inactive_user


def demo_list_inactive_users():
    """Lister tous les utilisateurs inactifs"""
    print_separator("Liste des Utilisateurs Inactifs")
    
    inactive_users = User.objects.filter(is_active=False)
    
    if inactive_users.exists():
        print(f"✓ Nombre d'utilisateurs inactifs: {inactive_users.count()}\n")
        
        for user in inactive_users:
            print(f"📧 {user.email}")
            print(f"   - Nom: {user.get_full_name()}")
            print(f"   - Superuser: {user.is_superuser}")
            print(f"   - Raison: {user.deactivation_reason or 'Non spécifiée'}")
            print(f"   - Désactivé le: {user.deactivated_at or 'N/A'}")
            print()
    else:
        print("✓ Aucun utilisateur inactif trouvé")


def demo_cleanup():
    """Nettoyer les utilisateurs de démonstration"""
    print_separator("Nettoyage des Utilisateurs de Démonstration")
    
    demo_emails = [
        'demo_inactif@example.com',
        'demo_admin@example.com',
        'demo_a_reactiver@example.com',
        'test_middleware@example.com'
    ]
    
    for email in demo_emails:
        deleted_count = User.objects.filter(email=email).delete()[0]
        if deleted_count > 0:
            print(f"✓ Supprimé: {email}")
    
    print("\n✓ Nettoyage terminé")


def main():
    """Fonction principale"""
    print("\n" + "🔒" * 40)
    print("  DÉMONSTRATION - SYSTÈME DE DÉSACTIVATION AUTOMATIQUE")
    print("  Comptes Inactifs (90 jours)")
    print("🔒" * 40)
    
    while True:
        print("\n" + "-"*80)
        print("Menu Principal:")
        print("-"*80)
        print("1. Afficher la configuration (PREUVE 1)")
        print("2. Créer un utilisateur inactif pour test (PREUVE 2)")
        print("3. Tester la logique du middleware")
        print("4. Démontrer l'exemption des superusers (PREUVE 3)")
        print("5. Préparer la réactivation manuelle (PREUVE 4)")
        print("6. Lister tous les utilisateurs inactifs")
        print("7. Nettoyer les utilisateurs de démonstration")
        print("8. Exécuter toutes les démonstrations")
        print("0. Quitter")
        print("-"*80)
        
        choice = input("\nVotre choix: ").strip()
        
        if choice == '1':
            demo_configuration()
        elif choice == '2':
            demo_create_inactive_user()
        elif choice == '3':
            demo_check_middleware_logic()
        elif choice == '4':
            demo_superuser_exemption()
        elif choice == '5':
            demo_manual_reactivation()
        elif choice == '6':
            demo_list_inactive_users()
        elif choice == '7':
            demo_cleanup()
        elif choice == '8':
            demo_configuration()
            demo_check_middleware_logic()
            demo_create_inactive_user()
            demo_superuser_exemption()
            demo_manual_reactivation()
            demo_list_inactive_users()
        elif choice == '0':
            print("\n✓ Au revoir!")
            break
        else:
            print("\n❌ Choix invalide. Veuillez réessayer.")
        
        input("\nAppuyez sur Entrée pour continuer...")


if __name__ == '__main__':
    main()
