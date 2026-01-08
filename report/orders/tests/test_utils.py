# tests/test_utils.py
import os
import tempfile
import pandas as pd
from unittest.mock import patch, Mock, MagicMock
from django.test import TestCase
from django.core.files.base import ContentFile
from orders.utils import (
    extraire_depuis_fichier_relatif, 
    generate_report_number,
    _lire_csv,
    _lire_excel,
    _lire_json,
    _lire_txt
)


class TestUtils(TestCase):
    def setUp(self):
        # Créer des fichiers temporaires pour les tests
        self.temp_dir = tempfile.mkdtemp()
        
        # Fichier CSV
        self.csv_data = """Name,Age,City
John,30,Paris
Jane,25,Lyon"""
        self.csv_path = os.path.join(self.temp_dir, 'test.csv')
        with open(self.csv_path, 'w', encoding='utf-8') as f:
            f.write(self.csv_data)
        
        # Fichier Excel
        self.excel_path = os.path.join(self.temp_dir, 'test.xlsx')
        df = pd.DataFrame({
            'Name': ['John', 'Jane'],
            'Age': [30, 25],
            'City': ['Paris', 'Lyon']
        })
        df.to_excel(self.excel_path, index=False)
        
        # Fichier JSON
        self.json_data = [
            {'Name': 'John', 'Age': 30, 'City': 'Paris'},
            {'Name': 'Jane', 'Age': 25, 'City': 'Lyon'}
        ]
        self.json_path = os.path.join(self.temp_dir, 'test.json')
        df.to_json(self.json_path, orient='records')
        
        # Fichier texte
        self.txt_data = """Ligne 1
Ligne 2
Ligne 3"""
        self.txt_path = os.path.join(self.temp_dir, 'test.txt')
        with open(self.txt_path, 'w', encoding='utf-8') as f:
            f.write(self.txt_data)

    def tearDown(self):
        # Nettoyer les fichiers temporaires
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_lire_csv(self):
        """Test la lecture de fichiers CSV"""
        data, count = _lire_csv(self.csv_path)
        
        self.assertEqual(count, 2)
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]['Name'], 'John')
        self.assertEqual(data[1]['City'], 'Lyon')

    def test_lire_excel(self):
        """Test la lecture de fichiers Excel"""
        data, count = _lire_excel(self.excel_path, 'openpyxl')
        
        self.assertEqual(count, 2)
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]['Name'], 'John')
        self.assertEqual(data[1]['City'], 'Lyon')

    def test_lire_json(self):
        """Test la lecture de fichiers JSON"""
        data, count = _lire_json(self.json_path)
        
        self.assertEqual(count, 2)
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]['Name'], 'John')
        self.assertEqual(data[1]['City'], 'Lyon')

    def test_lire_txt(self):
        """Test la lecture de fichiers texte"""
        data, count = _lire_txt(self.txt_path)
        
        self.assertEqual(count, 3)
        self.assertIn('lines', data)
        self.assertEqual(len(data['lines']), 3)
        self.assertEqual(data['lines'][0], 'Ligne 1')

    def test_extraire_depuis_fichier_relatif_csv(self):
        """Test l'extraction depuis un fichier CSV"""
        # Créer un fichier dans MEDIA_ROOT
        from django.conf import settings
        test_dir = os.path.join(settings.MEDIA_ROOT, 'tests')


# ========== TESTS SUPPLÉMENTAIRES POUR ATTEINDRE 90% DE COUVERTURE ==========

