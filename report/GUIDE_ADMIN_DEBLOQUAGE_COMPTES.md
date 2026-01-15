# 🔓 GUIDE ADMINISTRATEUR - DÉBLOCAGE DES COMPTES VERROUILLÉS

## 📋 Vue d'ensemble

Ce guide explique comment les administrateurs peuvent débloquer manuellement les comptes utilisateurs verrouillés par le système de protection contre les attaques par force brute.

---

## 🎯 Méthodes de Déblocage

### Méthode 1: Interface d'Administration Django (Recommandée)

#### Étape 1: Accéder à l'interface admin

1. Ouvrez votre navigateur et accédez à: `http://localhost:8000/admin/`
2. Connectez-vous avec vos identifiants de **superuser**

#### Étape 2: Accéder aux tentatives d'accès

1. Dans le menu de gauche, cliquez sur **"Axes"**
2. Cliquez sur **"Access attempts"**

#### Étape 3: Identifier le compte verrouillé

Vous verrez une liste de toutes les tentatives de connexion échouées avec:
- **Username**: Email de l'utilisateur
- **IP Address**: Adresse IP de la tentative
- **Failures since start**: Nombre de tentatives échouées
- **Attempt time**: Date et heure de la dernière tentative
- **Locked out**: Statut de verrouillage (✓ = verrouillé)

#### Étape 4: Débloquer le compte

**Option A - Déblocage individuel**:
1. Cochez la case à côté du compte à débloquer
2. Dans le menu déroulant "Action", sélectionnez **"Delete selected access attempts"**
3. Cliquez sur **"Go"**
4. Confirmez la suppression

**Option B - Déblocage via détails**:
1. Cliquez sur l'entrée du compte verrouillé
2. En bas de la page, cliquez sur **"Delete"**
3. Confirmez la suppression

✅ **Le compte est maintenant débloqué et l'utilisateur peut se reconnecter immédiatement.**

---

### Méthode 2: Ligne de Commande (Pour les Experts)

#### Commande 1: Réinitialiser tous les verrouillages

```bash
cd c:\Users\Lenovo\CascadeProjects\msrn\report
python manage.py axes_reset
```

**Résultat**: Tous les comptes verrouillés sont débloqués.

#### Commande 2: Débloquer un utilisateur spécifique

```bash
python manage.py axes_reset_username utilisateur@mtn-ci.com
```

**Résultat**: Seul le compte `utilisateur@mtn-ci.com` est débloqué.

#### Commande 3: Débloquer une adresse IP spécifique

```bash
python manage.py axes_reset_ip 192.168.1.100
```

**Résultat**: Tous les comptes verrouillés depuis l'IP `192.168.1.100` sont débloqués.

#### Commande 4: Lister tous les comptes verrouillés

```bash
python manage.py axes_list_attempts
```

**Résultat**: Affiche la liste de tous les comptes actuellement verrouillés.

---

### Méthode 3: Via la Base de Données (Avancé)

**⚠️ ATTENTION**: Cette méthode nécessite un accès direct à PostgreSQL.

#### Étape 1: Se connecter à PostgreSQL

```bash
psql -U msrn -d report_db
```

#### Étape 2: Voir les comptes verrouillés

```sql
SELECT 
    id,
    username,
    ip_address,
    failures_since_start,
    attempt_time,
    locked_out
FROM axes_accessattempt
WHERE locked_out = true
ORDER BY attempt_time DESC;
```

#### Étape 3: Débloquer un compte spécifique

```sql
DELETE FROM axes_accessattempt 
WHERE username = 'utilisateur@mtn-ci.com';
```

#### Étape 4: Débloquer tous les comptes

```sql
DELETE FROM axes_accessattempt;
```

---

## 📊 Scénarios Courants

### Scénario 1: Utilisateur légitime bloqué par erreur

**Situation**: Un utilisateur a oublié son mot de passe et a été verrouillé après 10 tentatives.

**Solution**:
1. Vérifier l'identité de l'utilisateur (appel téléphonique, email, etc.)
2. Débloquer le compte via l'interface admin (Méthode 1)
3. Réinitialiser le mot de passe de l'utilisateur si nécessaire
4. Informer l'utilisateur qu'il peut se reconnecter

### Scénario 2: Attaque par force brute détectée

**Situation**: Plusieurs comptes sont verrouillés depuis la même adresse IP.

**Solution**:
1. **NE PAS débloquer immédiatement**
2. Analyser les logs pour confirmer l'attaque:
   ```bash
   python manage.py axes_list_attempts
   ```
3. Bloquer l'adresse IP au niveau du firewall si nécessaire
4. Contacter les utilisateurs légitimes concernés
5. Débloquer uniquement les comptes légitimes après vérification

### Scénario 3: Déblocage automatique après 30 minutes

**Situation**: Un utilisateur attend le déblocage automatique.

**Solution**:
- **Aucune action requise** - Le système débloque automatiquement après 30 minutes
- Si l'utilisateur est pressé, débloquer manuellement via la Méthode 1 ou 2

### Scénario 4: Déblocage d'urgence en masse

**Situation**: Incident système nécessitant le déblocage de tous les comptes.

