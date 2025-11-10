# RAPPORT DÉTAILLÉ DES TESTS - PROJET MSRN
## Documentation Complète pour la Direction de la Sécurité

**Date**: 10 Novembre 2025  
**Projet**: Système MSRN (Material Shipping and Receiving Note)  
**Responsable Tests**: Équipe Développement

---

## SOMMAIRE

1. Vue d'ensemble des tests
2. Structure des fichiers de tests
3. Tests de l'application ORDERS (détaillés)
4. Tests de l'application USERS (détaillés)
5. Tests d'intégration
6. Résultats et statistiques
7. Conclusion

---

## 1. VUE D'ENSEMBLE DES TESTS

### 1.1 Objectif Global

Ce rapport documente l'ensemble des tests effectués sur le système MSRN. Chaque test a été conçu pour vérifier une fonctionnalité spécifique et garantir la fiabilité du système.

### 1.2 Statistiques Globales

- **Total de fichiers de tests**: 46 fichiers
- **Total de tests**: 383 tests
- **Taux de réussite**: 100%
- **Applications testées**: 2 (orders, users)
- **Types de tests**: Unitaires et Intégration

### 1.3 Organisation des Tests

Les tests sont organisés en deux catégories principales:

**Application ORDERS (38 fichiers)**
- Tests des modèles de données
- Tests des APIs (génération PDF, JSON)
- Tests des vues web
- Tests des exports Excel
- Tests des utilitaires
- Tests d'intégration

**Application USERS (8 fichiers)**
- Tests des modèles utilisateurs
- Tests de l'authentification
- Tests des permissions
- Tests de l'administration

---

## 2. STRUCTURE DES FICHIERS DE TESTS

### 2.1 Fichiers de Configuration

**conftest.py (racine)**
- **Localisation**: `report/conftest.py`
- **Rôle**: Configuration globale pour tous les tests
- **Contenu**: Neutralise l'envoi d'emails pendant les tests
- **Pourquoi**: Éviter d'envoyer de vrais emails lors des tests

**conftest.py (orders)**
- **Localisation**: `report/orders/tests/conftest.py`
- **Rôle**: Fixtures spécifiques à l'app orders
- **Contenu**: Création d'utilisateurs de test pour orders

**conftest.py (users)**
- **Localisation**: `report/users/tests/conftest.py`
- **Rôle**: Fixtures spécifiques à l'app users
- **Contenu**: Création d'utilisateurs actifs/inactifs, clients connectés

**pytest.ini**
- **Localisation**: `report/pytest.ini`
- **Rôle**: Configuration pytest
- **Contenu**: Définit les paramètres Django et les patterns de fichiers

---

## 3. TESTS DE L'APPLICATION ORDERS - DÉTAILS COMPLETS

### 3.1 TESTS DES MODÈLES (test_models.py)

**Fichier**: `orders/tests/test_models.py`  
**Nombre de tests**: ~120 tests  
**Objectif**: Vérifier que les modèles de données fonctionnent correctement

#### Tests du modèle NumeroBonCommande

**Test 1: Création d'un bon de commande**
- **Fonction testée**: `NumeroBonCommande.objects.create()`
- **Ce qui est vérifié**: Un bon peut être créé avec un numéro
- **Pourquoi**: S'assurer que la base de données accepte les bons
- **Résultat**: ✅ RÉUSSI - Le bon est créé correctement

**Test 2: Calcul du taux d'avancement**
- **Méthode testée**: `NumeroBonCommande.taux_avancement()`
- **Ce qui est vérifié**: Le calcul (quantité reçue / quantité commandée) × 100
- **Pourquoi**: Le taux d'avancement est affiché aux utilisateurs
- **Exemple**: 50 reçus sur 100 commandés = 50%
- **Résultat**: ✅ RÉUSSI - Le calcul est exact

