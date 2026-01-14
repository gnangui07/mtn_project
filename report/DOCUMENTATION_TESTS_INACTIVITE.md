# 📋 Documentation des Tests - Désactivation Automatique des Comptes Inactifs

## Vue d'ensemble

Ce document fournit les procédures de test pour valider la fonctionnalité de désactivation automatique des comptes utilisateurs standards inactifs depuis 90 jours.

---

## 🎯 Preuve 1: Configuration des Paramètres

### Objectif
Confirmer que le système est configuré pour désactiver automatiquement les comptes utilisateurs standards après 90 jours d'inactivité.

### Procédure de Test

#### Étape 1: Vérifier la Configuration du Middleware
```bash
# Ouvrir le fichier settings.py
cat report/reports/settings.py | grep -A 15 "MIDDLEWARE"
```

**Résultat attendu:**
```python
MIDDLEWARE = [
    ...
    'users.middleware_inactivity.InactivityDeactivationMiddleware',
    ...
]
```

#### Étape 2: Vérifier la Constante de Configuration
```bash
# Ouvrir le fichier middleware_inactivity.py
cat report/users/middleware_inactivity.py | grep "INACTIVITY_DAYS"
```

**Résultat attendu:**
```python
INACTIVITY_DAYS = 90
```

#### Étape 3: Capture d'Écran de l'Interface de Configuration
1. Accéder à l'interface admin Django: `http://localhost:8000/admin/`
2. Se connecter avec un compte superuser
3. Naviguer vers **Users** > **Users**
4. Prendre une capture d'écran montrant la liste des utilisateurs avec les colonnes:
   - Email
   - Statut (is_active)
   - Date de dernière connexion (last_login)
   - Date d'inscription (date_joined)

#### Étape 4: Exécuter les Tests Automatisés
```bash
cd report
pytest users/tests/test_inactivity_deactivation.py::TestInactivityConfiguration -v
```

**Résultat attendu:**
```
✓ test_inactivity_days_configuration PASSED
✓ test_middleware_is_registered PASSED
✓ test_deactivation_fields_exist PASSED
```

---

## 🎯 Preuve 2: Désactivation Automatique après 90 Jours

### Objectif
Démontrer que les comptes utilisateurs standards inactifs depuis 90 jours sont automatiquement désactivés.

### Procédure de Test

#### Étape 1: Créer un Utilisateur de Test
```bash
python manage.py shell
```

```python
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

User = get_user_model()

# Créer un utilisateur standard
test_user = User.objects.create_user(
    email='test_inactif@example.com',
    password='TestPass123!',
    first_name='Test',
    last_name='Inactif',
    is_active=True,
    is_superuser=False
)

print(f"Utilisateur créé: {test_user.email}")
print(f"Actif: {test_user.is_active}")
print(f"Date de création: {test_user.date_joined}")
```

#### Étape 2: Modifier la Date de Dernière Connexion
```python
# Simuler 91 jours d'inactivité
test_user.last_login = timezone.now() - timedelta(days=91)
test_user.save()

print(f"Dernière connexion modifiée: {test_user.last_login}")
print(f"Jours d'inactivité: {(timezone.now() - test_user.last_login).days}")
```

#### Étape 3: Tenter une Connexion
1. Ouvrir un navigateur et accéder à: `http://localhost:8000/users/connexion/`
2. Saisir les identifiants:
   - Email: `test_inactif@example.com`
   - Mot de passe: `TestPass123!`
3. Cliquer sur "Se connecter"

**Résultat attendu:**
- ❌ La connexion échoue
- 📧 Un message d'erreur s'affiche: 
  > "Votre compte a été verrouillé pour cause d'inactivité. Veuillez contacter un administrateur (superuser) pour le réactiver."

#### Étape 4: Vérifier la Désactivation en Base de Données
```python
# Recharger l'utilisateur depuis la base
test_user.refresh_from_db()

print(f"Compte actif: {test_user.is_active}")  # False
print(f"Raison de désactivation: {test_user.deactivation_reason}")
print(f"Date de désactivation: {test_user.deactivated_at}")
```

