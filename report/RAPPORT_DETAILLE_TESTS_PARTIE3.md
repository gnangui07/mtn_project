# RAPPORT DÉTAILLÉ DES TESTS - PARTIE 3
## Suite des Tests ORDERS et Tests USERS

---

### 3.7 TESTS DES RAPPORTS PDF (6 fichiers)

#### test_penalty_report.py

**Fichier**: `orders/tests/test_penalty_report.py`  
**Nombre de tests**: ~15 tests  
**Objectif**: Tester la génération du PDF de pénalité

**Test 93: Génération du PDF**
- **Fonction testée**: `generate_penalty_report(bon_commande, context, user_email)`
- **Ce qui est vérifié**: 
  - PDF généré en mémoire (BytesIO)
  - Format PDF valide
  - Taille > 0
- **Pourquoi**: Document contractuel critique
- **Résultat**: ✅ RÉUSSI

**Test 94: En-tête du document**
- **Élément testé**: Header avec logo et titre
- **Ce qui est vérifié**: 
  - Logo MTN présent
  - Titre "FICHE DE PÉNALITÉ"
  - Numéro PO affiché
- **Pourquoi**: Identification du document
- **Résultat**: ✅ RÉUSSI

**Test 95: Informations du bon**
- **Section testée**: Bloc d'informations
- **Ce qui est vérifié**: 
  - Numéro PO
  - Fournisseur
  - Date de commande
  - Date de livraison prévue
  - Date de livraison réelle
- **Pourquoi**: Contexte complet
- **Résultat**: ✅ RÉUSSI

**Test 96: Tableau des pénalités**
- **Élément testé**: Tableau avec calculs
- **Ce qui est vérifié**: 
  - Colonnes: Description, Jours, Taux, Montant
  - Calculs affichés
  - Total des pénalités
- **Pourquoi**: Détail des calculs
- **Résultat**: ✅ RÉUSSI

**Test 97: Formatage des montants**
- **Format testé**: Affichage des montants en FCFA
- **Ce qui est vérifié**: 
  - Séparateur de milliers
  - 2 décimales
  - Symbole FCFA
- **Exemple**: 1500000.50 → 1 500 000,50 FCFA
- **Résultat**: ✅ RÉUSSI

**Test 98: Pied de page**
- **Élément testé**: Footer du document
- **Ce qui est vérifié**: 
  - Date de génération
  - Utilisateur qui a généré
  - Numéro de page
- **Pourquoi**: Traçabilité
- **Résultat**: ✅ RÉUSSI

**Test 99: Gestion des valeurs nulles**
- **Cas testé**: Champs optionnels vides
- **Ce qui est vérifié**: 
  - Pas d'erreur si données manquantes
  - Affichage "N/A" ou "-"
- **Pourquoi**: Robustesse
- **Résultat**: ✅ RÉUSSI

#### test_delay_evaluation_report.py

**Fichier**: `orders/tests/test_delay_evaluation_report.py`  
**Nombre de tests**: ~12 tests  
**Objectif**: Tester la génération du PDF d'évaluation des délais

**Test 100: Génération du PDF**
- **Fonction testée**: `generate_delay_evaluation_report()`
- **Ce qui est vérifié**: PDF généré correctement
- **Pourquoi**: Document d'analyse
- **Résultat**: ✅ RÉUSSI

**Test 101: Graphique des délais**
- **Élément testé**: Graphique en barres
- **Ce qui est vérifié**: 
  - 3 barres (MTN, FM, Vendor)
  - Hauteurs proportionnelles
  - Légende présente
- **Pourquoi**: Visualisation des responsabilités
- **Résultat**: ✅ RÉUSSI

**Test 102: Tableau de répartition**
- **Élément testé**: Tableau avec pourcentages
- **Ce qui est vérifié**: 
  - Délais en jours
  - Pourcentages calculés
  - Total = 100%
- **Pourquoi**: Détail chiffré
- **Résultat**: ✅ RÉUSSI

**Test 103: Section commentaires**
- **Élément testé**: Zone de commentaires
- **Ce qui est vérifié**: 
  - Commentaire MTN affiché
  - Commentaire FM affiché
  - Commentaire Vendor affiché
- **Pourquoi**: Justifications des délais
- **Résultat**: ✅ RÉUSSI