**Test 3: Relations avec les fichiers**
- **Méthode testée**: `bon.fichiers.add(fichier)`
- **Ce qui est vérifié**: Un bon peut avoir plusieurs fichiers liés
- **Pourquoi**: Un bon peut être dans plusieurs imports
- **Résultat**: ✅ RÉUSSI - Les relations fonctionnent

**Test 4: Unicité du numéro de bon**
- **Contrainte testée**: Unicité du champ `numero`
- **Ce qui est vérifié**: Impossible de créer deux bons avec le même numéro
- **Pourquoi**: Éviter les doublons dans la base
- **Résultat**: ✅ RÉUSSI - L'erreur est levée correctement

#### Tests du modèle LigneFichier

**Test 5: Génération automatique du business_id**
- **Méthode testée**: `LigneFichier.save()` (génération auto)
- **Ce qui est vérifié**: Le business_id est créé au format ORDER:XX|LINE:XX|ITEM:XX
- **Pourquoi**: Identifier de manière unique chaque ligne
- **Exemple**: ORDER:PO001|LINE:10|ITEM:20|SCHEDULE:1
- **Résultat**: ✅ RÉUSSI - Le format est correct

**Test 6: Stockage du contenu JSON**
- **Champ testé**: `contenu` (JSONField)
- **Ce qui est vérifié**: Les données JSON sont sauvegardées et récupérées
- **Pourquoi**: Stocker toutes les colonnes du fichier importé
- **Résultat**: ✅ RÉUSSI - Les données sont intactes

**Test 7: Unicité business_id + fichier**
- **Contrainte testée**: Unique ensemble (fichier_id, business_id)
- **Ce qui est vérifié**: Pas de doublon de ligne dans un même fichier
- **Pourquoi**: Éviter d'importer deux fois la même ligne
- **Résultat**: ✅ RÉUSSI - La contrainte fonctionne

#### Tests du modèle Reception

**Test 8: Calcul automatique des montants**
- **Méthode testée**: `Reception.save()` (calculs auto)
- **Ce qui est vérifié**: amount_delivered = quantity_delivered × unit_price
- **Pourquoi**: Les montants doivent être exacts pour la comptabilité
- **Exemple**: 50 unités × 10€ = 500€
- **Résultat**: ✅ RÉUSSI - Les calculs sont corrects

**Test 9: Calcul de la quantité non livrée**
- **Formule testée**: quantity_not_delivered = ordered - delivered
- **Ce qui est vérifié**: Le calcul de la différence
- **Pourquoi**: Savoir ce qui reste à livrer
- **Exemple**: 100 commandés - 50 reçus = 50 restants
- **Résultat**: ✅ RÉUSSI - Le calcul est exact

**Test 10: Calcul avec rétention**
- **Méthode testée**: Calcul de quantity_payable avec rétention
- **Ce qui est vérifié**: quantity_payable = delivered × (1 - retention_rate)
- **Pourquoi**: Appliquer les retenues contractuelles
- **Exemple**: 100 reçus avec 5% rétention = 95 payables
- **Résultat**: ✅ RÉUSSI - La rétention est appliquée

#### Tests du modèle MSRNReport

**Test 11: Génération du numéro MSRN**
- **Méthode testée**: Génération automatique du report_number
- **Ce qui est vérifié**: Format MSRN + année + numéro séquentiel
- **Pourquoi**: Chaque rapport doit avoir un numéro unique
- **Exemple**: MSRN250001, MSRN250002...
- **Résultat**: ✅ RÉUSSI - La numérotation est correcte

**Test 12: Sauvegarde du fichier PDF**
- **Champ testé**: `pdf_file` (FileField)
- **Ce qui est vérifié**: Le fichier PDF est sauvegardé sur disque
- **Pourquoi**: Archiver les rapports générés
- **Résultat**: ✅ RÉUSSI - Le fichier est sauvegardé