**Résultat attendu:**
```
Compte actif: False
Raison de désactivation: Inactivité de 91 jours (désactivation automatique)
Date de désactivation: 2026-01-13 14:30:00+00:00
```

#### Étape 5: Capture d'Écran
Prendre une capture d'écran de:
1. La page de connexion avec le message d'erreur
2. L'interface admin montrant le compte désactivé

#### Étape 6: Exécuter les Tests Automatisés
```bash
pytest users/tests/test_inactivity_deactivation.py::TestAutomaticDeactivation -v
```

**Résultat attendu:**
```
✓ test_deactivation_after_90_days_no_login PASSED
✓ test_deactivation_after_90_days_with_old_login PASSED
✓ test_login_attempt_shows_inactivity_message PASSED
✓ test_no_deactivation_before_90_days PASSED
```

---

## 🎯 Preuve 3: Exemption des Superusers

### Objectif
Confirmer que les comptes superuser ne sont pas automatiquement désactivés, même après une longue période d'inactivité.

### Procédure de Test

#### Étape 1: Identifier un Compte Superuser
```bash
python manage.py shell
```

```python
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

User = get_user_model()

# Créer ou récupérer un superuser
superuser = User.objects.create_superuser(
    email='admin_test@example.com',
    password='AdminPass123!',
    first_name='Admin',
    last_name='Test'
)

print(f"Superuser: {superuser.email}")
print(f"Is superuser: {superuser.is_superuser}")
print(f"Actif: {superuser.is_active}")
```

#### Étape 2: Simuler 120 Jours d'Inactivité
```python
# Simuler 120 jours d'inactivité (bien > 90)
superuser.last_login = timezone.now() - timedelta(days=120)
superuser.save()

print(f"Dernière connexion: {superuser.last_login}")
print(f"Jours d'inactivité: {(timezone.now() - superuser.last_login).days}")
```

#### Étape 3: Se Connecter avec le Superuser
1. Ouvrir un navigateur et accéder à: `http://localhost:8000/users/connexion/`
2. Saisir les identifiants du superuser
3. Cliquer sur "Se connecter"

**Résultat attendu:**
- ✅ La connexion réussit
- ✅ Redirection vers la page d'accueil
- ✅ Message de bienvenue affiché

#### Étape 4: Vérifier que le Compte Reste Actif
```python
# Recharger le superuser depuis la base
superuser.refresh_from_db()

print(f"Compte actif: {superuser.is_active}")  # True
print(f"Raison de désactivation: {superuser.deactivation_reason}")  # None
print(f"Date de désactivation: {superuser.deactivated_at}")  # None
```

**Résultat attendu:**
```
Compte actif: True
Raison de désactivation: None
Date de désactivation: None
```

#### Étape 5: Capture d'Écran
Prendre une capture d'écran de:
1. La page d'accueil après connexion réussie
2. L'interface admin montrant le superuser toujours actif malgré 120 jours d'inactivité

#### Étape 6: Exécuter les Tests Automatisés
```bash
pytest users/tests/test_inactivity_deactivation.py::TestSuperuserExemption -v
```

**Résultat attendu:**
```
✓ test_superuser_not_deactivated_after_90_days PASSED
✓ test_superuser_never_logged_in_not_deactivated PASSED
✓ test_middleware_exempts_superusers PASSED
```

---

## 🎯 Preuve 4: Réactivation Manuelle par Superuser

### Objectif
Démontrer que les comptes utilisateurs standards désactivés peuvent être réactivés par un superuser actif.

### Procédure de Test

#### Étape 1: Désactiver un Compte pour Inactivité
```bash
python manage.py shell
```