**Solution**:
```bash
python manage.py axes_reset
```

---

## 🔍 Monitoring et Alertes

### Vérifier les statistiques de verrouillage

```bash
# Nombre total de comptes verrouillés
python manage.py shell -c "from axes.models import AccessAttempt; print(f'Comptes verrouillés: {AccessAttempt.objects.filter(locked_out=True).count()}')"

# Comptes verrouillés dans les dernières 24h
python manage.py shell -c "from axes.models import AccessAttempt; from django.utils import timezone; from datetime import timedelta; print(AccessAttempt.objects.filter(attempt_time__gte=timezone.now()-timedelta(days=1)).count())"
```

### Exporter les logs pour analyse

```bash
# Export CSV des tentatives échouées
python manage.py shell -c "
from axes.models import AccessAttempt
import csv
with open('failed_attempts.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['Username', 'IP', 'Failures', 'Time', 'Locked'])
    for attempt in AccessAttempt.objects.all():
        writer.writerow([attempt.username, attempt.ip_address, attempt.failures_since_start, attempt.attempt_time, attempt.locked_out])
print('Export terminé: failed_attempts.csv')
"
```

---

## 📝 Bonnes Pratiques

### ✅ À FAIRE

1. **Vérifier l'identité** avant de débloquer un compte
2. **Documenter** chaque déblocage manuel (qui, quand, pourquoi)
3. **Analyser les patterns** d'attaques répétées
4. **Informer l'utilisateur** après déblocage
5. **Surveiller** les comptes fréquemment verrouillés

### ❌ À NE PAS FAIRE

1. **Ne pas** débloquer automatiquement sans vérification
2. **Ne pas** ignorer les alertes de verrouillages multiples
3. **Ne pas** désactiver la protection pour "simplifier"
4. **Ne pas** partager les commandes de déblocage avec des non-admins
5. **Ne pas** oublier de changer le mot de passe si compromis

---

## 🚨 Procédure d'Urgence

### En cas d'attaque massive

1. **STOP**: Ne pas débloquer les comptes immédiatement
2. **ANALYSER**: Vérifier les logs et identifier la source
3. **BLOQUER**: Bloquer les IP malveillantes au niveau firewall
4. **ALERTER**: Notifier l'équipe de sécurité
5. **DOCUMENTER**: Créer un rapport d'incident
6. **DÉBLOQUER**: Uniquement les comptes légitimes après vérification

### Contact d'urgence

- **Équipe Sécurité**: security@mtn-ci.com
- **Support IT**: support@mtn-ci.com
- **Hotline**: +225 XX XX XX XX

---

## 📞 Support Utilisateur

### Message type pour informer un utilisateur

```
Bonjour [Nom],

Votre compte a été temporairement verrouillé pour des raisons de sécurité 
suite à 10 tentatives de connexion échouées.

Nous avons vérifié votre identité et débloqué votre compte. Vous pouvez 
maintenant vous reconnecter.

Si vous avez oublié votre mot de passe, veuillez utiliser la fonction 
"Mot de passe oublié" sur la page de connexion.

Pour votre sécurité:
- Utilisez un mot de passe fort et unique
- Ne partagez jamais vos identifiants
- Contactez-nous immédiatement en cas d'activité suspecte

Cordialement,
L'équipe MSRN
```

---

## 📈 Rapports et Statistiques

### Rapport hebdomadaire recommandé

```bash
# Script à exécuter chaque lundi
python manage.py shell << EOF
from axes.models import AccessAttempt
from django.utils import timezone
from datetime import timedelta

week_ago = timezone.now() - timedelta(days=7)
attempts = AccessAttempt.objects.filter(attempt_time__gte=week_ago)

print("=== RAPPORT HEBDOMADAIRE SÉCURITÉ ===")
print(f"Période: {week_ago.date()} à {timezone.now().date()}")
print(f"Total tentatives échouées: {attempts.count()}")
print(f"Comptes verrouillés: {attempts.filter(locked_out=True).count()}")
print(f"IP uniques: {attempts.values('ip_address').distinct().count()}")
print("\nTop 5 comptes ciblés:")
for username in attempts.values('username').annotate(count=models.Count('id')).order_by('-count')[:5]:
    print(f"  - {username['username']}: {username['count']} tentatives")
EOF
```

---

## ✅ Checklist Administrateur

Avant de débloquer un compte, vérifier:

- [ ] L'identité de l'utilisateur a été confirmée
- [ ] L'adresse IP de la tentative est légitime
- [ ] Aucun pattern d'attaque n'est détecté
- [ ] L'utilisateur a été informé du déblocage
- [ ] Le déblocage a été documenté
- [ ] Le mot de passe a été réinitialisé si nécessaire

---

## 📚 Ressources Complémentaires

- [Documentation Django-Axes](https://django-axes.readthedocs.io/)
- [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
- [Audit de Sécurité Complet](./AUDIT_SECURITE_FORCE_BRUTE.md)

---

**Version**: 1.0  
**Dernière mise à jour**: 14 Janvier 2026  
**Auteur**: Expert Cybersécurité MSRN