**Test 104: Quotité réalisée**
- **Élément testé**: Affichage du pourcentage réalisé
- **Ce qui est vérifié**: 
  - Valeur affichée
  - Format: XX.XX%
- **Pourquoi**: Avancement du projet
- **Résultat**: ✅ RÉUSSI

#### test_compensation_letter_report.py

**Fichier**: `orders/tests/test_compensation_letter_report.py`  
**Nombre de tests**: ~10 tests  
**Objectif**: Tester la génération de la lettre de compensation

**Test 105: Format lettre officielle**
- **Fonction testée**: `generate_compensation_letter()`
- **Ce qui est vérifié**: 
  - Format lettre (en-tête, corps, signature)
  - Ton formel
  - Structure correcte
- **Pourquoi**: Document contractuel
- **Résultat**: ✅ RÉUSSI

**Test 106: Destinataire**
- **Élément testé**: Bloc destinataire
- **Ce qui est vérifié**: 
  - Nom du fournisseur
  - Adresse si disponible
  - Formule de politesse
- **Pourquoi**: Identification du destinataire
- **Résultat**: ✅ RÉUSSI

**Test 107: Objet de la lettre**
- **Élément testé**: Ligne "Objet:"
- **Ce qui est vérifié**: 
  - Mention du PO
  - Mention de la compensation
- **Pourquoi**: Clarté du sujet
- **Résultat**: ✅ RÉUSSI

**Test 108: Corps de la lettre**
- **Élément testé**: Texte principal
- **Ce qui est vérifié**: 
  - Contexte du retard
  - Montant de compensation demandé
  - Références contractuelles
- **Pourquoi**: Justification de la demande
- **Résultat**: ✅ RÉUSSI

**Test 109: Signature**
- **Élément testé**: Bloc signature
- **Ce qui est vérifié**: 
  - Nom du signataire
  - Fonction
  - Date
- **Pourquoi**: Validation officielle
- **Résultat**: ✅ RÉUSSI

#### test_penalty_amendment_report.py

**Fichier**: `orders/tests/test_penalty_amendment_report.py`  
**Nombre de tests**: ~8 tests  
**Objectif**: Tester la fiche d'amendement de pénalité

**Test 110: Génération de l'amendement**
- **Fonction testée**: `generate_penalty_amendment_report()`
- **Ce qui est vérifié**: PDF généré
- **Pourquoi**: Modifier une pénalité existante
- **Résultat**: ✅ RÉUSSI

**Test 111: Référence à la pénalité originale**
- **Élément testé**: Lien avec pénalité initiale
- **Ce qui est vérifié**: 
  - Numéro de la pénalité originale
  - Date de la pénalité originale
  - Montant initial
- **Pourquoi**: Traçabilité
- **Résultat**: ✅ RÉUSSI

**Test 112: Nouveau montant**
- **Élément testé**: Montant amendé
- **Ce qui est vérifié**: 
  - Nouveau montant affiché
  - Différence calculée
  - Justification de l'amendement
- **Pourquoi**: Transparence des modifications
- **Résultat**: ✅ RÉUSSI

#### test_reports.py (Général)

**Fichier**: `orders/tests/test_reports.py`  
**Nombre de tests**: ~10 tests  
**Objectif**: Tests généraux des rapports

**Test 113: Palette de couleurs**
- **Élément testé**: Couleurs utilisées dans les PDFs
- **Ce qui est vérifié**: 
  - Couleurs cohérentes (bleu professionnel)
  - Contraste suffisant
  - Lisibilité
- **Pourquoi**: Identité visuelle
- **Résultat**: ✅ RÉUSSI

**Test 114: Polices de caractères**
- **Élément testé**: Fonts utilisées
- **Ce qui est vérifié**: 
  - Police professionnelle
  - Tailles appropriées
  - Gras pour les titres
- **Pourquoi**: Lisibilité
- **Résultat**: ✅ RÉUSSI

**Test 115: Marges et mise en page**
- **Élément testé**: Layout du document
- **Ce qui est vérifié**: 
  - Marges correctes
  - Espacement cohérent
  - Pas de débordement
- **Pourquoi**: Présentation professionnelle
- **Résultat**: ✅ RÉUSSI

---

### 3.8 TESTS DES FORMULAIRES (test_forms.py)

**Fichier**: `orders/tests/test_forms.py`  
**Nombre de tests**: ~18 tests  
**Objectif**: Tester les formulaires de saisie

