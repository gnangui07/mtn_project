# RAPPORT COMPLET DES TESTS - SECTION 2: APIs
## Documentation Exhaustive Sans Omission

---

## TESTS DES APIs - 98 TESTS COMPLETS

### PARTIE A: test_penalty_api.py (15 tests)

**Fichier**: `orders/tests/test_penalty_api.py`

#### Test 141: Génération PDF pénalité - Succès
**Fonction**: `generate_penalty_report_api(request, bon_id=1)`
**Parcours**: User connecté → GET /api/penalty/1/ → PDF généré
**Vérifie**:
- Code HTTP 200
- Content-Type: application/pdf
- Content-Disposition: inline; filename="PenaltySheet-PO001.pdf"
- Header X-Penalty-Due: "5000.00"
- Taille PDF > 0
**Pourquoi**: Document contractuel critique
**Résultat**: ✅ RÉUSSI

#### Test 142: Calcul des pénalités
**Fonction**: `collect_penalty_context(bon_commande)`
**Setup**: Retard de 10 jours, montant 100000€
**Calcul**: 10 jours × 0.05% × 100000€ = 500€
**Vérifie**: penalties_due = 500€
**Pourquoi**: Calcul exact des pénalités
**Résultat**: ✅ RÉUSSI

#### Test 143: Plafond 10%
**Setup**: Retard de 300 jours (calcul > 10%)
**Vérifie**: Pénalité plafonnée à 10% du montant
**Pourquoi**: Limite contractuelle
**Résultat**: ✅ RÉUSSI

#### Test 144: Authentification requise
**Test**: Appel sans connexion
**Vérifie**: Redirection 302 vers /users/login/
**Pourquoi**: Sécurité
**Résultat**: ✅ RÉUSSI

#### Test 145: Bon inexistant
**Test**: GET /api/penalty/999999/
**Vérifie**: 
- Code 404
- JSON: {"success": false, "error": "Bon de commande non trouvé"}
**Pourquoi**: Gestion d'erreur
**Résultat**: ✅ RÉUSSI

#### Test 146: Méthode PUT non autorisée
**Test**: PUT /api/penalty/1/
**Vérifie**: 
- Code 405
- JSON: {"success": false, "error": "Méthode non autorisée"}
**Pourquoi**: Seuls GET et POST autorisés
**Résultat**: ✅ RÉUSSI

#### Test 147: Méthode DELETE non autorisée
**Test**: DELETE /api/penalty/1/
**Vérifie**: Code 405
**Pourquoi**: Validation des méthodes
**Résultat**: ✅ RÉUSSI

#### Test 148: Email envoyé asynchrone
**Fonction**: `send_penalty_notification()`
**Vérifie**:
- Email envoyé aux superusers
- PDF en pièce jointe
- Utilisateur en CC
- Sujet: "Fiche de Pénalité - PO PO001"
**Pourquoi**: Notification automatique
**Résultat**: ✅ RÉUSSI

#### Test 149: Génération sans retard
**Setup**: Livraison dans les délais
**Vérifie**: penalties_due = 0€
**Pourquoi**: Pas de pénalité si respect
**Résultat**: ✅ RÉUSSI

#### Test 150: Calcul jours de retard
**Setup**: Prévu 01/01/2025, Reçu 11/01/2025
**Vérifie**: delay_days = 10
**Pourquoi**: Base du calcul
**Résultat**: ✅ RÉUSSI

#### Test 151: Format du PDF
**Vérifie**:
- Header avec logo MTN
- Titre "FICHE DE PÉNALITÉ"
- Tableau des calculs
- Footer avec date et utilisateur
**Pourquoi**: Document professionnel
**Résultat**: ✅ RÉUSSI

#### Test 152: Données dans le PDF
**Vérifie présence**:
- Numéro PO
- Fournisseur
- Montant commande
- Jours de retard
- Taux de pénalité
- Montant pénalité
**Pourquoi**: Informations complètes
**Résultat**: ✅ RÉUSSI

#### Test 153: Gestion erreur email
**Setup**: Serveur SMTP down
**Vérifie**: 
- PDF quand même retourné
- Erreur loggée
- Pas de blocage
**Pourquoi**: Robustesse
**Résultat**: ✅ RÉUSSI

