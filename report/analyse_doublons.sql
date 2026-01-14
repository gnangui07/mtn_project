-- Requêtes SQL pour analyser les doublons

-- 1. Statistiques générales
SELECT 
    'Total lignes' as metrique,
    COUNT(*) as valeur
FROM orders_lignefichier

UNION ALL

SELECT 
    'Business IDs uniques' as metrique,
    COUNT(DISTINCT business_id) as valeur
FROM orders_lignefichier

UNION ALL

SELECT 
    'Doublons évités' as metrique,
    COUNT(*) - COUNT(DISTINCT business_id) as valeur
FROM orders_lignefichier;

-- 2. Analyse par fichier
SELECT 
    f.id as fichier_id,
    SUBSTRING(f.fichier, CHARINDEX('/', f.fichier) + 1, 50) as nom_fichier,
    COUNT(l.id) as total_lignes,
    COUNT(DISTINCT l.business_id) as business_ids_uniques,
    COUNT(l.id) - COUNT(DISTINCT l.business_id) as doublons_dans_fichier
FROM orders_fichierimporte f
LEFT JOIN orders_lignefichier l ON f.id = l.fichier_id
GROUP BY f.id, f.fichier
ORDER BY f.date_importation DESC;

-- 3. Top 10 des business_ids les plus dupliqués
SELECT 
    business_id,
    COUNT(*) as nb_occurrences,
    STRING_AGG(CAST(fichier_id AS VARCHAR), ', ') as fichiers_ids
FROM orders_lignefichier
WHERE business_id IS NOT NULL
GROUP BY business_id
HAVING COUNT(*) > 1
ORDER BY COUNT(*) DESC
LIMIT 10;

-- 4. Exemple détaillé d'un doublon
SELECT 
    l.id,
    l.fichier_id,
    l.numero_ligne,
    l.business_id,
    l.contenu->>'Order' as order_value,
    l.contenu->>'Line' as line_value,
    l.contenu->>'Item' as item_value,
    l.contenu->>'Schedule' as schedule_value,
    f.date_importation
FROM orders_lignefichier l
JOIN orders_fichierimporte f ON l.fichier_id = f.id
WHERE l.business_id = (
    SELECT business_id 
    FROM orders_lignefichier 
    GROUP BY business_id 
    ORDER BY COUNT(*) DESC 
    LIMIT 1
)
ORDER BY f.date_importation;
