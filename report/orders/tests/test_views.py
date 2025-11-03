"""
Tests des vues de l'app orders (ultra simples):
- Vues protégées → redirigent si non connecté; 200 si connecté.
- Pages ouvertes → répondent 200.
- Recherche PO (search_bon) → redirige sans param.
- Téléchargements/accès fichier → 404 si identifiant inexistant.
"""
import pytest
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile

from orders.models import FichierImporte, LigneFichier, NumeroBonCommande, VendorEvaluation, TimelineDelay


@pytest.mark.django_db
def test_requires_login_redirects(client):
    # Vues protégées (doivent rediriger si non connecté)
    protected = [
        'orders:msrn_archive',
        'orders:accueil',
        'orders:download_msrn_report',  # nécessite un report_id; on met un id bidon
        'orders:po_progress_monitoring',
        'orders:vendor_evaluation_list',
        'orders:vendor_ranking',
    ]
    for name in protected:
        if name == 'orders:download_msrn_report':
            url = reverse(name, kwargs={'report_id': 123456})
        else:
            url = reverse(name)
        resp = client.get(url)
        assert resp.status_code in (301, 302)


# -------------------------------------------------
# vendor_evaluation / vendor_evaluation_detail
# -------------------------------------------------


@pytest.mark.django_db
def test_vendor_evaluation_and_detail_access_by_service(client, user_active):
    # Donner un service à l'utilisateur qui matche le CPU du PO
    user_active.service = 'ITS'
    user_active.save(update_fields=['service'])
    client.login(username=user_active.email, password='Secret123!')

    # Créer un PO accessible (cpu='ITS')
    po = NumeroBonCommande.objects.create(numero='PO-SERV-1', cpu='ITS')

    # Page d'évaluation (formulaire)
    url_eval = reverse('orders:vendor_evaluation', kwargs={'bon_commande_id': po.id})
    resp_eval = client.get(url_eval)
    assert resp_eval.status_code == 200

    # Créer une évaluation et tester la page de détail
    ve = VendorEvaluation.objects.create(
        bon_commande=po,
        supplier='ACME',
        delivery_compliance=7,
        delivery_timeline=7,
        advising_capability=7,
        after_sales_qos=7,
        vendor_relationship=7,
        evaluator=user_active,
    )
    url_detail = reverse('orders:vendor_evaluation_detail', kwargs={'evaluation_id': ve.id})
    resp_detail = client.get(url_detail)
    assert resp_detail.status_code == 200


# ---------------------------------
# timeline_delays / update_delays
# ---------------------------------


@pytest.mark.django_db
def test_timeline_delays_and_update(client, user_active):
    # Accès par service
    user_active.service = 'ITS'
    user_active.save(update_fields=['service'])
    client.login(username=user_active.email, password='Secret123!')

    po = NumeroBonCommande.objects.create(numero='PO-TL-1', cpu='ITS')
    tl = TimelineDelay.objects.create(
        bon_commande=po,
        comment_mtn='ok',
        comment_force_majeure='ok',
        comment_vendor='ok',
        delay_part_mtn=1,
        delay_part_force_majeure=1,
        delay_part_vendor=1,
    )

    # GET timeline
    url_tl = reverse('orders:timeline_delays', kwargs={'bon_commande_id': po.id})
    resp_tl = client.get(url_tl)
    assert resp_tl.status_code == 200

    # POST update_delays (JSON)
    url_upd = reverse('orders:update_delays', kwargs={'timeline_id': tl.id})
    payload = {
        'comment_mtn': 'mise a jour',
        'comment_force_majeure': 'maj',
        'comment_vendor': 'maj',
        'delay_part_mtn': 2,
        'delay_part_force_majeure': 1,
        'delay_part_vendor': 2
    }
    resp_upd = client.post(url_upd, data=payload, content_type='application/json')
    # Réponse JSON succès (200)
    assert resp_upd.status_code == 200
    assert resp_upd.json().get('success') is True


# ---------------------------------
# telecharger_fichier (existant)
# ---------------------------------