#### Test 154: Méthode POST identique à GET
**Test**: POST /api/penalty/1/
**Vérifie**: Même résultat que GET
**Pourquoi**: Flexibilité
**Résultat**: ✅ RÉUSSI

#### Test 155: Cache-Control headers
**Vérifie**: 
- Cache-Control: no-cache
- Pragma: no-cache
**Pourquoi**: Toujours données fraîches
**Résultat**: ✅ RÉUSSI

---

### PARTIE B: test_delay_evaluation_api.py (12 tests)

**Fichier**: `orders/tests/test_delay_evaluation_api.py`

#### Test 156: Génération PDF évaluation délais
**Fonction**: `generate_delay_evaluation_api(request, bon_id=1)`
**Vérifie**:
- Code 200
- Content-Type: application/pdf
- PDF généré avec graphique
**Pourquoi**: Analyse des retards
**Résultat**: ✅ RÉUSSI

#### Test 157: Calcul délais par responsable
**Setup**: MTN=5j, FM=3j, Vendor=2j
**Fonction**: `collect_delay_evaluation_context()`
**Vérifie**:
- mtn_delay = 5
- force_majeure_delay = 3
- vendor_delay = 2
- total_delay = 10
**Pourquoi**: Répartition des responsabilités
**Résultat**: ✅ RÉUSSI

#### Test 158: Calcul des pourcentages
**Setup**: Total 10 jours (5+3+2)
**Vérifie**:
- mtn_percentage = 50%
- fm_percentage = 30%
- vendor_percentage = 20%
**Pourquoi**: Visualisation claire
**Résultat**: ✅ RÉUSSI

#### Test 159: Graphique dans le PDF
**Vérifie**:
- 3 barres (MTN, FM, Vendor)
- Hauteurs proportionnelles
- Légende présente
- Couleurs distinctes
**Pourquoi**: Visualisation
**Résultat**: ✅ RÉUSSI

#### Test 160: Commentaires inclus
**Setup**: Commentaires pour chaque partie
**Vérifie**: Tous les commentaires dans le PDF
**Pourquoi**: Justifications
**Résultat**: ✅ RÉUSSI

#### Test 161: Quotité réalisée
**Setup**: quotite_realisee = 75%
**Vérifie**: Affichée dans le PDF
**Pourquoi**: Avancement du projet
**Résultat**: ✅ RÉUSSI

#### Test 162-167: Tests supplémentaires
- Authentification requise
- Bon inexistant (404)
- Méthode non autorisée (405)
- Email envoyé
- Gestion délais nuls
- Format du PDF
**Résultat**: ✅ TOUS RÉUSSIS

---

### PARTIE C: test_compensation_letter_api.py (10 tests)

**Fichier**: `orders/tests/test_compensation_letter_api.py`

#### Test 168: Génération lettre de compensation
**Fonction**: `generate_compensation_letter_api(request, bon_id=1)`
**Vérifie**:
- Code 200
- Content-Type: application/pdf
- Format lettre officielle
**Pourquoi**: Document contractuel
**Résultat**: ✅ RÉUSSI

#### Test 169: Format lettre
**Vérifie**:
- En-tête MTN
- Destinataire (fournisseur)
- Objet de la lettre
- Corps avec justification
- Signature
**Pourquoi**: Document formel
**Résultat**: ✅ RÉUSSI

#### Test 170: Montant de compensation
**Setup**: Pénalités = 5000€
**Vérifie**: Montant demandé = 5000€
**Pourquoi**: Cohérence avec pénalités
**Résultat**: ✅ RÉUSSI

#### Test 171-177: Tests supplémentaires
- Authentification
- Bon inexistant
- Méthode non autorisée
- Email envoyé
- Références contractuelles
- Date de la lettre
- Numéro de référence
**Résultat**: ✅ TOUS RÉUSSIS

---

### PARTIE D: test_msrn_api.py (18 tests)

**Fichier**: `orders/tests/test_msrn_api.py`

#### Test 178: Génération MSRN - Succès
**Fonction**: `generate_msrn_report_api(request, bon_id=1)`
**Méthode**: POST
**Données**: {"retention_rate": 0, "retention_cause": ""}
**Vérifie**:
- Code 200
- JSON: {"success": true, "download_url": "/media/...", "report_number": "MSRN250001"}
- Fichier PDF sauvegardé sur disque
- Entrée MSRNReport en base
**Pourquoi**: Document officiel de réception
**Résultat**: ✅ RÉUSSI

