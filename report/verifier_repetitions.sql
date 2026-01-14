-- Requêtes SQL pour vérifier les 58 569 lignes manquantes

-- 1. Vérifier les répétitions INTERNES par fichier
SELECT 
    f.id as fichier_id,
    f.fichier as nom_fichier,
    COUNT(l.id) as lignes_en_base,
    COUNT(DISTINCT l.business_id) as business_ids_uniques,
    COUNT(l.id) - COUNT(DISTINCT l.business_id) as repetitions_internes,
    ROUND((COUNT(l.id) - COUNT(DISTINCT l.business_id)) * 100.0 / COUNT(l.id), 2) as pourcentage_repetitions
FROM orders_fichierimporte f
LEFT JOIN orders_lignefichier l ON f.id = l.fichier_id
GROUP BY f.id, f.fichier
ORDER BY f.date_importation DESC;

-- 2. Top 20 des business_ids les plus répétés
SELECT 
    business_id,
    COUNT(*) as nb_occurrences,
    STRING_AGG(CAST(fichier_id AS VARCHAR), ', ' ORDER BY fichier_id) as fichiers_ids,
    MIN(CAST(contenu->>'Order' AS VARCHAR)) as order_exemple,
    MIN(CAST(contenu->>'Line' AS VARCHAR)) as line_exemple,
    MIN(CAST(contenu->>'Item' AS VARCHAR)) as item_exemple
FROM orders_lignefichier
WHERE business_id IS NOT NULL AND business_id != ''
GROUP BY business_id
HAVING COUNT(*) > 1
ORDER BY COUNT(*) DESC
LIMIT 20;

-- 3. Lignes sans business_id (potentiellement invalides)
SELECT 
    COUNT(*) as total_sans_bid,
    COUNT(CASE WHEN contenu IS NULL OR contenu = '{}' THEN 1 END) as contenu_vide,
    COUNT(CASE WHEN business_id IS NULL THEN 1 END) as bid_null,
    COUNT(CASE WHEN business_id = '' THEN 1 END) as bid_vide
FROM orders_lignefichier;

-- 4. Lignes potentiellement filtrées (valeurs invalides)
SELECT 
    COUNT(*) as lignes_avec_false,
    COUNT(DISTINCT fichier_id) as fichiers_concernes
FROM orders_lignefichier
WHERE 
    contenu->>'Order' IN ('false', 'null', 'None', '0', '')
    OR contenu->>'Line' IN ('false', 'null', 'None', '0', '')
    OR contenu->>'Item' IN ('false', 'null', 'None', '0', '');

-- 5. Distribution des business_ids par fichier
SELECT 
    f.id,
    COUNT(l.id) as total_lignes,
    COUNT(DISTINCT l.business_id) as uniques,
    COUNT(DISTINCT l.business_id) * 100.0 / COUNT(l.id) as taux_uniquite
FROM orders_fichierimporte f
LEFT JOIN orders_lignefichier l ON f.id = l.fichier_id
GROUP BY f.id
ORDER BY f.date_importation DESC;

-- 6. Vérifier si les 61 500 lignes du fichier 3 étaient bien uniques
-- (Adapter l'ID du fichier selon vos données)
SELECT 
    fichier_id,
    COUNT(*) as lignes_totales,
    COUNT(DISTINCT business_id) as uniques_reelles,
    COUNT(*) - COUNT(DISTINCT business_id) as doublons_internes,
    COUNT(DISTINCT CONCAT(
        COALESCE(contenu->>'Order', ''),
        '|',
        COALESCE(contenu->>'Line', ''),
        '|',
        COALESCE(contenu->>'Item', ''),
        '|',
        COALESCE(contenu->>'Schedule', '')
    )) as combinaisons_uniques
FROM orders_lignefichier
WHERE fichier_id = (SELECT id FROM orders_fichierimporte ORDER BY date_importation DESC LIMIT 1)
GROUP BY fichier_id;
