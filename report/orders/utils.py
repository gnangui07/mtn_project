import os
import random
import tempfile

import pandas as pd
from django.core.files.storage import default_storage


def _lire_csv(chemin_absolu):
    """
    But:
    - Lire un fichier CSV et retourner son contenu simplement utilisable.

    Étapes:
    1) Lire avec pandas.
    2) Remplacer les valeurs manquantes (NaN) par None.
    3) Convertir en liste de dictionnaires.

    Entrées:
    - chemin_absolu (str): chemin complet vers le fichier CSV.

    Sorties:
    - (list[dict], int): contenu sous forme de liste de lignes + nombre de lignes.
    """
    df = pd.read_csv(chemin_absolu, dtype=str, keep_default_na=False)
    df = df.where(pd.notnull(df), None)
    return df.to_dict(orient='records'), len(df)


def _lire_excel(chemin_absolu, engine_name):
    """
    But:
    - Lire un fichier Excel (xlsx/xls/xlsb/ods) et le rendre en liste de dicts.

    Étapes:
    1) Lire avec le moteur indiqué (openpyxl/xlrd/pyxlsb/odf).
    2) Convertir les booléens en chaînes.
    3) Remplacer NaN/valeurs vides par None.

    Entrées:
    - chemin_absolu (str): chemin du fichier.
    - engine_name (str): nom du moteur ('openpyxl', 'xlrd', 'pyxlsb', 'odf').

    Sorties:
    - (list[dict], int): contenu + nombre de lignes.
    """
    # Lire en gardant les types originaux d'abord
    df = pd.read_excel(chemin_absolu, engine=engine_name)
    
    # Convertir les booléens en chaînes
    for col in df.columns:
        if df[col].dtype == 'bool':
            df[col] = df[col].astype(str)
    
    # Convertir tout en str et gérer les valeurs manquantes
    df = df.astype(str).replace({'nan': None, 'None': None, 'False': None, 'false': None, 'True': None, 'true': None})
    
    return df.to_dict(orient='records'), len(df)


def _lire_json(chemin_absolu):
    """
    But:
    - Lire un JSON et retourner une structure simple (liste de dicts ou dict).

    Étapes:
    1) Essayer de parser via pandas (tableau → DataFrame → liste).
    2) Si liste d'objets → normaliser et retourner.
    3) Si objet unique → retourner tel quel.
    4) En cas d’erreur → lire comme texte brut.

    Entrées:
    - chemin_absolu (str)

    Sorties:
    - (list|dict|{"raw_text": str}, int): contenu extrait + estimation du nombre de lignes.
    """
    try:
        df_or_obj = pd.read_json(chemin_absolu, dtype=str)
        if isinstance(df_or_obj, pd.DataFrame):
            df = df_or_obj.where(pd.notnull(df_or_obj), None)
            return df.to_dict(orient='records'), len(df)
        else:
            if isinstance(df_or_obj, list):
                # Normaliser liste de dicts, remplacer NaN si besoin
                nettoye = []
                for element in df_or_obj:
                    if isinstance(element, dict):
                        element_net = {
                            k: (None if (isinstance(v, float) and pd.isna(v)) else v)
                            for k, v in element.items()
                        }
                        nettoye.append(element_net)
                    else:
                        nettoye.append(element)
                return nettoye, len(nettoye)
            # C’est un objet JSON unique (dict)  
            return df_or_obj, 1
    except Exception:
        # JSON invalide ou autre erreur → lecture brute  
        with open(chemin_absolu, 'r', encoding='utf-8', errors='ignore') as f:
            texte = f.read()
        return {"raw_text": texte}, 0


def _lire_txt(chemin_absolu):
    """
    But:
    - Lire un .txt/.log et retourner chaque ligne simplement.

    Étapes:
    1) Ouvrir le fichier en UTF‑8 (tolérant).
    2) Lire toutes les lignes et enlever le retour à la ligne.

    Entrées:
    - chemin_absolu (str)

    Sorties:
    - ({"lines": list[str]}, int): contenu + nombre de lignes.
    """
    with open(chemin_absolu, 'r', encoding='utf-8', errors='ignore') as f:
        lignes = [l.rstrip('\n') for l in f]
    return {"lines": lignes}, len(lignes)