#### Formulaire d'évaluation fournisseur

**Test 116: Validation du formulaire**
- **Formulaire testé**: `VendorEvaluationForm`
- **Ce qui est vérifié**: 
  - Tous les champs requis présents
  - Validation des types
- **Pourquoi**: Données cohérentes
- **Résultat**: ✅ RÉUSSI

**Test 117: Validation des notes (1-10)**
- **Validation testée**: Chaque critère entre 1 et 10
- **Ce qui est vérifié**: 
  - Erreur si < 1
  - Erreur si > 10
  - Accepte 1 à 10
- **Pourquoi**: Échelle standardisée
- **Résultat**: ✅ RÉUSSI

**Test 118: Champs obligatoires**
- **Validation testée**: Champs requis
- **Ce qui est vérifié**: 
  - Erreur si champ vide
  - Message d'erreur clair
- **Pourquoi**: Données complètes
- **Résultat**: ✅ RÉUSSI

#### Formulaire de délais timeline

**Test 119: Validation du formulaire**
- **Formulaire testé**: `TimelineDelayForm`
- **Ce qui est vérifié**: 
  - 3 champs de délais
  - Champs commentaires
  - Quotité réalisée
- **Pourquoi**: Saisie des délais
- **Résultat**: ✅ RÉUSSI

**Test 120: Validation des nombres**
- **Validation testée**: Délais en jours (entiers positifs)
- **Ce qui est vérifié**: 
  - Erreur si négatif
  - Erreur si non-numérique
- **Pourquoi**: Données valides
- **Résultat**: ✅ RÉUSSI

**Test 121: Quotité entre 0 et 100**
- **Validation testée**: Pourcentage valide
- **Ce qui est vérifié**: 
  - Erreur si < 0
  - Erreur si > 100
- **Pourquoi**: Pourcentage cohérent
- **Résultat**: ✅ RÉUSSI

#### Formulaire d'import de fichier

**Test 122: Validation du fichier**
- **Formulaire testé**: `FileImportForm`
- **Ce qui est vérifié**: 
  - Extensions autorisées (.xlsx, .csv)
  - Taille maximale
- **Pourquoi**: Sécurité
- **Résultat**: ✅ RÉUSSI

**Test 123: Rejet des formats invalides**
- **Validation testée**: Extension du fichier
- **Ce qui est vérifié**: 
  - Erreur si .pdf, .exe, etc.
  - Message d'erreur explicite
- **Pourquoi**: Sécurité
- **Résultat**: ✅ RÉUSSI

---

### 3.9 TESTS DES SIGNAUX (test_signals.py)

**Fichier**: `orders/tests/test_signals.py`  
**Nombre de tests**: ~8 tests  
**Objectif**: Tester les signaux Django

**Test 124: Signal post_save sur Reception**
- **Signal testé**: Création automatique d'ActivityLog
- **Ce qui est vérifié**: 
  - Log créé automatiquement
  - Données correctes dans le log
- **Pourquoi**: Traçabilité automatique
- **Résultat**: ✅ RÉUSSI

**Test 125: Signal pre_delete sur FichierImporte**
- **Signal testé**: Archivage avant suppression
- **Ce qui est vérifié**: 
  - Données archivées
  - Fichier physique supprimé
- **Pourquoi**: Pas de perte de données
- **Résultat**: ✅ RÉUSSI

**Test 126: Signal post_save sur MSRNReport**
- **Signal testé**: Mise à jour du bon de commande
- **Ce qui est vérifié**: 
  - Taux de rétention mis à jour sur le bon
  - Date MSRN enregistrée
- **Pourquoi**: Synchronisation des données
- **Résultat**: ✅ RÉUSSI

---

### 3.10 TESTS DES URLs (test_urls.py)

**Fichier**: `orders/tests/test_urls.py`  
**Nombre de tests**: ~15 tests  
**Objectif**: Tester le routage des URLs

**Test 127: URL de l'accueil**
- **URL testée**: `/orders/`
- **Ce qui est vérifié**: 
  - Route vers la bonne vue
  - Nom correct: 'orders:accueil'
- **Pourquoi**: Navigation correcte
- **Résultat**: ✅ RÉUSSI