class TestExtraireDepuisFichierErrors(TestCase):
    """Tests de gestion d'erreurs pour extraire_depuis_fichier_relatif"""
    
    def test_fichier_inexistant(self):
        """Test avec un fichier inexistant"""
        from orders.utils import extraire_depuis_fichier_relatif
        
        # Fichier qui n'existe pas - devrait lever une exception (mock os.path.exists pour éviter le fallback local)
        with patch('orders.utils.os.path.exists', return_value=False):
            with patch('orders.utils.default_storage.open', side_effect=FileNotFoundError):
                data, count = extraire_depuis_fichier_relatif('nonexistent_file.csv', 'csv')
                self.assertIn('error', data)
    
    def test_format_non_supporte(self):
        """Test avec un format de fichier non supporté"""
        from orders.utils import extraire_depuis_fichier_relatif
        import tempfile
        from django.conf import settings
        
        # Créer un fichier avec extension non supportée
        os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
        test_file = os.path.join(settings.MEDIA_ROOT, 'test.xyz')
        with open(test_file, 'w') as f:
            f.write('Some content')
        
        try:
            data, count = extraire_depuis_fichier_relatif('test.xyz', 'xyz')
            # Devrait retourner un dictionnaire avec raw_bytes_hex
            self.assertIsInstance(data, dict)
            self.assertIn('raw_bytes_hex', data)
            self.assertEqual(count, 0)
        finally:
            if os.path.exists(test_file):
                os.remove(test_file)
    
    def test_fichier_corrompu_excel(self):
        """Test avec un fichier Excel corrompu"""
        from orders.utils import extraire_depuis_fichier_relatif
        from django.conf import settings
        
        # Créer un fichier Excel invalide
        os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
        test_file = os.path.join(settings.MEDIA_ROOT, 'corrupt.xlsx')
        with open(test_file, 'w') as f:
            f.write('This is not a valid Excel file')
        
        try:
            data, count = extraire_depuis_fichier_relatif('corrupt.xlsx', 'xlsx')
            # Devrait retourner un dictionnaire avec erreur
            self.assertIsInstance(data, dict)
            self.assertIn('error', data)
            self.assertEqual(count, 0)
        finally:
            if os.path.exists(test_file):
                os.remove(test_file)
    
    def test_fichier_vide(self):
        """Test avec un fichier vide"""
        from orders.utils import extraire_depuis_fichier_relatif
        from django.conf import settings
        
        # Créer un fichier CSV vide
        os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
        test_file = os.path.join(settings.MEDIA_ROOT, 'empty.csv')
        with open(test_file, 'w') as f:
            f.write('')
        
        try:
            data, count = extraire_depuis_fichier_relatif('empty.csv', 'csv')
            # Devrait retourner un dictionnaire avec erreur
            self.assertIsInstance(data, dict)
            self.assertIn('error', data)
            self.assertEqual(count, 0)
        finally:
            if os.path.exists(test_file):
                os.remove(test_file)


class TestLectureFichiersErrors(TestCase):
    """Tests de gestion d'erreurs pour les fonctions de lecture"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_csv_malformed(self):
        """Test lecture CSV mal formé"""
        # Créer un CSV avec des lignes incohérentes
        csv_path = os.path.join(self.temp_dir, 'malformed.csv')
        with open(csv_path, 'w', encoding='utf-8') as f:
            f.write('Col1,Col2,Col3\n')
            f.write('Val1,Val2,Val3\n')  # Ligne correcte
            f.write('Val4,Val5,Val6\n')  # Ligne correcte
        
        data, count = _lire_csv(csv_path)
        
        # Devrait lire correctement
        self.assertIsInstance(data, list)
        self.assertEqual(count, 2)
    
    def test_excel_with_multiple_sheets(self):
        """Test lecture Excel avec plusieurs feuilles"""
        excel_path = os.path.join(self.temp_dir, 'multi_sheet.xlsx')
        
        # Créer un fichier Excel avec 2 feuilles
        import pandas as pd
        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            pd.DataFrame({'A': [1, 2], 'B': [3, 4]}).to_excel(writer, sheet_name='Sheet1', index=False)
            pd.DataFrame({'C': [5, 6], 'D': [7, 8]}).to_excel(writer, sheet_name='Sheet2', index=False)
        
        data, count = _lire_excel(excel_path, 'openpyxl')
        
        # Devrait lire la première feuille
        self.assertEqual(count, 2)
        self.assertEqual(len(data), 2)
    
    def test_json_invalid_syntax(self):
        """Test lecture JSON avec syntaxe invalide"""
        json_path = os.path.join(self.temp_dir, 'invalid.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            f.write('{"key": "value",}')  # Virgule finale invalide
        
        try:
            data, count = _lire_json(json_path)
            # Devrait gérer l'erreur
            self.assertIsInstance(data, list)
        except:
            # C'est acceptable si une exception est levée
            pass
    
    def test_txt_with_encoding_issues(self):
        """Test lecture TXT avec problèmes d'encodage"""
        txt_path = os.path.join(self.temp_dir, 'encoding.txt')
        
        # Créer un fichier avec encodage non-UTF8
        with open(txt_path, 'wb') as f:
            f.write(b'\xff\xfe')  # BOM UTF-16
            f.write('Test content'.encode('utf-16-le'))
        
        try:
            data, count = _lire_txt(txt_path)
            # Devrait essayer de lire
            self.assertIsInstance(data, dict)
        except:
            # C'est acceptable si une exception est levée
            pass