@pytest.mark.django_db
def test_telecharger_fichier_existing_returns_attachment(client):
    # Créer un fichier avec une ligne pour permettre l'export
    upload = SimpleUploadedFile('dl.csv', b'Order,Qty\nPO-DL,2\n', content_type='text/csv')
    fichier = FichierImporte.objects.create(fichier=upload)

    url = reverse('orders:telecharger_fichier', kwargs={'fichier_id': fichier.id})
    resp = client.get(url)
    assert resp.status_code == 200
    # Vérifier l'entête de téléchargement
    assert 'Content-Disposition' in resp.headers
    assert 'attachment' in resp.headers['Content-Disposition']


@pytest.mark.django_db
def test_basic_pages_ok_when_logged(client, user_active):
    client.login(username=user_active.email, password='Secret123!')
    names = [
        'orders:msrn_archive',
        'orders:accueil',
        'orders:po_progress_monitoring',
        'orders:vendor_evaluation_list',
        'orders:vendor_ranking',
        'orders:consultation',  # ouverte
    ]
    for name in names:
        url = reverse(name)
        resp = client.get(url)
        assert resp.status_code == 200


@pytest.mark.django_db
def test_search_bon_autocomplete_with_q_returns_json(client):
    url = reverse('orders:search_bon')
    resp = client.get(url, {'q': 'PO-123', 'limit': 5})
    # L'autocomplete renvoie du JSON (même vide) avec 200
    assert resp.status_code == 200

@pytest.mark.django_db
def test_download_msrn_report_missing_file_redirects(client, user_active):
    client.login(username=user_active.email, password='Secret123!')
    url = reverse('orders:download_msrn_report', kwargs={'report_id': 999999})
    resp = client.get(url)
    # Si l'id n'existe pas, la vue gère l'exception et redirige vers l'archive
    assert resp.status_code in (301, 302)


@pytest.mark.django_db
def test_details_bon_missing_file_returns_404(client):
    # details_bon avec id inconnu → 404
    url = reverse('orders:details_bon', kwargs={'bon_id': 999999})
    resp = client.get(url)
    assert resp.status_code == 404


@pytest.mark.django_db
def test_import_fichier_get_shows_form(client):
    url = reverse('orders:import_fichier')
    resp = client.get(url)
    assert resp.status_code == 200


@pytest.mark.django_db
def test_import_fichier_post_invalid_shows_form(client):
    # POST sans fichier → formulaire invalide → rester sur la page
    url = reverse('orders:import_fichier')
    resp = client.post(url, {})
    assert resp.status_code == 200


@pytest.mark.django_db
def test_telecharger_fichier_missing_returns_404(client):
    url = reverse('orders:telecharger_fichier', kwargs={'fichier_id': 999999})
    resp = client.get(url)
    assert resp.status_code == 404


# ------------------------------
# Tests avec données minimales
# ------------------------------


@pytest.mark.django_db
def test_details_bon_search_not_found_redirects(client):
    # On utilise la route dédiée de recherche
    url = reverse('orders:search_bon')
    resp = client.get(url, {'order_number': 'PO-XYZ-UNKNOWN'})
    # La vue redirige vers l'accueil avec un message si non trouvé
    assert resp.status_code in (301, 302)


@pytest.mark.django_db
def test_details_bon_search_found_returns_200(client, user_active):
    # Préparer un FichierImporte minimal (l'import auto crée les lignes et associe le PO)
    dummy = SimpleUploadedFile('test.csv', b'Order,Qty\nPO-123,5\n', content_type='text/csv')
    FichierImporte.objects.create(fichier=dummy, utilisateur=user_active)

    # Appeler la route de recherche avec order_number existant et suivre la redirection
    url = reverse('orders:search_bon')
    client.login(username=user_active.email, password='Secret123!')
    resp = client.get(url, {'order_number': 'PO-123'}, follow=True)
    # Après redirection, on doit afficher la page de détails (200)
    assert resp.status_code == 200


@pytest.mark.django_db
def test_import_fichier_post_valid_redirects(client):
    # Upload d'un petit CSV valide
    content = b'Order,Qty\nPO-999,1\n'
    upload = SimpleUploadedFile('mini.csv', content, content_type='text/csv')
    url = reverse('orders:import_fichier')
    resp = client.post(url, {'fichier': upload})
    # En cas de succès, redirige vers details_bon avec l'id du fichier
    assert resp.status_code in (301, 302)