#### Test 179: Génération avec rétention 5%
**Données**: {"retention_rate": 5, "retention_cause": "Garantie"}
**Vérifie**:
- Rétention appliquée sur chaque ligne
- Montant payable = montant reçu × 0.95
- Cause enregistrée
**Pourquoi**: Application de la rétention
**Résultat**: ✅ RÉUSSI

#### Test 180: Validation taux > 10%
**Données**: {"retention_rate": 15}
**Vérifie**:
- Code 400
- JSON: {"success": false, "error": "Taux maximum 10%"}
**Pourquoi**: Limite contractuelle
**Résultat**: ✅ RÉUSSI

#### Test 181: Cause obligatoire si rétention
**Données**: {"retention_rate": 5, "retention_cause": ""}
**Vérifie**:
- Code 400
- JSON: {"error": "Cause obligatoire si rétention"}
**Pourquoi**: Justification requise
**Résultat**: ✅ RÉUSSI

#### Test 182: Bon inexistant
**Test**: POST /api/msrn/999999/
**Vérifie**: Code 404
**Résultat**: ✅ RÉUSSI

#### Test 183: Méthode GET non autorisée
**Test**: GET /api/msrn/1/
**Vérifie**: Code 405
**Pourquoi**: Seul POST autorisé
**Résultat**: ✅ RÉUSSI

#### Test 184: Numéro MSRN unique
**Test**: Génération de 2 MSRN
**Vérifie**: 
- MSRN250001
- MSRN250002
**Pourquoi**: Numérotation séquentielle
**Résultat**: ✅ RÉUSSI

#### Test 185: Format du numéro
**Vérifie**: MSRN + année (2 chiffres) + séquence (4 chiffres)
**Exemple**: MSRN250001
**Pourquoi**: Format standardisé
**Résultat**: ✅ RÉUSSI

#### Test 186: Fichier PDF sauvegardé
**Vérifie**:
- Fichier dans /media/msrn_reports/
- Nom: msrn-report-PO001-MSRN250001.pdf
- Taille > 0
**Pourquoi**: Archivage
**Résultat**: ✅ RÉUSSI

#### Test 187: Contenu du PDF
**Vérifie**:
- Toutes les lignes du bon
- Quantités commandées/reçues
- Montants avec rétention
- Total général
**Pourquoi**: Document complet
**Résultat**: ✅ RÉUSSI

#### Test 188: Email envoyé
**Vérifie**:
- Email aux superusers
- PDF en pièce jointe
- Lien de téléchargement
**Résultat**: ✅ RÉUSSI

#### Test 189-195: Tests supplémentaires
- Authentification requise
- Validation des données JSON
- Gestion des erreurs de sauvegarde
- Rollback en cas d'erreur
- Logs de génération
- Statistiques MSRN
- Export liste MSRN
**Résultat**: ✅ TOUS RÉUSSIS

---

### PARTIE E: test_reception_api.py (20 tests)

**Fichier**: `orders/tests/test_reception_api.py`

#### Test 196: GET réceptions - Succès
**Fonction**: `update_quantity_delivered(request)`
**Méthode**: GET
**Paramètres**: ?bon_number=PO001
**Vérifie**:
- Code 200
- JSON avec clés: bon_number, receptions, ordered_quantity, delivered_quantity
- Données correctes
**Pourquoi**: Afficher les données avant mise à jour
**Résultat**: ✅ RÉUSSI

#### Test 197: GET - Paramètre manquant
**Test**: GET sans bon_number
**Vérifie**:
- Code 400
- JSON: {"error": "Paramètre bon_number requis"}
**Résultat**: ✅ RÉUSSI

#### Test 198: GET - Bon inexistant
**Test**: GET ?bon_number=XXXXX
**Vérifie**: Code 404
**Résultat**: ✅ RÉUSSI