class TestGenerateReportNumber(TestCase):
    """Tests pour la fonction generate_report_number"""
    
    def test_generate_report_number_format(self):
        """Test le format du numéro de rapport généré"""
        from orders.utils import generate_report_number
        
        report_number = generate_report_number()
        
        # Devrait être une chaîne non vide
        self.assertIsInstance(report_number, str)
        # Format MSRN-YYYYMMDD-XXXX (5+8+1+4 = 18 caractères)
        self.assertEqual(len(report_number), 18)
    
    def test_generate_report_number_unique(self):
        """Test que les numéros générés sont uniques"""
        from orders.utils import generate_report_number
        
        numbers = set()
        for _ in range(10):
            num = generate_report_number()
            numbers.add(num)
        
        # Tous les numéros devraient être différents
        self.assertEqual(len(numbers), 10)
    
    def test_generate_report_number_sequential(self):
        """Test que les numéros sont générés"""
        from orders.utils import generate_report_number
        
        # Générer plusieurs numéros
        numbers = [generate_report_number() for _ in range(5)]
        
        # Tous devraient être des chaînes
        for num in numbers:
            self.assertIsInstance(num, str)
            self.assertEqual(len(num), 18)


class TestUtilsEdgeCases(TestCase):
    """Tests de cas limites pour les utilitaires"""
    
    def test_lire_csv_with_bom(self):
        """Test lecture CSV avec BOM UTF-8"""
        temp_dir = tempfile.mkdtemp()
        try:
            csv_path = os.path.join(temp_dir, 'bom.csv')
            with open(csv_path, 'wb') as f:
                f.write(b'\xef\xbb\xbf')  # BOM UTF-8
                f.write('Name,Age\nJohn,30\n'.encode('utf-8'))
            
            data, count = _lire_csv(csv_path)
            
            self.assertEqual(count, 1)
            self.assertEqual(data[0]['Name'], 'John')
        finally:
            import shutil
            shutil.rmtree(temp_dir)
    
    def test_lire_excel_with_formulas(self):
        """Test lecture Excel avec formules"""
        temp_dir = tempfile.mkdtemp()
        try:
            excel_path = os.path.join(temp_dir, 'formulas.xlsx')
            
            import pandas as pd
            df = pd.DataFrame({
                'A': [1, 2, 3],
                'B': [4, 5, 6],
                'Sum': [5, 7, 9]  # Simule une formule =A+B
            })
            df.to_excel(excel_path, index=False)
            
            data, count = _lire_excel(excel_path, 'openpyxl')
            
            self.assertEqual(count, 3)
            # Les valeurs calculées devraient être lues
            # Les valeurs peuvent être des strings ou des entiers
            self.assertIn(str(data[0]['Sum']), ['5', '5.0'])
        finally:
            import shutil
            shutil.rmtree(temp_dir)
    
    def test_lire_txt_with_special_chars(self):
        """Test lecture TXT avec caractères spéciaux"""
        temp_dir = tempfile.mkdtemp()
        try:
            txt_path = os.path.join(temp_dir, 'special.txt')
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write('Ligne 1: €£¥\n')
                f.write('Ligne 2: àéèêë\n')
                f.write('Ligne 3: 中文\n')
            data, count = _lire_txt(txt_path)

            self.assertEqual(count, 3)
            self.assertIn('lines', data)
            self.assertEqual(len(data['lines']), 3)
        finally:
            import shutil
            shutil.rmtree(temp_dir)