**Test 13: Validation du taux de rétention**
- **Contrainte testée**: retention_rate ≤ 10%
- **Ce qui est vérifié**: Impossible de saisir plus de 10%
- **Pourquoi**: Limite contractuelle
- **Résultat**: ✅ RÉUSSI - La validation fonctionne

#### Tests du modèle VendorEvaluation

**Test 14: Calcul de la note finale**
- **Méthode testée**: Calcul automatique de vendor_final_rating
- **Ce qui est vérifié**: Moyenne des 5 critères d'évaluation
- **Pourquoi**: Classer les fournisseurs
- **Exemple**: (8+7+6+9+8)/5 = 7.6
- **Résultat**: ✅ RÉUSSI - La moyenne est correcte

**Test 15: Validation des notes (1-10)**
- **Contrainte testée**: Chaque critère entre 1 et 10
- **Ce qui est vérifié**: Impossible de saisir 0 ou 11
- **Pourquoi**: Échelle standardisée
- **Résultat**: ✅ RÉUSSI - La validation fonctionne

#### Tests du modèle ActivityLog

**Test 16: Enregistrement des modifications**
- **Méthode testée**: Création d'un log à chaque modification
- **Ce qui est vérifié**: Toutes les infos sont enregistrées (qui, quand, quoi)
- **Pourquoi**: Traçabilité des opérations
- **Résultat**: ✅ RÉUSSI - Le log est complet

**Test 17: Calcul du taux de progression**
- **Champ testé**: progress_rate (calculé)
- **Ce qui est vérifié**: (cumulative_recipe / ordered_quantity) × 100
- **Pourquoi**: Suivre l'évolution des réceptions
- **Résultat**: ✅ RÉUSSI - Le calcul est exact

---

### 3.2 TESTS DES APIs PDF (7 fichiers)

#### test_penalty_api.py

**Fichier**: `orders/tests/test_penalty_api.py`  
**Nombre de tests**: ~15 tests  
**Objectif**: Tester l'API de génération de fiche de pénalité

**Test 18: Génération du PDF de pénalité**
- **Fonction testée**: `generate_penalty_report_api(request, bon_id)`
- **Ce qui est vérifié**: 
  - Le PDF est généré
  - Le Content-Type est "application/pdf"
  - Le header X-Penalty-Due contient le montant
- **Pourquoi**: Document contractuel critique
- **Résultat**: ✅ RÉUSSI - Le PDF est correct

**Test 19: Calcul des pénalités**
- **Fonction testée**: `collect_penalty_context(bon_commande)`
- **Ce qui est vérifié**: 
  - Calcul des jours de retard
  - Application du taux de pénalité (0.05% par jour)
  - Calcul du montant total
- **Pourquoi**: Les pénalités doivent être exactes
- **Exemple**: 10 jours × 0.05% × 10000€ = 50€
- **Résultat**: ✅ RÉUSSI - Les calculs sont corrects

**Test 20: Authentification requise**
- **Décorateur testé**: `@login_required`
- **Ce qui est vérifié**: Redirection si non connecté
- **Pourquoi**: Sécurité - seuls les utilisateurs autorisés
- **Résultat**: ✅ RÉUSSI - Redirection vers login

**Test 21: Bon inexistant (404)**
- **Cas d'erreur testé**: bon_id qui n'existe pas
- **Ce qui est vérifié**: Retourne une erreur 404
- **Pourquoi**: Gestion propre des erreurs
- **Résultat**: ✅ RÉUSSI - Erreur 404 retournée

**Test 22: Méthode non autorisée (405)**
- **Cas testé**: Appel avec PUT ou DELETE
- **Ce qui est vérifié**: Retourne une erreur 405
- **Pourquoi**: Seuls GET et POST sont autorisés
- **Résultat**: ✅ RÉUSSI - Erreur 405 retournée

**Test 23: Envoi d'email asynchrone**
- **Fonction testée**: `send_penalty_notification()`
- **Ce qui est vérifié**: 
  - Email envoyé aux superusers
  - PDF en pièce jointe
  - Utilisateur en copie