```python
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

# Créer un utilisateur désactivé pour inactivité
inactive_user = User.objects.create_user(
    email='user_a_reactiver@example.com',
    password='TestPass123!',
    first_name='User',
    last_name='Inactif',
    is_active=False,
    is_superuser=False
)

inactive_user.deactivation_reason = 'Inactivité de 91 jours (désactivation automatique)'
inactive_user.deactivated_at = timezone.now()
inactive_user.save()

print(f"Utilisateur créé: {inactive_user.email}")
print(f"Actif: {inactive_user.is_active}")
print(f"Raison: {inactive_user.deactivation_reason}")
```

#### Étape 2: Se Connecter avec un Superuser Actif
1. Ouvrir un navigateur et accéder à: `http://localhost:8000/admin/`
2. Se connecter avec un compte superuser actif
3. Naviguer vers **Users** > **Users**

#### Étape 3: Réactiver le Compte
1. Cocher la case à côté de l'utilisateur `user_a_reactiver@example.com`
2. Dans le menu déroulant "Action", sélectionner **"Réactiver les comptes désactivés pour inactivité"**
3. Cliquer sur "Go"

**Résultat attendu:**
- ✅ Message de succès: "1 compte(s) réactivé(s) avec succès"
- ✅ L'utilisateur reçoit un email de notification (optionnel)

#### Étape 4: Vérifier la Réactivation
```python
# Recharger l'utilisateur depuis la base
inactive_user.refresh_from_db()

print(f"Compte actif: {inactive_user.is_active}")  # True
print(f"Raison de désactivation: {inactive_user.deactivation_reason}")  # None
print(f"Date de désactivation: {inactive_user.deactivated_at}")  # None
```

**Résultat attendu:**
```
Compte actif: True
Raison de désactivation: None
Date de désactivation: None
```

#### Étape 5: Vérifier que l'Utilisateur Peut se Connecter
1. Se déconnecter de l'admin
2. Accéder à: `http://localhost:8000/users/connexion/`
3. Saisir les identifiants:
   - Email: `user_a_reactiver@example.com`
   - Mot de passe: `TestPass123!`
4. Cliquer sur "Se connecter"

**Résultat attendu:**
- ✅ La connexion réussit
- ✅ Redirection vers la page d'accueil
- ✅ Message de bienvenue affiché

#### Étape 6: Capture d'Écran
Prendre une capture d'écran de:
1. L'interface admin avec l'action de réactivation
2. Le message de succès après réactivation
3. La page d'accueil après connexion réussie de l'utilisateur réactivé

#### Étape 7: Exécuter les Tests Automatisés
```bash
pytest users/tests/test_inactivity_deactivation.py::TestManualReactivation -v
```

**Résultat attendu:**
```
✓ test_admin_action_reactivates_account PASSED
✓ test_reactivated_user_can_login PASSED
✓ test_only_superuser_can_reactivate PASSED
✓ test_reactivation_clears_deactivation_fields PASSED
```

---

## 🚀 Exécution Complète des Tests

### Lancer Tous les Tests
```bash
cd report
pytest users/tests/test_inactivity_deactivation.py -v --tb=short
```

### Avec Couverture de Code
```bash
pytest users/tests/test_inactivity_deactivation.py --cov=users.middleware_inactivity --cov=users.admin --cov-report=html -v
```