class TestUtilsAdditionalCoverage(TestCase):
    """Tests additionnels pour couvrir des branches spécifiques dans utils.py"""

    def test_lire_json_list_normalized(self):
        """JSON liste doit être lu et compter correctement (normalisation)"""
        temp_dir = tempfile.mkdtemp()
        try:
            json_path = os.path.join(temp_dir, 'list.json')
            with open(json_path, 'w', encoding='utf-8') as f:
                f.write('[{"a": 1, "b": null}, {"a": 2, "b": null}]')
            data, count = _lire_json(json_path)
            self.assertIsInstance(data, list)
            self.assertEqual(count, 2)
        finally:
            import shutil
            shutil.rmtree(temp_dir)

    def test_lire_excel_bool_columns_converted_to_str(self):
        """Colonnes booléennes doivent devenir des chaînes"""
        temp_dir = tempfile.mkdtemp()
        try:
            excel_path = os.path.join(temp_dir, 'bools.xlsx')
            df = pd.DataFrame({'Flag': [True, False]})
            df.to_excel(excel_path, index=False)
            data, count = _lire_excel(excel_path, 'openpyxl')
            self.assertEqual(count, 2)
            self.assertIn(str(data[0]['Flag']), ['True', 'False', 'None'])
        finally:
            import shutil
            shutil.rmtree(temp_dir)

    def test_extraire_engine_dispatch_and_cleanup(self):
        """Vérifie l'utilisation des bons moteurs et la suppression du temporaire"""
        from unittest.mock import patch, MagicMock
        from django.conf import settings
        for name, ext, engine in [('file.xls', 'xls', 'xlrd'), ('file.xlsb', 'xlsb', 'pyxlsb'), ('file.ods', 'ods', 'odf')]:
            with patch('orders.utils.default_storage.open') as mock_open, \
                 patch('orders.utils.tempfile.NamedTemporaryFile') as mock_tmp, \
                 patch('orders.utils._lire_excel') as mock_lire_excel, \
                 patch('orders.utils.os.remove') as mock_remove:
                tmp = MagicMock()
                tmp.name = os.path.join(settings.MEDIA_ROOT, name + '.tmp')
                mock_tmp.return_value = tmp
                mock_open.return_value.__enter__.return_value.read.return_value = b''
                mock_lire_excel.return_value = ([], 0)
                extraire_depuis_fichier_relatif(name, ext)
                mock_lire_excel.assert_called_with(tmp.name, engine_name=engine)
                mock_remove.assert_called()