**Test 128: URLs des APIs**
- **URLs testées**: 
  - `/orders/api/penalty/<id>/`
  - `/orders/api/msrn/<id>/`
  - `/orders/api/receptions/`
- **Ce qui est vérifié**: Routes correctes
- **Pourquoi**: APIs accessibles
- **Résultat**: ✅ RÉUSSI

**Test 129: URLs avec paramètres**
- **Pattern testé**: `<int:bon_id>`
- **Ce qui est vérifié**: 
  - Paramètre extrait correctement
  - Type validé (int)
- **Pourquoi**: Passage de paramètres
- **Résultat**: ✅ RÉUSSI

---

### 3.11 TESTS DES EMAILS (test_emails.py)

**Fichier**: `orders/tests/test_emails.py`  
**Nombre de tests**: ~12 tests  
**Objectif**: Tester l'envoi d'emails

**Test 130: Envoi email de notification**
- **Fonction testée**: `send_penalty_notification()`
- **Ce qui est vérifié**: 
  - Email envoyé
  - Destinataires corrects (superusers)
  - CC: utilisateur
- **Pourquoi**: Notifications automatiques
- **Résultat**: ✅ RÉUSSI

**Test 131: Pièce jointe PDF**
- **Élément testé**: Attachement du PDF
- **Ce qui est vérifié**: 
  - PDF attaché
  - Nom de fichier correct
  - Content-Type correct
- **Pourquoi**: Document joint
- **Résultat**: ✅ RÉUSSI

**Test 132: Sujet de l'email**
- **Élément testé**: Subject de l'email
- **Ce qui est vérifié**: 
  - Format: "Type de rapport - PO Numéro"
  - Informations correctes
- **Pourquoi**: Identification rapide
- **Résultat**: ✅ RÉUSSI

**Test 133: Corps de l'email**
- **Élément testé**: Body de l'email
- **Ce qui est vérifié**: 
  - Informations du rapport
  - Date et heure
  - Lien de téléchargement si applicable
- **Pourquoi**: Contexte complet
- **Résultat**: ✅ RÉUSSI

**Test 134: Gestion des erreurs d'envoi**
- **Cas testé**: Échec d'envoi (serveur SMTP down)
- **Ce qui est vérifié**: 
  - Exception capturée
  - Pas de blocage du processus
  - Log de l'erreur
- **Pourquoi**: Robustesse
- **Résultat**: ✅ RÉUSSI

---

## 4. TESTS DE L'APPLICATION USERS

### 4.1 TESTS DES MODÈLES USERS (test_models.py)

**Fichier**: `users/tests/test_models.py`  
**Nombre de tests**: ~25 tests  
**Objectif**: Tester le modèle utilisateur personnalisé

**Test 135: Création d'un utilisateur**
- **Méthode testée**: `User.objects.create_user()`
- **Ce qui est vérifié**: 
  - Utilisateur créé
  - Email comme username
  - Mot de passe hashé
- **Pourquoi**: Authentification par email
- **Résultat**: ✅ RÉUSSI

**Test 136: Création d'un superuser**
- **Méthode testée**: `User.objects.create_superuser()`
- **Ce qui est vérifié**: 
  - is_superuser = True
  - is_staff = True
  - Tous les droits
- **Pourquoi**: Compte administrateur
- **Résultat**: ✅ RÉUSSI

**Test 137: Validation de l'email**
- **Validation testée**: Format email
- **Ce qui est vérifié**: 
  - Email valide accepté
  - Email invalide rejeté
- **Pourquoi**: Données cohérentes
- **Résultat**: ✅ RÉUSSI

**Test 138: Unicité de l'email**
- **Contrainte testée**: Email unique
- **Ce qui est vérifié**: 
  - Impossible de créer deux users avec même email
  - Erreur levée
- **Pourquoi**: Pas de doublons
- **Résultat**: ✅ RÉUSSI

**Test 139: Génération du token d'activation**
- **Méthode testée**: `user.generate_activation_token()`
- **Ce qui est vérifié**: 
  - Token généré
  - Token unique
  - Format correct
- **Pourquoi**: Activation de compte
- **Résultat**: ✅ RÉUSSI

**Test 140: Validation du token**
- **Méthode testée**: `user.validate_activation_token(token)`
- **Ce qui est vérifié**: 
  - Token valide accepté
  - Token invalide rejeté
  - Token expiré rejeté
