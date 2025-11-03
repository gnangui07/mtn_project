"""
Tests pour utils.extraire_depuis_fichier_relatif (cas CSV minimal)
"""
import os
import io
import pytest
from django.conf import settings
from django.core.files.storage import default_storage

from orders.utils import extraire_depuis_fichier_relatif


@pytest.mark.django_db
def test_extraire_depuis_fichier_relatif_csv(tmp_path, settings):
    # Préparer un faux MEDIA_ROOT
    media_root = tmp_path / "media"
    media_root.mkdir(parents=True, exist_ok=True)
    settings.MEDIA_ROOT = str(media_root)

    # Créer un petit CSV dans MEDIA_ROOT/uploads
    uploads_dir = media_root / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    rel_path = os.path.join('uploads', 'mini_utils.csv')
    abs_path = uploads_dir / 'mini_utils.csv'
    abs_path.write_text("Order,Qty\nPO-1,3\n", encoding='utf-8')

    contenu, nb = extraire_depuis_fichier_relatif(rel_path, 'csv')
    assert isinstance(contenu, list)
    assert nb == 1
    # Vérifier le contenu
    assert contenu[0].get('Order') == 'PO-1'