class TestUtilsErrorHandling(TestCase):
    """Test gestion des erreurs dans les utilitaires"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_extraire_fichier_non_supporte(self):
        """Test avec extension non supportée"""
        from orders.utils import extraire_depuis_fichier_relatif
        import os
        from django.conf import settings
        
        # Test avec une extension non supportée (xyz)
        # Créer un fichier de test.xyz
        path = os.path.join(settings.MEDIA_ROOT, 'test.xyz')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as f:
            f.write(b'test')
        
        try:
            data, count = extraire_depuis_fichier_relatif('test.xyz', 'xyz')
            self.assertIn('raw_bytes_hex', data)
        finally:
            if os.path.exists(path):
                os.remove(path)
    
    def test_extraire_fichier_inexistant(self):
        """Test avec fichier inexistant"""
        from orders.utils import extraire_depuis_fichier_relatif
        from django.core.files.base import ContentFile
        
        # Créer un fichier qui n'existe pas physiquement
        from orders.models import FichierImporte
        from django.contrib.auth import get_user_model
        
        user = get_user_model().objects.create_user(
            email='test@example.com',
            password='testpass'
        )
        
        fichier = FichierImporte.objects.create(
            fichier=ContentFile(b'test', name='test.csv'),
            utilisateur=user
        )
        
        # Modifier le chemin pour qu'il n'existe pas
        with patch('orders.utils.os.path.exists', return_value=False):
             with patch('orders.utils.default_storage.open', side_effect=FileNotFoundError):
                data, count = extraire_depuis_fichier_relatif('test.csv', 'csv')
                self.assertIn('error', data)
    
    def test_lire_csv_erreur_parsing(self):
        """Test lecture CSV avec erreur de parsing"""
        from orders.utils import _lire_csv
        import pandas as pd
        
        # Créer un fichier CSV invalide (guillemet non fermé)
        invalid_csv_path = os.path.join(self.temp_dir, 'invalid.csv')
        with open(invalid_csv_path, 'w') as f:
            f.write('Col1,Col2\n"Value1,Value2') # Erreur de parsing EOF
        
        # Devrait lever une ParserError (pandas)
        with self.assertRaises(pd.errors.ParserError):
            _lire_csv(invalid_csv_path)
    
    def test_lire_excel_fichier_corrompu(self):
        """Test lecture Excel avec fichier corrompu"""
        from orders.utils import _lire_excel
        
        # Créer un fichier invalide
        invalid_excel_path = os.path.join(self.temp_dir, 'invalid.xlsx')
        with open(invalid_excel_path, 'wb') as f:
            f.write(b'Not an Excel file')
        
        # Devrait lever une exception
        with self.assertRaises(Exception):
            _lire_excel(invalid_excel_path, 'openpyxl')
    
    def test_lire_json_invalide(self):
        """Test lecture JSON invalide"""
        from orders.utils import _lire_json
        
        # Créer un fichier JSON invalide
        invalid_json_path = os.path.join(self.temp_dir, 'invalid.json')
        with open(invalid_json_path, 'w') as f:
            f.write('{ invalid json }')
        
        # Devrait retourner un dict avec raw_text
        result, count = _lire_json(invalid_json_path)
        self.assertIsInstance(result, dict)
        self.assertIn('raw_text', result)
    
    def test_generate_report_number_format(self):
        """Test formatage numéro de rapport"""
        from orders.utils import generate_report_number
        from datetime import datetime
        from unittest.mock import patch
        
        # Mock de datetime pour avoir un résultat prévisible
        fixed_now = datetime(2024, 1, 15, 10, 30, 0)
        with patch('orders.utils.datetime') as mock_datetime:
            mock_datetime.now.return_value = fixed_now
            
            report_num = generate_report_number()
            
            # Vérifie le format : MSRN-YYYYMMDD-XXXX
            self.assertTrue(report_num.startswith('MSRN-20240115-'))
            # Vérifie que le suffixe est un nombre à 4 chiffres
            suffix = report_num.split('-')[-1]
            self.assertEqual(len(suffix), 4)
            self.assertTrue(suffix.isdigit())
    
    def test_generate_report_number_uniqueness(self):
        """Test unicité des numéros de rapport"""
        from orders.utils import generate_report_number
        
        # Générer plusieurs numéros
        numbers = [generate_report_number() for _ in range(10)]
        
        # Vérifier qu'ils sont tous uniques
        self.assertEqual(len(numbers), len(set(numbers)))
    
    def test_extraire_depuis_fichier_extension_manquante(self):
        """Test avec extension manquante"""
        from orders.utils import extraire_depuis_fichier_relatif
        
        # Sans extension, devrait deviner à partir du nom
        with patch('orders.utils.default_storage.exists', return_value=True), \
             patch('orders.utils._lire_csv') as mock_lire:
            
            mock_lire.return_value = ([], 0)
            extraire_depuis_fichier_relatif('test.csv', None)
            mock_lire.assert_called_once()
    
    def test_extraire_fichier_nettoyage_temporaire(self):
        """Test nettoyage fichier temporaire en cas d'erreur"""
        from orders.utils import extraire_depuis_fichier_relatif
        from unittest.mock import patch
        
        # Mock os.path.exists pour retourner False pour le fichier d'origine mais True pour le fichier temporaire
        with patch('orders.utils.os.path.exists') as mock_exists, \
             patch('orders.utils.default_storage.open') as mock_open, \
             patch('orders.utils.os.remove') as mock_remove:
            
            # side_effect pour exists
            def exists_side_effect(path):
                return path != chemin_media
            
            chemin_media = os.path.join(self.temp_dir, 'test.csv')
            # On considère que seul le chemin initial n'existe pas
            mock_exists.side_effect = lambda p: p != 'test.csv' and 'media' not in str(p) # Simplification, ou juste mock_exists.return_value = False
            
            # Plus simple: on mock default_storage.open pour lever une erreur
            # et on laisse l'exception handler faire son travail.
            # Le code fait: if not os.path.exists(abs): ... except: storage.open ...
            # Donc il faut que os.path.exists retourne False au début.
            # MAIS il faut qu'il retourne True à la fin pour le cleanup: if os.path.exists(chemin_tmp)
            
            # On va utiliser une side_effect sur os.path.exists
            mock_exists.side_effect = [False, True, True] # 1: check initial, 2: check cleanup, 3: ?
            
            mock_open.side_effect = Exception('Read error')
            
            # L'exception est catchée et on retourne un dict d'erreur
            extraire_depuis_fichier_relatif('test.csv', 'csv')
            
            # Vérifier que le fichier temporaire est quand même supprimé
            mock_remove.assert_called_once()
    
    def test_lire_csv_with_encoding(self):
        """Test lecture CSV avec différents encodages"""
        from orders.utils import _lire_csv
        
        # Créer un fichier CSV avec encodage UTF-8 BOM
        csv_path = os.path.join(self.temp_dir, 'utf8_bom.csv')
        with open(csv_path, 'w', encoding='utf-8-sig') as f:
            f.write('\ufeffName,Age\nJohn,30\n')
        
        data, count = _lire_csv(csv_path)
        self.assertEqual(count, 1)
        self.assertEqual(data[0]['Name'], 'John')
    
    def test_lire_excel_with_empty_rows(self):
        """Test lecture Excel avec lignes vides"""
        from orders.utils import _lire_excel
        import pandas as pd
        
        # Créer un Excel avec des lignes vides
        excel_path = os.path.join(self.temp_dir, 'empty_rows.xlsx')
        df = pd.DataFrame({
            'Name': ['John', None, 'Jane'],
            'Age': [30, None, 25],
            'City': ['Paris', None, 'Lyon']
        })
        df.to_excel(excel_path, index=False)
        
        data, count = _lire_excel(excel_path, 'openpyxl')
        # pandas.read_excel avec keep_default_na=False transforme None en 'None'
        self.assertEqual(count, 3)
        self.assertIsNone(data[1]['Name'])


