import os
import random
import tempfile

import pandas as pd
from django.core.files.storage import default_storage


def _lire_csv(chemin_absolu):
    """
    Lit un CSV en DataFrame pandas, remplace NaN par None, et renvoie
    (liste_de_dicts, nb_lignes).
    """
    df = pd.read_csv(chemin_absolu, dtype=str, keep_default_na=False)
    df = df.where(pd.notnull(df), None)
    return df.to_dict(orient='records'), len(df)


def _lire_excel(chemin_absolu, engine_name):
    """
    Lit un fichier Excel (.xlsx, .xls, .xlsb, .ods) avec le moteur spécifié,
    convertit les booléens en chaînes, remplace NaN par None, et renvoie (liste_de_dicts, nb_lignes).
    - engine='openpyxl' pour .xlsx
    - engine='xlrd' pour .xls (xlrd==1.2.0 recommandé)
    - engine='pyxlsb' pour .xlsb
    - engine='odf' pour .ods
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
    Lit un fichier JSON. Si c'est un tableau → DataFrame pandas → liste_de_dicts.
    Sinon → on lit le texte brut et on renvoie {"raw_text": ...}.
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
    Lit un fichier texte (.txt ou .log) et renvoie ({"lines": [...]} , nb_lignes).
    """
    with open(chemin_absolu, 'r', encoding='utf-8', errors='ignore') as f:
        lignes = [l.rstrip('\n') for l in f]
    return {"lines": lignes}, len(lignes)


def extraire_depuis_fichier_relatif(chemin_relatif, ext):
    """
    À partir du chemin relatif (par exemple 'uploads/monfichier.xlsb') et de l’extension :
      1) On essaye d'accéder directement au chemin local (MEDIA_ROOT/chemin_relatif).
      2) S’il est absent (storage distant), on télécharge dans un fichier temporaire local.
      3) Selon ext, on appelle :
         - 'csv'   → _lire_csv
         - 'xlsx'  → _lire_excel(engine='openpyxl')
         - 'xls'   → _lire_excel(engine='xlrd')
         - 'xlsb'  → _lire_excel(engine='pyxlsb')
         - 'ods'   → _lire_excel(engine='odf')
         - 'json'  → _lire_json
         - 'txt', 'log' → _lire_txt
         - Tout autre → lecture binaire + hexdigest
      4) On renvoie toujours (contenu_extrait, nb_lignes).
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
    Génère un numéro de rapport unique à 4 chiffres.
    
    Returns:
        str: Un nombre aléatoire entre 1000 et 9999 sous forme de chaîne
    """
    return str(random.randint(1000, 9999))
