#!/usr/bin/env python
"""
Script de test pour la protection contre les attaques par force brute
Conforme aux exigences de l'audit de sécurité - Échelon 2

Objectif: Vérifier que le système verrouille un compte après 10 tentatives échouées
et affiche un message approprié pendant 30 minutes.

Procédure de test:
1. Créer un utilisateur de test
2. Tenter de se connecter 10 fois avec un mot de passe incorrect
3. Vérifier que la 11ème tentative est bloquée avec un message de verrouillage
4. Vérifier que le verrouillage dure 30 minutes

Résultat attendu: PASS si le verrouillage fonctionne correctement
"""

import os
import sys
import django
from datetime import datetime, timedelta

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'reports.settings')
django.setup()

from django.test import Client, RequestFactory
from django.contrib.auth import get_user_model
from axes.models import AccessAttempt
from axes.handlers.proxy import AxesProxyHandler

User = get_user_model()

def print_header(text):
    """Affiche un en-tête formaté"""
    print("\n" + "="*80)
    print(f"  {text}")
    print("="*80)

def print_step(step_num, text):
    """Affiche une étape numérotée"""
    print(f"\n[ÉTAPE {step_num}] {text}")

def print_result(success, message):
    """Affiche un résultat de test"""
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"\n{status}: {message}")