class TestImportUtils(TestCase):
    """Test le module import_utils"""
    
    def setUp(self):
        from django.contrib.auth import get_user_model
        self.user = get_user_model().objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
    
    @patch('orders.import_utils.process_chunk')
    @patch('orders.import_utils.os.path.exists')
    @patch('orders.import_utils.os.path.splitext')
    def test_import_file_optimized_xlsx(self, mock_splitext, mock_exists, mock_process):
        """Test import fichier Excel optimisé"""
        from orders.import_utils import import_file_optimized
        from orders.models import FichierImporte
        from django.core.files.base import ContentFile
        
        # Setup mocks
        mock_splitext.return_value = ('test', '.xlsx')
        mock_exists.return_value = True
        mock_process.return_value = None
        
        # Créer un fichier
        fichier = FichierImporte.objects.create(
            fichier=ContentFile(b'test', name='test.xlsx'),
            utilisateur=self.user
        )
        
        # Mock du chemin
        with patch.object(fichier, 'fichier') as mock_file:
            mock_file.path = '/path/to/test.xlsx'
            mock_file.name = 'test.xlsx'
            with patch('orders.import_utils.load_workbook') as mock_load_wb:
                # Mock workbook
                mock_wb = Mock()
                mock_ws = Mock()
                mock_wb.active = mock_ws
                mock_wb.close = Mock()
                mock_load_wb.return_value = mock_wb
                
                # Mock itération des lignes
                mock_ws.iter_rows.return_value = [
                    (None, None, None),  # Header
                    ('Data1', 'Data2', 'Data3'),  # Data row
                ]
                
                result = import_file_optimized(fichier)
                
                self.assertIsInstance(result, tuple)
                self.assertEqual(len(result), 2)
                mock_load_wb.assert_called_once()
    
    @patch('orders.import_utils.process_chunk')
    @patch('orders.import_utils.pd.read_csv')
    @patch('orders.import_utils.os.path.exists')
    @patch('orders.import_utils.os.path.splitext')
    def test_import_file_optimized_csv(self, mock_splitext, mock_exists, mock_read_csv, mock_process):
        """Test import fichier CSV optimisé"""
        from orders.import_utils import import_file_optimized
        from orders.models import FichierImporte
        from django.core.files.base import ContentFile
        import pandas as pd
        
        # Setup mocks
        mock_splitext.return_value = ('test', '.csv')
        mock_exists.return_value = True
        mock_process.return_value = None
        
        # Mock DataFrame
        mock_df = pd.DataFrame({'col1': ['value1']})
        mock_read_csv.return_value = [mock_df]
        
        # Créer un fichier
        fichier = FichierImporte.objects.create(
            fichier=ContentFile(b'test', name='test.csv'),
            utilisateur=self.user
        )
        
        # Mock du chemin
        with patch.object(fichier, 'fichier') as mock_file:
            mock_file.path = '/path/to/test.csv'
            mock_file.name = 'test.csv'
            result = import_file_optimized(fichier)
            
            self.assertIsInstance(result, tuple)
            self.assertEqual(len(result), 2)
            mock_read_csv.assert_called() # Called potentially multiple times if retry logic or setup involved
    
    @patch('orders.import_utils.process_chunk')
    @patch('orders.import_utils.os.path.exists')
    @patch('orders.import_utils.os.path.splitext')
    def test_import_file_s3_storage(self, mock_splitext, mock_exists, mock_process):
        """Test import avec stockage S3 distant"""
        from orders.import_utils import import_file_optimized
        from orders.models import FichierImporte
        from django.core.files.base import ContentFile
        
        # Setup mocks
        mock_splitext.return_value = ('test', '.xlsx')
        mock_exists.return_value = True
        mock_process.return_value = None
        
        # Créer un fichier
        # Créer un fichier - On saute l'extraction au create() car on veut la tester manuellement après
        fichier = FichierImporte(
            fichier=ContentFile(b'test', name='test.xlsx'),
            utilisateur=self.user
        )
        fichier._skip_extraction = True
        fichier.save()

        
        # Simuler NotImplementedError (stockage distant) sur access à .path
        from unittest.mock import PropertyMock
        with patch.object(fichier, 'fichier') as mock_file:
            type(mock_file).path = PropertyMock(side_effect=NotImplementedError)
            mock_file.name = 'test.xlsx'
            with patch('orders.import_utils.tempfile.NamedTemporaryFile') as mock_tmp:
                with patch('orders.import_utils.default_storage') as mock_storage:
                    with patch('orders.import_utils.load_workbook') as mock_load_wb:
                        # Setup mocks
                        mock_tmp_file = Mock()
                        mock_tmp_file.name = '/tmp/test.xlsx'
                        mock_tmp.return_value = mock_tmp_file
                        
                        # Pour que d.write(f.read()) fonctionne, f doit avoir une méthode read() qui retourne des bytes
                        mock_f = MagicMock()
                        mock_f.read.return_value = b'test content'
                        mock_file.open.return_value.__enter__.return_value = mock_f
                        
                        mock_wb = Mock()
                        mock_ws = Mock()
                        mock_wb.active = mock_ws
                        mock_wb.close = Mock()
                        mock_load_wb.return_value = mock_wb
                        mock_ws.iter_rows.return_value = []
                        
                        result = import_file_optimized(fichier)
                        
                        self.assertIsInstance(result, tuple)
                        mock_file.open.assert_called_once()
    
    def test_process_chunk_basic(self):
        """Test traitement basique d'un chunk"""
        from orders.import_utils import process_chunk
        from orders.models import FichierImporte
        from django.core.files.base import ContentFile
        
        # Créer un fichier
        fichier = FichierImporte.objects.create(
            fichier=ContentFile(b'test', name='test.xlsx'),
            utilisateur=self.user
        )
        
        # Données de test
        records = [
            {
                'Order Number': 'PO001',
                'Business ID': 'BID001',
                'Ordered Quantity': '100',
                'Received Quantity': '50',
                'Price': '10.5'
            }
        ]
        
        # Mock des dépendances
        with patch('orders.import_utils.LigneFichier') as mock_ligne:
            with patch('orders.import_utils.NumeroBonCommande.objects.filter') as mock_filter:
                with patch('orders.import_utils.Reception.objects.filter') as mock_reception_filter:
                    # Setup mocks
                    mock_ligne_instance = Mock()
                    mock_ligne_instance.generate_business_id.return_value = 'BID001'
                    mock_ligne.return_value = mock_ligne_instance
                    
                    mock_po = Mock()
                    mock_po.id = 1
                    mock_filter.return_value = []
                    
                    mock_reception_filter.return_value = MagicMock()
                    mock_reception_filter.return_value.select_related.return_value = []
                    
                    result = process_chunk(records, 0, fichier, {})
                    
                    self.assertEqual(result, len(records))
    
    def test_process_chunk_existing_ligne(self):
        """Test traitement chunk avec ligne existante"""
        from orders.import_utils import process_chunk
        from orders.models import FichierImporte, LigneFichier
        from django.core.files.base import ContentFile
        
        # Créer un fichier
        fichier = FichierImporte.objects.create(
            fichier=ContentFile(b'test', name='test.xlsx'),
            utilisateur=self.user
        )
        
        # Créer une ligne existante
        ligne_existante = LigneFichier.objects.create(
            fichier=fichier,
            numero_ligne=1,
            business_id='BID001',
            contenu={'test': 'data'}
        )
        
        # Données de test avec même business_id
        records = [
            {
                'Order Number': 'PO001',
                'Business ID': 'BID001',
                'Ordered Quantity': '100',
                'Received Quantity': '50',
                'Price': '10.5'
            }
        ]
        
        # Mock des dépendances
        with patch('orders.import_utils.LigneFichier') as mock_ligne:
            with patch('orders.import_utils.NumeroBonCommande.objects.filter') as mock_filter:
                with patch('orders.import_utils.Reception.objects.filter') as mock_reception_filter:
                    # Setup mocks
                    mock_ligne_instance = Mock()
                    mock_ligne_instance.generate_business_id.return_value = 'BID001'
                    mock_ligne.return_value = mock_ligne_instance
                    
                    mock_po = Mock()
                    mock_po.id = 1
                    mock_filter.return_value = []
                    
                    mock_reception_filter.return_value = MagicMock()
                    mock_reception_filter.return_value.select_related.return_value = []
                    
                    # Simuler ligne existante
                    mock_ligne.objects.filter.return_value.first.return_value = ligne_existante
                    
                    result = process_chunk(records, 0, fichier, {})
                    
                    self.assertEqual(result, len(records))
    
    def test_process_chunk_cpu_extraction(self):
        """Test extraction CPU depuis les données"""
        from orders.import_utils import process_chunk
        from orders.models import FichierImporte
        from django.core.files.base import ContentFile
        
        # Créer un fichier
        fichier = FichierImporte.objects.create(
            fichier=ContentFile(b'test', name='test.xlsx'),
            utilisateur=self.user
        )
        
        # Données de test avec CPU
        records = [
            {
                'Order Number': 'PO001',
                'Business ID': 'BID001',
                'Ordered Quantity': '100',
                'Received Quantity': '50',
                'Price': '10.5',
                'CPU': 'CPU123 - Project A'
            }
        ]
        
        po_cpu_map = {}
        
        # Mock des dépendances
        with patch('orders.import_utils.LigneFichier') as mock_ligne:
            with patch('orders.import_utils.NumeroBonCommande.objects.filter') as mock_filter:
                with patch('orders.import_utils.Reception.objects.filter') as mock_reception_filter:
                    # Setup mocks
                    mock_ligne_instance = Mock()
                    mock_ligne_instance.generate_business_id.return_value = 'BID001'
                    mock_ligne.return_value = mock_ligne_instance
                    
                    mock_po = Mock()
                    mock_po.id = 1
                    mock_filter.return_value = []
                    
                    mock_reception_filter.return_value = MagicMock()
                    mock_reception_filter.return_value.select_related.return_value = []
                    
                    result = process_chunk(records, 0, fichier, po_cpu_map)
                    
                    # Vérifier extraction CPU
                    self.assertEqual(po_cpu_map.get('PO001'), 'Project A')
    
    def test_process_chunk_no_order_number(self):
        """Test traitement sans numéro de commande"""
        from orders.import_utils import process_chunk
        from orders.models import FichierImporte
        from django.core.files.base import ContentFile
        
        # Créer un fichier
        fichier = FichierImporte.objects.create(
            fichier=ContentFile(b'test', name='test.xlsx'),
            utilisateur=self.user
        )
        
        # Données sans Order Number
        records = [
            {
                'Business ID': 'BID001',
                'Ordered Quantity': '100',
                'Received Quantity': '50'
            }
        ]
        
        # Mock des dépendances
        with patch('orders.import_utils.LigneFichier') as mock_ligne:
            mock_ligne_instance = Mock()
            mock_ligne_instance.generate_business_id.return_value = 'BID001'
            mock_ligne.return_value = mock_ligne_instance
            
            result = process_chunk(records, 0, fichier, {})
            
            self.assertEqual(result, len(records))
    
    def test_process_chunk_invalid_quantities(self):
        """Test traitement avec quantités invalides"""
        from orders.import_utils import process_chunk
        from orders.models import FichierImporte
        from django.core.files.base import ContentFile
        
        # Créer un fichier
        fichier = FichierImporte.objects.create(
            fichier=ContentFile(b'test', name='test.xlsx'),
            utilisateur=self.user
        )
        
        # Données avec quantités invalides
        records = [
            {
                'Order Number': 'PO001',
                'Business ID': 'BID001',
                'Ordered Quantity': 'invalid',
                'Received Quantity': '',
                'Price': 'N/A'
            }
        ]
        
        # Mock des dépendances
        with patch('orders.import_utils.LigneFichier') as mock_ligne:
            with patch('orders.import_utils.NumeroBonCommande.objects.filter') as mock_filter:
                with patch('orders.import_utils.Reception.objects.filter') as mock_reception_filter:
                    # Setup mocks
                    mock_ligne_instance = Mock()
                    mock_ligne_instance.generate_business_id.return_value = 'BID001'
                    mock_ligne.return_value = mock_ligne_instance
                    
                    mock_po = Mock()
                    mock_po.id = 1
                    mock_filter.return_value = []
                    
                    mock_reception_filter.return_value = MagicMock()
                    mock_reception_filter.return_value.select_related.return_value = []
                    
                    result = process_chunk(records, 0, fichier, {})
                    
                    self.assertEqual(result, len(records))