#### Test 199: POST mise à jour - Succès
**Méthode**: POST
**Données**: {"bon_number": "PO001", "receptions": [{"business_id": "...", "quantity": 10}]}
**Vérifie**:
- Code 200
- Quantités mises à jour en base
- Montants recalculés
- ActivityLog créé
**Pourquoi**: Enregistrer les réceptions
**Résultat**: ✅ RÉUSSI

#### Test 200: POST - Validation quantité > commandée
**Données**: Tentative de recevoir 150 alors que 100 commandés
**Vérifie**:
- Code 400
- JSON: {"error": "Quantité dépasse commandée"}
**Pourquoi**: Impossible de recevoir plus
**Résultat**: ✅ RÉUSSI

#### Test 201: POST - Correction négative invalide
**Setup**: 10 déjà reçus
**Données**: Correction de -15
**Vérifie**:
- Code 400
- JSON: {"error": "Total ne peut être négatif"}
**Résultat**: ✅ RÉUSSI

#### Test 202: POST - Correction positive
**Setup**: 10 reçus
**Données**: Correction de +5
**Vérifie**: Total = 15
**Résultat**: ✅ RÉUSSI

#### Test 203: POST - Correction négative valide
**Setup**: 10 reçus
**Données**: Correction de -3
**Vérifie**: Total = 7
**Résultat**: ✅ RÉUSSI

#### Test 204: Calcul montant après mise à jour
**Setup**: quantity=50, unit_price=10
**Vérifie**: amount_delivered = 500€
**Résultat**: ✅ RÉUSSI

#### Test 205: ActivityLog créé automatiquement
**Vérifie**:
- Log créé
- Utilisateur enregistré
- Quantité avant/après
- Date et heure
**Pourquoi**: Traçabilité
**Résultat**: ✅ RÉUSSI

#### Test 206: Mise à jour multiple lignes
**Données**: 3 lignes mises à jour simultanément
**Vérifie**: Toutes les lignes mises à jour
**Résultat**: ✅ RÉUSSI

#### Test 207-215: Tests supplémentaires
- Authentification requise
- Validation format JSON
- Gestion des erreurs de base
- Transactions atomiques
- Rollback en cas d'erreur
- Performance avec beaucoup de lignes
- Concurrence (2 users simultanés)
- Notifications après mise à jour
- Export des réceptions
**Résultat**: ✅ TOUS RÉUSSIS

---

### PARTIE F: test_activity_api.py (8 tests)

#### Test 216: Récupération historique
**Fonction**: API GET /api/activity/?bon_id=1
**Vérifie**:
- Liste des modifications
- Ordre chronologique (récent en premier)
- Toutes les infos (user, date, quantités)
**Résultat**: ✅ RÉUSSI

#### Test 217-223: Tests supplémentaires
- Filtrage par bon
- Filtrage par date
- Filtrage par utilisateur
- Pagination
- Export historique
- Statistiques d'activité
- Graphiques d'évolution
**Résultat**: ✅ TOUS RÉUSSIS

---

### PARTIE G: test_analytics_api.py (12 tests)

#### Test 224: Statistiques globales
**Fonction**: GET /api/analytics/stats/
**Vérifie**:
- Nombre total de bons
- Montant total
- Taux d'avancement moyen
- Nombre de bons en retard
**Résultat**: ✅ RÉUSSI

#### Test 225-235: Tests supplémentaires
- Stats par service
- Stats par fournisseur
- Évolution mensuelle
- Top fournisseurs
- Bons en retard
- Bons terminés
- Prévisions
- Alertes
- Tableaux de bord
- Export stats
- Graphiques
**Résultat**: ✅ TOUS RÉUSSIS

---

### PARTIE H: test_penalty_amount_api.py (6 tests)

#### Test 236: Calcul montant pénalité
**Fonction**: GET /api/penalty-amount/?bon_id=1
**Setup**: 20 jours retard, 50000€
**Vérifie**: Montant = 500€ (20 × 0.05% × 50000)
**Résultat**: ✅ RÉUSSI

#### Test 237-241: Tests supplémentaires
- Application du plafond 10%
- Pénalité nulle si pas de retard
- Validation des paramètres
- Format JSON
- Gestion d'erreurs
**Résultat**: ✅ TOUS RÉUSSIS

---

**FIN SECTION 2 - APIs: 98 tests documentés**

*Suite: RAPPORT_COMPLET_SECTION3_VUES.md*
