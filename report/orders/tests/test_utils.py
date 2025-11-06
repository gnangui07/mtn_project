# tests/test_utils.py
import os
import tempfile
import pandas as pd
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
        os.makedirs(test_dir, exist_ok=True)
        
        test_file_path = os.path.join(test_dir, 'test.csv')
        with open(test_file_path, 'w', encoding='utf-8') as f:
            f.write(self.csv_data)
        
        # Tester l'extraction
        data, count = extraire_depuis_fichier_relatif('tests/test.csv', 'csv')
        
        self.assertEqual(count, 2)
        self.assertEqual(len(data), 2)
        
        # Nettoyer
        os.remove(test_file_path)

    def test_extraire_depuis_fichier_relatif_extension_inconnue(self):
        """Test l'extraction avec une extension inconnue"""
        # Créer un fichier binaire
        bin_path = os.path.join(self.temp_dir, 'test.bin')
        with open(bin_path, 'wb') as f:
            f.write(b'test binary data')
        
        # Tester l'extraction - devrait retourner des bytes hexadécimaux
        data, count = extraire_depuis_fichier_relatif(bin_path, 'bin')
        
        self.assertEqual(count, 0)
        self.assertIn('raw_bytes_hex', data)
        self.assertEqual(data['raw_bytes_hex'], '746573742062696e6172792064617461')

    def test_generate_report_number(self):
        """Test la génération de numéros de rapport"""
        report_number = generate_report_number()
        
        # Vérifier que c'est une chaîne
        self.assertIsInstance(report_number, str)
        
        # Vérifier que c'est un nombre entre 1000 et 9999
        number = int(report_number)
        self.assertGreaterEqual(number, 1000)
        self.assertLessEqual(number, 9999)
        
        # Tester plusieurs générations pour s'assurer qu'elles sont différentes
        numbers = {generate_report_number() for _ in range(10)}
        self.assertGreaterEqual(len(numbers), 1)  # Au moins 1 nombre unique

    def test_extraire_depuis_fichier_relatif_erreur(self):
        """Test l'extraction avec un fichier qui génère une erreur"""
        # Créer un fichier Excel corrompu
        corrupt_excel_path = os.path.join(self.temp_dir, 'corrupt.xlsx')
        with open(corrupt_excel_path, 'w', encoding='utf-8') as f:
            f.write('not a valid excel file')
        
        # Tester l'extraction - devrait retourner une erreur
        data, count = extraire_depuis_fichier_relatif(corrupt_excel_path, 'xlsx')
        
        self.assertEqual(count, 0)
        self.assertIn('error', data)
        self.assertIn('Extraction failed', data['error'])