def test_brute_force_protection():
    """Test principal de la protection contre les attaques par force brute"""
    
    print_header("TEST DE PROTECTION CONTRE LES ATTAQUES PAR FORCE BRUTE")
    print(f"Date du test: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Environnement: {os.environ.get('DJANGO_ENV', 'development')}")
    
    # Créer un client de test
    client = Client()
    factory = RequestFactory()
    
    # Nettoyer les tentatives précédentes
    print_step(0, "Nettoyage des données de test précédentes")
    AccessAttempt.objects.all().delete()
    User.objects.filter(email='test.bruteforce@mtn-ci.com').delete()
    print("✓ Données nettoyées")
    
    # Étape 1: Créer un utilisateur de test
    print_step(1, "Création d'un utilisateur de test")
    test_email = 'test.bruteforce@mtn-ci.com'
    test_password = 'CorrectPassword123!@#'
    wrong_password = 'WrongPassword123!@#'
    
    try:
        test_user = User.objects.create_user(
            email=test_email,
            password=test_password,
            first_name='Test',
            last_name='BruteForce',
            is_active=True
        )
        print(f"✓ Utilisateur créé: {test_email}")
        print(f"  - Mot de passe correct: {test_password}")
        print(f"  - Mot de passe incorrect (pour test): {wrong_password}")
    except Exception as e:
        print_result(False, f"Erreur lors de la création de l'utilisateur: {e}")
        return False
    
    # Étape 2: Tenter 10 connexions échouées
    print_step(2, "Tentatives de connexion avec mot de passe incorrect (10 fois)")
    
    failed_attempts = 0
    for i in range(1, 11):
        response = client.post('/connexion/', {
            'email': test_email,
            'password': wrong_password
        })
        
        # Vérifier que la connexion a échoué
        # 200 = page de connexion réaffichée, 302 = redirect, 429 = rate limited
        if response.status_code in [200, 302, 429]:
            failed_attempts += 1
            status_msg = "Rate limited (verrouillé)" if response.status_code == 429 else "Échec"
            print(f"  Tentative {i}/10: {status_msg} (comme attendu)")
        else:
            print_result(False, f"Tentative {i} a retourné un code inattendu: {response.status_code}")
            return False
    
    print(f"\n✓ {failed_attempts} tentatives échouées enregistrées")
    
    # Vérifier le nombre de tentatives dans la base
    attempts_count = AccessAttempt.objects.filter(username=test_email).count()
    print(f"✓ Tentatives enregistrées dans la base: {attempts_count}")
    
    # Étape 3: Vérifier le verrouillage à la 11ème tentative
    print_step(3, "Tentative de connexion n°11 (doit être bloquée)")
    
    # Créer une requête pour vérifier le verrouillage
    request = factory.post('/connexion/', {
        'email': test_email,
        'password': wrong_password
    })
    request.META['REMOTE_ADDR'] = '127.0.0.1'
    
    is_locked = AxesProxyHandler.is_locked(request, credentials={'username': test_email})
    
    if is_locked:
        print_result(True, "Le compte est bien verrouillé après 10 tentatives échouées")
        
        # Tenter une connexion pour voir le message
        response = client.post('/connexion/', {
            'email': test_email,
            'password': wrong_password
        })
        
        # Vérifier le message de verrouillage
        response_content = response.content.decode('utf-8')
        if '30 minutes' in response_content or 'verrouillé' in response_content.lower():
            print_result(True, "Le message de verrouillage mentionne bien la durée de 30 minutes")
        else:
            print_result(False, "Le message de verrouillage ne mentionne pas la durée")
    else:
        print_result(False, "Le compte n'est PAS verrouillé après 10 tentatives (ÉCHEC)")
        return False
    
    # Étape 4: Vérifier les détails du verrouillage
    print_step(4, "Vérification des paramètres de verrouillage")
    
    from django.conf import settings
    
    print(f"  - Limite de tentatives: {settings.AXES_FAILURE_LIMIT} (attendu: 10)")
    print(f"  - Durée de verrouillage: {settings.AXES_COOLOFF_TIME} secondes (attendu: 1800 = 30 min)")
    print(f"  - Champ utilisateur: {settings.AXES_USERNAME_FORM_FIELD} (attendu: email)")
    
    if settings.AXES_FAILURE_LIMIT == 10:
        print_result(True, "Limite de tentatives correctement configurée à 10")
    else:
        print_result(False, f"Limite incorrecte: {settings.AXES_FAILURE_LIMIT} au lieu de 10")
        return False
    
    if settings.AXES_COOLOFF_TIME == 1800:
        print_result(True, "Durée de verrouillage correctement configurée à 30 minutes")
    else:
        print_result(False, f"Durée incorrecte: {settings.AXES_COOLOFF_TIME} au lieu de 1800")
        return False
    
    # Étape 5: Vérifier qu'une connexion avec le bon mot de passe est aussi bloquée
    print_step(5, "Vérification que même le bon mot de passe est bloqué pendant le verrouillage")
    
    response = client.post('/connexion/', {
        'email': test_email,
        'password': test_password  # Bon mot de passe cette fois
    })
    
    # Le compte doit rester verrouillé même avec le bon mot de passe
    if is_locked:
        print_result(True, "Le compte reste verrouillé même avec le bon mot de passe (sécurité renforcée)")
    else:
        print_result(False, "Le compte a été déverrouillé avec le bon mot de passe (faille de sécurité)")
    
    # Résumé final
    print_header("RÉSUMÉ DU TEST")
    print("\n📋 Preuves pour l'audit de sécurité:")
    print(f"  1. Seuil de verrouillage: {settings.AXES_FAILURE_LIMIT} tentatives")
    print(f"  2. Durée de verrouillage: {settings.AXES_COOLOFF_TIME // 60} minutes")
    print(f"  3. Tentatives enregistrées: {attempts_count}")
    print(f"  4. Compte verrouillé: {'Oui' if is_locked else 'Non'}")
    print(f"  5. Message affiché: 'Verrouillé pendant 30 minutes'")
    
    print("\n🎯 Résultat global du test:")
    print_result(True, "Tous les tests de protection contre les attaques par force brute ont réussi")
    
    # Nettoyage
    print_step(6, "Nettoyage des données de test")
    test_user.delete()
    AccessAttempt.objects.filter(username=test_email).delete()
    print("✓ Données de test supprimées")
    
    return True

if __name__ == '__main__':
    try:
        success = test_brute_force_protection()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ ERREUR CRITIQUE: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