- **Pourquoi**: Notifier les responsables
- **Résultat**: ✅ RÉUSSI - Email envoyé correctement

#### test_delay_evaluation_api.py

**Fichier**: `orders/tests/test_delay_evaluation_api.py`  
**Nombre de tests**: ~12 tests  
**Objectif**: Tester l'API d'évaluation des délais

**Test 24: Génération du PDF d'évaluation**
- **Fonction testée**: `generate_delay_evaluation_api(request, bon_id)`
- **Ce qui est vérifié**: PDF généré avec les délais
- **Pourquoi**: Document d'analyse des retards
- **Résultat**: ✅ RÉUSSI

**Test 25: Calcul des délais par responsable**
- **Fonction testée**: `collect_delay_evaluation_context()`
- **Ce qui est vérifié**: 
  - Délai MTN
  - Délai Force Majeure
  - Délai Fournisseur
  - Total des délais
- **Pourquoi**: Identifier les responsabilités
- **Résultat**: ✅ RÉUSSI - Les délais sont corrects

**Test 26: Calcul du pourcentage de responsabilité**
- **Formule testée**: (délai_partie / délai_total) × 100
- **Ce qui est vérifié**: Répartition en pourcentages
- **Exemple**: 5j MTN + 3j FM + 2j Vendor = 50% + 30% + 20%
- **Résultat**: ✅ RÉUSSI - Les pourcentages sont exacts

#### test_compensation_letter_api.py

**Fichier**: `orders/tests/test_compensation_letter_api.py`  
**Nombre de tests**: ~10 tests  
**Objectif**: Tester l'API de lettre de compensation

**Test 27: Génération de la lettre**
- **Fonction testée**: `generate_compensation_letter_api()`
- **Ce qui est vérifié**: PDF de lettre officielle
- **Pourquoi**: Document contractuel de demande
- **Résultat**: ✅ RÉUSSI

**Test 28: Calcul du montant de compensation**
- **Fonction testée**: Calcul basé sur les pénalités
- **Ce qui est vérifié**: Montant = pénalités dues
- **Pourquoi**: Demander le remboursement exact
- **Résultat**: ✅ RÉUSSI

#### test_msrn_api.py

**Fichier**: `orders/tests/test_msrn_api.py`  
**Nombre de tests**: ~18 tests  
**Objectif**: Tester l'API de génération MSRN

**Test 29: Génération du rapport MSRN**
- **Fonction testée**: `generate_msrn_report_api()`
- **Ce qui est vérifié**: 
  - PDF généré
  - Numéro MSRN unique
  - Fichier sauvegardé
  - Retour JSON avec download_url
- **Pourquoi**: Document officiel de réception
- **Résultat**: ✅ RÉUSSI

**Test 30: Application de la rétention**
- **Fonction testée**: Calcul avec retention_rate
- **Ce qui est vérifié**: 
  - Rétention appliquée sur chaque ligne
  - Montant payable = montant reçu × (1 - rétention)
- **Exemple**: 1000€ avec 5% rétention = 950€ payable
- **Résultat**: ✅ RÉUSSI

**Test 31: Validation du taux de rétention**
- **Validation testée**: retention_rate ≤ 10%
- **Ce qui est vérifié**: Erreur 400 si > 10%
- **Pourquoi**: Limite contractuelle
- **Résultat**: ✅ RÉUSSI - Erreur retournée

**Test 32: Cause obligatoire si rétention**
- **Validation testée**: retention_cause requis si rate > 0
- **Ce qui est vérifié**: Erreur 400 si cause manquante
- **Pourquoi**: Justifier toute rétention
- **Résultat**: ✅ RÉUSSI

---

**FIN DE LA PARTIE 1**

*Suite dans RAPPORT_DETAILLE_TESTS_PARTIE2.md*