- **Pourquoi**: Sécurité
- **Résultat**: ✅ RÉUSSI

**Test 141: Génération mot de passe temporaire**
- **Méthode testée**: `user.generate_temporary_password()`
- **Ce qui est vérifié**: 
  - Mot de passe généré
  - Complexité suffisante
  - Hashé correctement
- **Pourquoi**: Réinitialisation sécurisée
- **Résultat**: ✅ RÉUSSI

**Test 142: Méthode get_full_name**
- **Méthode testée**: `user.get_full_name()`
- **Ce qui est vérifié**: 
  - Retourne "Prénom Nom"
  - Gère les champs vides
- **Pourquoi**: Affichage du nom
- **Résultat**: ✅ RÉUSSI

**Test 143: Méthode get_short_name**
- **Méthode testée**: `user.get_short_name()`
- **Ce qui est vérifié**: Retourne le prénom
- **Pourquoi**: Affichage court
- **Résultat**: ✅ RÉUSSI

**Test 144: Champ CPU (service)**
- **Champ testé**: `user.cpu`
- **Ce qui est vérifié**: 
  - Choix limités (ITS, RAN, etc.)
  - Validation des valeurs
- **Pourquoi**: Filtrage par service
- **Résultat**: ✅ RÉUSSI

**Test 145: Préférences vocales**
- **Champ testé**: `user.voice_preference`
- **Ce qui est vérifié**: 
  - Choix de langue (fr, en)
  - Valeur par défaut
- **Pourquoi**: Notifications vocales
- **Résultat**: ✅ RÉUSSI

---

### 4.2 TESTS DES VUES USERS (test_views.py)

**Fichier**: `users/tests/test_views.py`  
**Nombre de tests**: ~35 tests  
**Objectif**: Tester l'authentification et les vues utilisateur

#### Tests de connexion

**Test 146: Affichage du formulaire de login**
- **Vue testée**: `login_view(request)` avec GET
- **Ce qui est vérifié**: 
  - Page de login affichée
  - Formulaire présent
  - Template correct
- **Pourquoi**: Interface de connexion
- **Résultat**: ✅ RÉUSSI

**Test 147: Connexion réussie**
- **Vue testée**: `login_view(request)` avec POST
- **Ce qui est vérifié**: 
  - Authentification réussie
  - Session créée
  - Redirection vers accueil
  - Message de bienvenue
- **Pourquoi**: Accès au système
- **Résultat**: ✅ RÉUSSI

**Test 148: Connexion avec mauvais mot de passe**
- **Cas d'erreur testé**: Mot de passe incorrect
- **Ce qui est vérifié**: 
  - Authentification échouée
  - Message d'erreur affiché
  - Reste sur la page de login
- **Pourquoi**: Sécurité
- **Résultat**: ✅ RÉUSSI

**Test 149: Connexion avec email inexistant**
- **Cas d'erreur testé**: Email non enregistré
- **Ce qui est vérifié**: 
  - Authentification échouée
  - Message d'erreur
- **Pourquoi**: Sécurité
- **Résultat**: ✅ RÉUSSI

**Test 150: Connexion compte inactif**
- **Cas testé**: is_active = False
- **Ce qui est vérifié**: 
  - Connexion refusée
  - Message: "Compte non activé"
- **Pourquoi**: Validation du compte
- **Résultat**: ✅ RÉUSSI

**Test 151: Redirection après login**
- **Paramètre testé**: `?next=/orders/consultation/`
- **Ce qui est vérifié**: 
  - Redirection vers l'URL demandée
  - Pas vers l'accueil
- **Pourquoi**: UX - retour à la page voulue
- **Résultat**: ✅ RÉUSSI

#### Tests de déconnexion

**Test 152: Déconnexion**
- **Vue testée**: `logout_view(request)`
- **Ce qui est vérifié**: 
  - Session détruite
  - Redirection vers login
  - Message de confirmation
- **Pourquoi**: Sécurité
- **Résultat**: ✅ RÉUSSI

**Test 153: Accès après déconnexion**
- **Cas testé**: Accès à une page protégée après logout
- **Ce qui est vérifié**: 
  - Redirection vers login
  - Session invalide
- **Pourquoi**: Sécurité
- **Résultat**: ✅ RÉUSSI

#### Tests d'activation de compte