### Résultat Attendu
```
==================== test session starts ====================
users/tests/test_inactivity_deactivation.py::TestInactivityConfiguration::test_inactivity_days_configuration PASSED
users/tests/test_inactivity_deactivation.py::TestInactivityConfiguration::test_middleware_is_registered PASSED
users/tests/test_inactivity_deactivation.py::TestInactivityConfiguration::test_deactivation_fields_exist PASSED
users/tests/test_inactivity_deactivation.py::TestAutomaticDeactivation::test_deactivation_after_90_days_no_login PASSED
users/tests/test_inactivity_deactivation.py::TestAutomaticDeactivation::test_deactivation_after_90_days_with_old_login PASSED
users/tests/test_inactivity_deactivation.py::TestAutomaticDeactivation::test_login_attempt_shows_inactivity_message PASSED
users/tests/test_inactivity_deactivation.py::TestAutomaticDeactivation::test_no_deactivation_before_90_days PASSED
users/tests/test_inactivity_deactivation.py::TestSuperuserExemption::test_superuser_not_deactivated_after_90_days PASSED
users/tests/test_inactivity_deactivation.py::TestSuperuserExemption::test_superuser_never_logged_in_not_deactivated PASSED
users/tests/test_inactivity_deactivation.py::TestSuperuserExemption::test_middleware_exempts_superusers PASSED
users/tests/test_inactivity_deactivation.py::TestManualReactivation::test_admin_action_reactivates_account PASSED
users/tests/test_inactivity_deactivation.py::TestManualReactivation::test_reactivated_user_can_login PASSED
users/tests/test_inactivity_deactivation.py::TestManualReactivation::test_only_superuser_can_reactivate PASSED
users/tests/test_inactivity_deactivation.py::TestManualReactivation::test_reactivation_clears_deactivation_fields PASSED
users/tests/test_inactivity_deactivation.py::TestMiddlewareLogic::test_check_inactivity_method PASSED
users/tests/test_inactivity_deactivation.py::TestMiddlewareLogic::test_check_inactivity_no_login PASSED

==================== 16 passed in 5.23s ====================
```

---

## 📊 Checklist de Validation

### Preuve 1: Configuration ✅
- [ ] Middleware enregistré dans `settings.py`
- [ ] Constante `INACTIVITY_DAYS = 90` configurée
- [ ] Champs `deactivation_reason` et `deactivated_at` ajoutés au modèle
- [ ] Capture d'écran de l'interface admin
- [ ] Tests automatisés passent

### Preuve 2: Désactivation Automatique ✅
- [ ] Utilisateur standard créé
- [ ] Date de dernière connexion modifiée (91 jours)
- [ ] Tentative de connexion échoue avec message approprié
- [ ] Compte désactivé en base de données
- [ ] Capture d'écran du message d'erreur
- [ ] Tests automatisés passent

### Preuve 3: Exemption Superusers ✅
- [ ] Superuser créé avec 120 jours d'inactivité
- [ ] Connexion réussit malgré l'inactivité
- [ ] Compte reste actif en base de données
- [ ] Capture d'écran de la connexion réussie
- [ ] Tests automatisés passent

### Preuve 4: Réactivation Manuelle ✅
- [ ] Compte désactivé pour inactivité
- [ ] Connexion superuser réussie
- [ ] Action de réactivation effectuée
- [ ] Compte réactivé en base de données
- [ ] Utilisateur peut se reconnecter
- [ ] Capture d'écran de l'action admin
- [ ] Tests automatisés passent

---

## 🔧 Dépannage

### Problème: Le middleware ne se déclenche pas
**Solution:** Vérifier que le middleware est bien enregistré dans `settings.py` et redémarrer le serveur Django.

### Problème: Les tests échouent avec "core:accueil not found"
**Solution:** S'assurer que l'URL `core:accueil` existe dans `urls.py` ou modifier les tests pour utiliser une URL valide.

### Problème: L'action admin n'apparaît pas
**Solution:** Vider le cache du navigateur et vérifier que l'utilisateur connecté est bien un superuser.

---

## 📝 Notes Importantes

1. **Sécurité:** Les superusers ne sont JAMAIS désactivés automatiquement, même après des années d'inactivité.

2. **Notifications:** Un email de notification est envoyé automatiquement lors de la réactivation d'un compte (si configuré).

3. **Logs:** Toutes les désactivations et réactivations sont loggées pour audit.

4. **Performance:** Le middleware vérifie l'inactivité à chaque requête mais n'effectue qu'une seule requête SQL par utilisateur connecté.

5. **Migration:** Les nouveaux champs `deactivation_reason` et `deactivated_at` sont ajoutés via la migration `0003_user_deactivated_at_user_deactivation_reason.py`.

---

## 📞 Support

Pour toute question ou problème, contacter l'équipe de développement ou consulter la documentation technique dans le code source.