def extraire_depuis_fichier_relatif(chemin_relatif, ext):
    """
    But:
    - Extraire le contenu d’un fichier connu par son chemin relatif (dans MEDIA_ROOT).

    Étapes:
    1) Tenter d’ouvrir localement (MEDIA_ROOT/chemin_relatif).
    2) Sinon, télécharger via le storage dans un fichier temporaire.
    3) Selon l’extension, appeler le bon lecteur (_lire_csv/_lire_excel/_lire_json/_lire_txt).
    4) Renvoyer le contenu + le nombre de lignes.

    Entrées:
    - chemin_relatif (str): ex. 'uploads/monfichier.xlsx'
    - ext (str): extension sans le point (csv, xlsx, xls, xlsb, ods, json, txt, log…)

    Sorties:
    - (any, int): contenu extrait (liste/dict/texte/binaire hex) + nb_lignes estimé.
    """
    from django.conf import settings

    # 1) Obtenir un chemin local
    try:
        chemin_absolu = os.path.join(settings.MEDIA_ROOT, chemin_relatif)
        if not os.path.exists(chemin_absolu):
            raise FileNotFoundError
    except Exception:
        # Storage distant → récupère dans un temporaire local  
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}")
        chemin_tmp = tmp.name
        tmp.close()
        with default_storage.open(chemin_relatif, "rb") as src:
            with open(chemin_tmp, "wb") as dst:
                dst.write(src.read())
        chemin_absolu = chemin_tmp

    # 2) Lire/extraction selon extension
    try:
        if ext == 'csv':
            return _lire_csv(chemin_absolu)
        elif ext == 'xlsx':
            return _lire_excel(chemin_absolu, engine_name='openpyxl')
        elif ext == 'xls':
            return _lire_excel(chemin_absolu, engine_name='xlrd')
        elif ext == 'xlsb':
            return _lire_excel(chemin_absolu, engine_name='pyxlsb')
        elif ext == 'ods':
            return _lire_excel(chemin_absolu, engine_name='odf')
        elif ext == 'json':
            return _lire_json(chemin_absolu)
        elif ext in ('txt', 'log'):
            return _lire_txt(chemin_absolu)
        else:
            # Fallback : n’importe quelle autre extension, lecture binaire + hex
            with open(chemin_absolu, 'rb') as f:
                binaire = f.read()
            return {"raw_bytes_hex": binaire.hex()}, 0
    except Exception as e:
        return {"error": f"Extraction failed for .{ext}: {str(e)}"}, 0
    finally:
        # 3) On supprime le temporaire si on l’a créé
        if 'chemin_tmp' in locals():
            try:
                os.remove(chemin_tmp)
            except Exception:
                pass


def generate_report_number():
    """
    But:
    - Générer un petit numéro de rapport aléatoire (4 chiffres).

    Étapes:
    1) Tirer un nombre entre 1000 et 9999.
    2) Le convertir en chaîne.

    Sorties:
    - str: ex. '5831'
    """
    return str(random.randint(1000, 9999))


def round_decimal(value, places=2):
    """
    Arrondit une valeur décimale au nombre de décimales spécifié.
    :param value: La valeur à arrondir (Decimal, float, int ou str)
    :param places: Nombre de décimales (par défaut 2)
    :return: Decimal arrondi
    """
    from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
    
    if value is None:
        return Decimal('0')
    if not isinstance(value, Decimal):
        try:
            value = Decimal(str(value))
        except InvalidOperation:
            return Decimal('0')
    # Format de quantification basé sur le nombre de décimales
    quant_format = Decimal('0.' + ('0' * (places-1)) + '1') if places > 0 else Decimal('1')
    return value.quantize(quant_format, rounding=ROUND_HALF_UP)


def normalize_business_id(business_id):
    """
    Normalise un business_id en convertissant les valeurs numériques décimales en entiers
    pour éviter les doublons (ex: 43.0 -> 43)
    """
    if not business_id:
        return business_id
    
    parts = business_id.split('|')
    normalized_parts = []
    
    for part in parts:
        if ':' in part:
            key, value = part.split(':', 1)
            try:
                # Essayer de convertir en float puis supprimer les .0 inutiles
                float_val = float(value)
                if float_val.is_integer():
                    value = str(int(float_val))
            except (ValueError, TypeError):
                # Garder la valeur originale si conversion impossible
                pass
            normalized_parts.append(f"{key}:{value}")
        else:
            normalized_parts.append(part)
    
    return '|'.join(normalized_parts)
