# tests/test_forms.py
import pytest
from unittest.mock import Mock, patch
from orders.forms import UploadFichierForm


class TestUploadFichierForm:
    """Tests pour le formulaire d'upload de fichier"""

    def test_form_has_correct_fields(self):
        """Test que le formulaire a les bons champs"""
        form = UploadFichierForm()
        assert 'fichier' in form.fields

    def test_form_valid_with_file(self):
        """Test que le formulaire est valide avec un fichier"""
        file_mock = Mock()
        file_mock.name = 'test.csv'
        form = UploadFichierForm(files={'fichier': file_mock})
        assert form.is_valid()

    def test_form_invalid_without_file(self):
        """Test que le formulaire est invalide sans fichier"""
        form = UploadFichierForm(data={})
        assert not form.is_valid()
        assert 'fichier' in form.errors

    def test_form_meta_configuration(self):
        """Test la configuration Meta du formulaire"""
        assert UploadFichierForm.Meta.model.__name__ == 'FichierImporte'
        assert UploadFichierForm.Meta.fields == ['fichier']
        assert UploadFichierForm.Meta.labels['fichier'] == 'File'
        assert 'fichier' in UploadFichierForm.Meta.help_texts

    def test_form_save(self, db):
        """Test la sauvegarde du formulaire"""
        file_mock = Mock()
        file_mock.name = 'test.csv'
        
        form = UploadFichierForm(files={'fichier': file_mock})
        assert form.is_valid()
        
        # Patch du save du modèle pour éviter l'écriture en base
        with patch('orders.models.FichierImporte.save') as mock_save:
            form.save()
            mock_save.assert_called_once()