**Test 154: Page d'activation**
- **Vue testée**: `activate_account(request, token)`
- **Ce qui est vérifié**: 
  - Token validé
  - Compte activé (is_active = True)
  - Message de succès
  - Redirection vers login
- **Pourquoi**: Validation email
- **Résultat**: ✅ RÉUSSI

**Test 155: Token invalide**
- **Cas d'erreur testé**: Token incorrect
- **Ce qui est vérifié**: 
  - Activation échouée
  - Message d'erreur
  - Compte reste inactif
- **Pourquoi**: Sécurité
- **Résultat**: ✅ RÉUSSI

**Test 156: Token expiré**
- **Cas testé**: Token > 24h
- **Ce qui est vérifié**: 
  - Activation refusée
  - Message: "Token expiré"
- **Pourquoi**: Sécurité
- **Résultat**: ✅ RÉUSSI

#### Tests de réinitialisation mot de passe

**Test 157: Demande de réinitialisation**
- **Vue testée**: `password_reset_request(request)`
- **Ce qui est vérifié**: 
  - Email envoyé
  - Token généré
  - Lien de réinitialisation
- **Pourquoi**: Récupération de compte
- **Résultat**: ✅ RÉUSSI

**Test 158: Réinitialisation avec token**
- **Vue testée**: `password_reset_confirm(request, token)`
- **Ce qui est vérifié**: 
  - Nouveau mot de passe accepté
  - Ancien mot de passe invalide
  - Connexion possible avec nouveau
- **Pourquoi**: Changement de mot de passe
- **Résultat**: ✅ RÉUSSI

---

### 4.3 TESTS DES PERMISSIONS (test_permissions.py)

**Fichier**: `users/tests/test_permissions.py`  
**Nombre de tests**: ~15 tests  
**Objectif**: Tester les permissions et autorisations

**Test 159: Permission superuser**
- **Permission testée**: Accès admin
- **Ce qui est vérifié**: 
  - Superuser accède à tout
  - Utilisateur normal refusé
- **Pourquoi**: Sécurité
- **Résultat**: ✅ RÉUSSI

**Test 160: Filtrage par service**
- **Permission testée**: Accès aux données du service
- **Ce qui est vérifié**: 
  - User ITS voit uniquement ITS
  - User RAN voit uniquement RAN
  - Superuser voit tout
- **Pourquoi**: Confidentialité
- **Résultat**: ✅ RÉUSSI

**Test 161: Permission de modification**
- **Permission testée**: Modification des données
- **Ce qui est vérifié**: 
  - User peut modifier ses données
  - User ne peut pas modifier autres services
- **Pourquoi**: Intégrité des données
- **Résultat**: ✅ RÉUSSI

**Test 162: Permission d'export**
- **Permission testée**: Export de données
- **Ce qui est vérifié**: 
  - User exporte son service
  - Superuser exporte tout
- **Pourquoi**: Sécurité des données
- **Résultat**: ✅ RÉUSSI

---

### 4.4 TESTS DE L'ADMINISTRATION (test_admin.py)

**Fichier**: `users/tests/test_admin.py`  
**Nombre de tests**: ~10 tests  
**Objectif**: Tester l'interface d'administration

**Test 163: Liste des utilisateurs**
- **Vue testée**: Admin list view
- **Ce qui est vérifié**: 
  - Tous les users affichés
  - Colonnes correctes
  - Filtres disponibles
- **Pourquoi**: Gestion des users
- **Résultat**: ✅ RÉUSSI

**Test 164: Recherche d'utilisateur**
- **Fonction testée**: Barre de recherche admin
- **Ce qui est vérifié**: 
  - Recherche par email
  - Recherche par nom
- **Pourquoi**: Trouver rapidement
- **Résultat**: ✅ RÉUSSI

**Test 165: Modification en masse**
- **Action testée**: Activer/désactiver plusieurs users
- **Ce qui est vérifié**: 
  - Action appliquée à tous sélectionnés
  - Message de confirmation
- **Pourquoi**: Gestion efficace
- **Résultat**: ✅ RÉUSSI

---

**FIN DE LA PARTIE 3**

*Suite dans RAPPORT_DETAILLE_TESTS_PARTIE4.md (Tests d'intégration et conclusion)*

**Tests documentés dans cette partie: 73 tests (Test 93 à Test 165)**  
**Total cumulé: 165 tests sur 383**
