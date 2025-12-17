from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q, Sum, Count, F, ExpressionWrapper, DecimalField, Case, When, Value, Max, Subquery, OuterRef
from django.db.models.functions import Coalesce
from django.http import JsonResponse, HttpResponse, Http404
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.urls import reverse
from decimal import Decimal
import json
import logging
import openpyxl
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter
import os
from decimal import Decimal
from datetime import datetime
from .models import NumeroBonCommande, Reception, FichierImporte, LigneFichier, MSRNReport

from .models import (
    FichierImporte, LigneFichier, NumeroBonCommande, Reception, ActivityLog, MSRNReport
)
from .forms import UploadFichierForm
from . import reports
from django.contrib.auth.decorators import login_required
from django.conf import settings
import pandas as pd
from .models import FichierImporte, LigneFichier, NumeroBonCommande, Reception, import_or_update_fichier, MSRNReport
from .forms import UploadFichierForm
from django.db.models import Q, F, Count

logger = logging.getLogger(__name__)


def filter_bons_by_user_service(queryset, user):
    """
    But:
    - Ne montrer que les bons (PO) que l’utilisateur a le droit de voir (par service).

    Étapes:
    1) Si superuser → retourner tout.
    2) Sinon, lire la liste des services de l’utilisateur.
    3) Si liste vide → retourner rien.
    4) Sinon, filtrer les bons dont le CPU correspond à l’un de ces services.

    Entrées:
    - queryset (QuerySet[NumeroBonCommande]): liste de départ des bons.
    - user (User): utilisateur connecté.

    Sorties:
    - QuerySet filtré (seulement les bons visibles par cet utilisateur).
    """
    # Le superuser voit tout
    if user.is_superuser:
        return queryset
    
    # Récupérer la liste des services de l'utilisateur
    services_list = user.get_services_list() if hasattr(user, 'get_services_list') else []
    
    # Si l'utilisateur n'a pas de service, il ne voit rien
    if not services_list:
        return queryset.none()
    
    # Filtrer par CPU en utilisant une requête SQL directe (très rapide)
    # Utilise __in pour chercher dans la liste des services autorisés
    # Avec __iexact pour chaque service (insensible à la casse)
    from django.db.models import Q
    
    # Construire une requête OR pour chaque service
    query = Q()
    for service in services_list:
        query |= Q(cpu__iexact=service)
    
    return queryset.filter(query)


@login_required
def msrn_archive(request):
    """
    But:
    - Afficher l’archive des rapports MSRN (liste paginée avec recherche et filtres).

    Étapes:
    1) Charger la liste des rapports triés par date.
    2) Restreindre aux POs autorisés (services de l’utilisateur) si non‑superuser.
    3) Appliquer les filtres de recherche (q, with_retention).
    4) Paginer le résultat et rendre la page HTML.

    Entrées:
    - request (HttpRequest) GET:
      - q (str, optionnel): recherche sur numéro de rapport/PO/valeur numérique proche.
      - with_retention ('1'|'0'|None): filtre sur le taux de rétention.
      - page (int, optionnel): numéro de page.

    Sorties:
    - Template HTML `orders/msrn_archive.html` avec la page de résultats.
    """
    # Imports locaux pour éviter d'altérer les imports globaux existants
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    from django.db.models import Q
    from .models import MSRNReport, NumeroBonCommande

    base_qs = MSRNReport.objects.select_related('bon_commande').order_by('-created_at')
    qs = base_qs

    # Restreindre l'archive MSRN aux POs accessibles par l'utilisateur (filtrage par service/CPU)
    if not request.user.is_superuser:
        allowed_bons = filter_bons_by_user_service(
            NumeroBonCommande.objects.all(),
            request.user
        )
        # Debug pour comprendre le filtrage par services
        print("DEBUG msrn allowed_bons:", list(allowed_bons.values_list('numero', 'cpu')))
        qs = qs.filter(bon_commande__in=allowed_bons)
        print("DEBUG msrn qs_count:", qs.count())

    # Recherche simple (numéro de rapport, PO) + recherche par taux d'avancement (numérique)
    q = (request.GET.get('q') or '').strip()
    if q:
        # Filtrer par report_number et numéro de bon
        qs = qs.filter(
            Q(report_number__icontains=q)
            | Q(bon_commande__numero__icontains=q)
        )

        # Essayer d'interpréter la recherche comme un taux d'avancement numérique
        q_clean = q.replace('%', '').replace(',', '.').strip()
        try:
            q_rate = float(q_clean)
        except (ValueError, TypeError):
            q_rate = None

        if q_rate is not None:
            # Rechercher par taux d'avancement approximatif sur l'ensemble des rapports
            progress_ids = []
            for r in base_qs:
                # Utiliser le snapshot du taux d'avancement stocké dans le rapport
                taux = float(r.progress_rate_snapshot) if r.progress_rate_snapshot is not None else None
                if taux is not None:
                    # Correspondance si la valeur arrondie à 2 décimales contient la chaîne saisie
                    # ou si l'écart absolu est petit (tolérance 0.1%)
                        if (
                            abs(taux - q_rate) <= 0.1
                            or (f"{taux:.0f}" == q_clean)
                            or (f"{taux:.2f}".startswith(q_clean))
                        ):
                            progress_ids.append(r.id)

            if progress_ids:
                qs = qs | base_qs.filter(id__in=progress_ids)

    # Filtre optionnel par email/identifiant du générateur du MSRN
    user_email = (request.GET.get('user_email') or '').strip()
    if user_email:
        qs = qs.filter(user__icontains=user_email)

    # Filtre optionnel: with_retention=1 (seulement >0), =0 (aucune), sinon tous
    with_retention = request.GET.get('with_retention')
    if with_retention == '1':
        qs = qs.filter(retention_rate__gt=0)
    elif with_retention == '0':
        qs = qs.filter(retention_rate=0)

    # Pagination
    paginator = Paginator(qs, 25)
    page_number = request.GET.get('page') or 1
    try:
        reports = paginator.page(page_number)
    except PageNotAnInteger:
        reports = paginator.page(1)
    except EmptyPage:
        reports = paginator.page(paginator.num_pages)

    context = {
        'reports': reports,
        'q': q,
        'with_retention': with_retention,
        'user_email': user_email,
    }
    return render(request, 'orders/msrn_archive.html', context)


@require_http_methods(["GET"])
@login_required
def download_msrn_report(request, report_id):
    """
    But:
    - Télécharger un rapport MSRN existant (PDF) depuis l’archive.

    Étapes:
    1) Retrouver le rapport par son id.
    2) Vérifier que le fichier PDF existe.
    3) S’il existe → renvoyer le PDF en téléchargement.
    4) Sinon → message d’erreur et retour à l’archive.

    Entrées:
    - request (HttpRequest)
    - report_id (int): identifiant du MSRNReport.

    Sorties:
    - HttpResponse (PDF en attachement) ou redirection avec message d’erreur.
    """
    try:
        # Récupérer le rapport MSRN
        msrn_report = get_object_or_404(MSRNReport, id=report_id)
        
        # Vérifier que le fichier PDF existe
        if not msrn_report.pdf_file or not os.path.exists(msrn_report.pdf_file.path):
            messages.error(request, "Le fichier PDF du rapport MSRN n'existe pas.")
            return redirect('orders:msrn_archive')
        
        # Préparer la réponse HTTP pour le téléchargement
        with open(msrn_report.pdf_file.path, 'rb') as pdf_file:
            response = HttpResponse(pdf_file.read(), content_type='application/pdf')
            filename = f"MSRN-{msrn_report.report_number}.pdf"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
            
    except Exception as e:
        logger.error(f"Erreur lors du téléchargement du rapport MSRN {report_id}: {str(e)}")
        messages.error(request, "Erreur lors du téléchargement du rapport MSRN.")
        return redirect('orders:msrn_archive')


@login_required
def accueil(request):
    """
    But:
    - Page d'entrée: lister les POs accessibles selon le service de l'utilisateur.
    
    Performance:
    - Cache Redis par utilisateur (5 min) pour éviter les requêtes répétées.

    Entrées:
    - request (HttpRequest)

    Sorties:
    - Template HTML `orders/reception.html` avec la liste des POs.
    """
    from .models import NumeroBonCommande
    from django.core.cache import cache
    
    # Clé de cache spécifique à l'utilisateur
    cache_key = f"accueil_bons_{request.user.id}"
    
    # Essayer de récupérer depuis le cache
    cached_bons = cache.get(cache_key)
    
    if cached_bons is not None and isinstance(cached_bons, list) and cached_bons and all(
        isinstance(item, dict) and 'numero' in item and 'fichier_id' in item for item in cached_bons
    ):
        numeros_bons = cached_bons
    else:
        # Récupérer les numéros de bons avec informations nécessaires pour le dropdown
        qs = NumeroBonCommande.objects.all().order_by('numero')
        if not request.user.is_superuser:
            services_list = request.user.get_services_list() if hasattr(request.user, 'get_services_list') else []
            if services_list:
                services_upper = [s.upper() for s in services_list]
                qs = qs.filter(cpu__in=services_upper)
            else:
                qs = qs.none()
        numeros_bons = []
        # Import local pour éviter dépendances globales
        try:
            from .models import VendorEvaluation
        except Exception:
            VendorEvaluation = None
        for bon in qs:
            # Fichier le plus récent pour redirection
            fichier_id = None
            latest_file = None
            try:
                latest_file = bon.fichiers.order_by('-date_importation').first()
                if latest_file:
                    fichier_id = latest_file.id
            except Exception:
                fichier_id = None
            # Supplier: première occurrence rapide
            supplier = None
            try:
                if VendorEvaluation is not None:
                    ve = VendorEvaluation.objects.filter(bon_commande=bon).values('supplier').first()
                    supplier = ve['supplier'] if ve and ve.get('supplier') else None
            except Exception:
                supplier = None
            # Essai via business_id pour récupérer Supplier sans parcourir tout le fichier
            if supplier is None:
                try:
                    from .models import Reception, LigneFichier
                    rec = Reception.objects.filter(bon_commande=bon).values('business_id', 'fichier_id').first()
                    if rec and rec.get('business_id') and rec.get('fichier_id'):
                        lf = LigneFichier.objects.filter(
                            fichier_id=rec['fichier_id'],
                            business_id=rec['business_id']
                        ).values('contenu').first()
                        contenu = lf['contenu'] if lf and lf.get('contenu') else {}
                        def _norm(s: str):
                            return ' '.join(str(s).strip().lower().replace('_', ' ').replace('-', ' ').split())
                        for k, v in (contenu.items() if isinstance(contenu, dict) else []):
                            if not k:
                                continue
                            nk = _norm(k)
                            if v and ('supplier' in nk or 'vendor' in nk or 'fournisseur' in nk or 'vendeur' in nk):
                                supplier = str(v)
                                break
                except Exception:
                    supplier = None
            if supplier is None and latest_file:
                try:
                    first_line = latest_file.lignes.order_by('numero_ligne').first()
                    contenu = getattr(first_line, 'contenu', {}) or {}
                    def _norm(s: str):
                        return ' '.join(str(s).strip().lower().replace('_', ' ').replace('-', ' ').split())
                    for k, v in contenu.items():
                        if not k:
                            continue
                        nk = _norm(k)
                        if v and ('supplier' in nk or 'vendor' in nk or 'fournisseur' in nk or 'vendeur' in nk):
                            supplier = str(v)
                            break
                except Exception:
                    supplier = None
            numeros_bons.append({
                'id': bon.id,
                'numero': bon.numero,
                'cpu': bon.cpu,
                'fichier_id': fichier_id,
                'supplier': supplier or 'N/A',
            })
        # Mettre en cache pendant 5 minutes
        cache.set(cache_key, numeros_bons, timeout=300)
    
    # Afficher un message informatif si aucun bon n'est accessible
    if not numeros_bons and not request.user.is_superuser:
        services_list = request.user.get_services_list() if hasattr(request.user, 'get_services_list') else []
        if not services_list:
            messages.info(request, "⚠️ Votre compte n'est pas associé à un service. Veuillez contacter l'administrateur.")
        else:
            services_str = ', '.join(services_list)
            messages.info(request, f"ℹ️ Aucun bon de commande disponible pour vos services ({services_str}).")
    
    return render(request, 'orders/reception.html', {
        'numeros_bons': numeros_bons,
    })


def import_fichier(request):
    """But:
    - Importer un fichier (Excel, CSV, etc.) et extraire automatiquement les données.

    Mode async (recommandé pour les gros fichiers):
    - Si ?async=1 : Sauvegarde le fichier temporairement, lance la tâche Celery
    - Sinon : Import synchrone classique

    Entrées:
    - request (HttpRequest) GET/POST (fichier dans request.FILES en POST).

    Sorties:
    - GET → template `orders/reception.html` avec le formulaire.
    - POST async → JsonResponse avec task_id pour polling.
    - POST sync → redirection `orders:details_bon`.
    """
    # Import Celery task avec fallback
    try:
        from .tasks import import_fichier_task
        from .task_status_api import register_user_task
        CELERY_IMPORT_AVAILABLE = True
    except ImportError:
        CELERY_IMPORT_AVAILABLE = False
    
    if request.method == 'POST':
        form = UploadFichierForm(request.POST, request.FILES)
        fichier_upload = None
        if form.is_valid():
            fichier_upload = form.cleaned_data['fichier']
        else:
            # Fallback: utiliser directement le fichier envoyé si présent
            fichier_upload = request.FILES.get('fichier')

        if fichier_upload:
            # ===== MODE ASYNC =====
            async_mode = request.GET.get('async') == '1' or request.POST.get('async') == '1'
            
            if async_mode and CELERY_IMPORT_AVAILABLE:
                try:
                    import tempfile
                    import os
                    from django.conf import settings
                    
                    # Sauvegarder le fichier temporairement
                    temp_dir = os.path.join(settings.MEDIA_ROOT, 'imports', 'temp')
                    os.makedirs(temp_dir, exist_ok=True)
                    
                    # Nom unique pour le fichier
                    import time
                    temp_filename = f"import_{request.user.id}_{int(time.time())}_{fichier_upload.name}"
                    temp_path = os.path.join(temp_dir, temp_filename)
                    
                    # Sauvegarder le fichier
                    with open(temp_path, 'wb+') as destination:
                        for chunk in fichier_upload.chunks():
                            destination.write(chunk)
                    
                    # Lancer la tâche Celery
                    task = import_fichier_task.delay(
                        file_path=temp_path,
                        user_id=request.user.id,
                        original_filename=fichier_upload.name
                    )
                    
                    # Enregistrer la tâche pour l'utilisateur
                    try:
                        register_user_task(request.user.id, task.id, 'import_fichier')
                    except Exception:
                        pass
                    
                    # Si c'est une requête AJAX, retourner JSON
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': True,
                            'async': True,
                            'task_id': task.id,
                            'message': 'Import démarré en arrière-plan. Vous serez notifié quand le fichier sera traité.',
                            'poll_url': f'/orders/api/task-status/{task.id}/'
                        })
                    else:
                        # Sinon, rediriger vers une page de statut
                        messages.info(request, f'Import en cours en arrière-plan (ID: {task.id}). Vous pouvez continuer à naviguer.')
                        return redirect('orders:accueil')
                        
                except Exception as e:
                    logger.error(f"Erreur lors du démarrage de l'import async: {e}")
                    # Fallback vers le mode sync
                    messages.warning(request, "Mode async non disponible, import synchrone en cours...")
            
            # ===== MODE SYNC (par défaut ou fallback) =====
            fichier, _created = import_or_update_fichier(fichier_upload, utilisateur=request.user)
            messages.success(request, f'Fichier importé avec succès. {getattr(fichier, "nombre_lignes", 0)} lignes extraites.')
            return redirect('orders:details_bon', bon_id=fichier.id)
    else:
        form = UploadFichierForm()

    return render(request, 'orders/reception.html', {
        'form': form,
    })


def consultation(request):
    """
    But:
    - Afficher la page de consultation (présentation simple pour l’instant).

    Étapes:
    1) Rendre le template existant.

    Entrées:
    - request (HttpRequest)

    Sorties:
    - Template HTML `orders/consultation.html`.
    """
    # Dans le futur, cette vue pourrait offrir des filtres et des fonctionnalités de recherche avancées
    # Pour l'instant, elle affiche simplement le template avec un message
    return render(request, 'orders/consultation.html')


def details_bon(request, bon_id):
    """
    But:
    - Afficher proprement les données d’un fichier importé (le “bon”).

    Étapes:
    1) Si `bon_id='search'`, retrouver le fichier à partir d’un numéro de PO.
    2) Charger les lignes du fichier et leurs informations associées.
    3) Normaliser les en‑têtes et valeurs pour un tableau lisible.
    4) Joindre les réceptions existantes si présentes (quantités/montants).
    5) Déduire et afficher des métriques (taux, montants, devise, etc.).
    6) Rendre la page de détails.

    Entrées:
    - request (HttpRequest) GET:
      - selected_order_number (str, optionnel)
      - order_number (str, si bon_id='search')
    - bon_id (int | 'search')

    Sorties:
    - Template HTML `orders/detail_bon.html` avec les données, entêtes et métriques.
    """
    selected_order_number = None

    if request.method == 'GET' and 'selected_order_number' in request.GET:
        selected_order_number = request.GET.get('selected_order_number')

    if bon_id == 'search' and request.method == 'GET' and 'order_number' in request.GET:
        selected_order_number = request.GET.get('order_number')
        try:
            bon_commande = NumeroBonCommande.objects.get(numero=selected_order_number)
            
            # Vérifier que l'utilisateur a accès à ce bon (filtrage par service)
            bons_accessibles = filter_bons_by_user_service(NumeroBonCommande.objects.filter(id=bon_commande.id), request.user)
            if not bons_accessibles.exists():
                messages.error(request, f'You do not have access to purchase order {selected_order_number}.')
                return redirect('orders:accueil')
            
            fichier = bon_commande.fichiers.order_by('-date_importation').first()
            if not fichier:
                messages.warning(request, f'Purchase order {selected_order_number} exists but is not associated with any file.')
                return redirect('orders:accueil')
        except NumeroBonCommande.DoesNotExist:
            messages.error(request, f'Purchase order {selected_order_number} not found.')
            return redirect('orders:accueil')
    else:
        fichier = get_object_or_404(FichierImporte, id=bon_id)
        if not selected_order_number and fichier.bons_commande.exists():
            selected_order_number = fichier.bons_commande.first().numero
        
    # Vérifier si le fichier physique existe
    file_exists = False
    file_size = None
    try:
        if getattr(fichier, 'fichier', None) and getattr(fichier.fichier, 'path', None):
            file_exists = os.path.exists(fichier.fichier.path)
            if file_exists:
                try:
                    # L'accès à .size peut lever une erreur si le backend ne trouve pas le fichier
                    file_size = fichier.fichier.size
                except Exception:
                    file_size = None
        else:
            file_exists = False
    except Exception:
        file_exists = False
        file_size = None

    if getattr(fichier, 'fichier', None) and not file_exists:
        messages.warning(request, f"Le fichier original '{os.path.basename(fichier.fichier.name)}' est manquant. Les données en mémoire seront utilisées si disponibles.")

    bon_number = selected_order_number if selected_order_number else f'PO-{fichier.id}'
    
    # Récupérer le bon de commande pour l'ID
    bon_commande = None
    if selected_order_number:
        try:
            bon_commande = NumeroBonCommande.objects.get(numero=selected_order_number)
        except NumeroBonCommande.DoesNotExist:
            pass
    
    # Récupérer les données depuis le modèle LigneFichier
    try:
        # Initialiser les structures de données
        contenu_data = []
        receptions = {}

        # Préparer le queryset de lignes en limitant au maximum le volume chargé
        lignes_fichier_qs = None

        if selected_order_number:
            try:
                # Récupérer le bon de commande
                bon_commande = NumeroBonCommande.objects.get(numero=selected_order_number)

                # Récupérer les réceptions pour ce bon de commande et ce fichier
                receptions_queryset = Reception.objects.filter(
                    bon_commande=bon_commande,
                    fichier=fichier
                ).select_related('fichier', 'bon_commande').order_by('business_id')

                business_ids = []
                # Convertir les réceptions en dictionnaire indexé par business_id
                for reception in receptions_queryset:
                    if reception.business_id:
                        bid_str = str(reception.business_id)
                        receptions[bid_str] = {
                            'quantity_delivered': reception.quantity_delivered,
                            'ordered_quantity': reception.ordered_quantity,
                            'quantity_not_delivered': reception.quantity_not_delivered,
                            'amount_delivered': reception.amount_delivered,
                            'amount_not_delivered': reception.amount_not_delivered,
                            'quantity_payable': reception.quantity_payable,
                            'unit_price': reception.unit_price,
                            'amount_payable': reception.amount_payable,  # Use the desired header
                        }
                        business_ids.append(reception.business_id)

                # Limiter les lignes aux seules lignes du bon courant si des business_id sont disponibles
                if business_ids:
                    lignes_fichier_qs = LigneFichier.objects.filter(
                        fichier=fichier,
                        business_id__in=business_ids,
                    ).order_by('numero_ligne')
                else:
                    # Fallback: aucune réception trouvée, on charge toutes les lignes du fichier
                    lignes_fichier_qs = LigneFichier.objects.filter(fichier=fichier).order_by('numero_ligne')

            except NumeroBonCommande.DoesNotExist:
                # Fallback si le bon n'existe pas: charger toutes les lignes comme avant
                lignes_fichier_qs = LigneFichier.objects.filter(fichier=fichier).order_by('numero_ligne')
        else:
            # Aucun numéro de bon sélectionné: comportement historique
            lignes_fichier_qs = LigneFichier.objects.filter(fichier=fichier).order_by('numero_ligne')

        # Ajouter une fonction utilitaire pour extraire les valeurs numériques
        def extract_numeric_values(data):
            numeric_fields = ['Ordered Quantity', 'Quantity Delivered', 'Quantity Not Delivered', 'Price']
            for field in numeric_fields:
                if field in data:
                    try:
                        # Convertir en float puis en int si possible
                        value = data[field]
                        if isinstance(value, str):
                            value = value.replace(',', '').strip()
                        num = float(value) if value not in (None, '') else 0.0
                        if num.is_integer():
                            data[field] = int(num)
                        else:
                            data[field] = num
                    except (TypeError, ValueError):
                        data[field] = 0
            return data

        # Créer une liste des données avec l'ID de la ligne
        for ligne in lignes_fichier_qs:
            data = ligne.contenu.copy()
            data['_business_id'] = ligne.business_id  # Store business ID instead of row index
            data = extract_numeric_values(data)  # Extraire les valeurs numériques
            contenu_data.append(data)

    except Exception as e:
        messages.error(request, f"Erreur lors de la récupération des données : {str(e)}")
        contenu_data = []
        receptions = {}
        
    raw_data = []
    headers = []
    colonne_order = None
    taux_avancement = 0
    montant_total_recu = 0
    montant_total = 0
    supplier = "N/A"
    currency = "XOF"
    
    if selected_order_number:
        try:
            bon_commande = NumeroBonCommande.objects.get(numero=selected_order_number)
            taux_avancement = bon_commande.taux_avancement()
            montant_total_recu = bon_commande.montant_recu()
            montant_total = bon_commande.montant_total()
            # Récupérer le fournisseur et la devise
            supplier = bon_commande.get_supplier()
            currency = bon_commande.get_currency()
        except NumeroBonCommande.DoesNotExist:
            pass

    # Fonction de normalisation tolérante des en-têtes (comme dans export_po_progress_monitoring)
    def normalize_header(s: str):
        """Normalise un en-tête: strip -> lower -> remplace _ et - par espace -> compresse espaces"""
        return ' '.join(str(s).strip().lower().replace('_', ' ').replace('-', ' ').split())
    
    def get_value_tolerant(contenu: dict, exact_candidates=None, tokens=None):
        """Retourne la valeur pour une clé en acceptant des variantes d'en-têtes.
        - exact_candidates: liste de libellés candidats (str) comparés après normalisation
        - tokens: liste de mots qui doivent tous être présents dans l'en-tête normalisé
        Gestionne notamment: espaces de fin/début, doubles espaces, underscores, casse.
        """
        if not contenu:
            return None
        
        # Construire un mapping normalisé -> (clé originale, valeur)
        normalized = {normalize_header(k): (k, v) for k, v in contenu.items() if k}
        
        # 1) Essais exacts (après normalisation)
        if exact_candidates:
            for cand in exact_candidates:
                nk = normalize_header(cand)
                if nk in normalized:
                    return normalized[nk][1]
        
        # 2) Recherche par tokens (tous présents dans la clé normalisée)
        if tokens:
            needed = [normalize_header(t) for t in tokens]
            for nk, (_ok, v) in normalized.items():
                if all(t in nk for t in needed):
                    return v
        return None
    
    def normalize_keys(data_list):
        """Normalise les clés de tous les dictionnaires pour assurer la cohérence"""
        if not data_list or not isinstance(data_list, list):
            return data_list
        
        # Créer un mapping des variations de clés vers la clé normalisée (première occurrence)
        key_mapping = {}
        canonical_keys = {}  # normalized -> canonical
        
        for item in data_list:
            for key in item.keys():
                normalized = normalize_header(key)
                if normalized not in canonical_keys:
                    # Première fois qu'on voit cette clé normalisée
                    canonical_keys[normalized] = key.strip()
                key_mapping[key] = canonical_keys[normalized]
        
        # Appliquer la normalisation à tous les items
        normalized_data = []
        for item in data_list:
            normalized_item = {}
            for key, value in item.items():
                normalized_key = key_mapping.get(key, key)
                normalized_item[normalized_key] = value
            normalized_data.append(normalized_item)
        
        return normalized_data
    
    # Normaliser les données
    if contenu_data and isinstance(contenu_data, list):
        contenu_data = normalize_keys(contenu_data)

    if contenu_data:
        # Utiliser les en-têtes stockés dans le fichier importé
        
        # Traitement des données structurées (liste de dictionnaires)
        if isinstance(contenu_data, list) and len(contenu_data) > 0 and isinstance(contenu_data[0], dict):
            # Récupérer tous les en-têtes uniques
            all_keys = set()
            for item in contenu_data:
                all_keys.update(item.keys())
            
            # Trier les en-têtes par ordre alphabétique
            headers = sorted(list(all_keys))
            
            # Debug: afficher les headers disponibles
            print(f"[DEBUG details_bon] Headers disponibles ({len(headers)}): {headers}")
            
            # Trouver la colonne qui contient le numéro de commande
            for cle in headers:
                if cle.upper() in ['ORDER', 'ORDRE', 'BON', 'BON_COMMANDE', 'COMMANDE', 'BC', 'NUM_BC', 'PO', 'PO_NUMBER']:
                    colonne_order = cle
                    break
            
            # Filtrer les données si un numéro de commande est sélectionné
            if selected_order_number and colonne_order:
                raw_data = [
                    item for item in contenu_data 
                    if colonne_order in item and str(item[colonne_order]) == str(selected_order_number)
                ]
            else:
                raw_data = contenu_data

            # Initialiser les champs Quantity Delivered et Quantity Not Delivered pour toutes les données
            for item in raw_data:
                if 'Ordered Quantity' in item:
                    try:
                        ordered_qty = float(item['Ordered Quantity']) if item['Ordered Quantity'] is not None else 0
                        item['Quantity Delivered'] = item.get('Quantity Delivered', 0)
                        item['Quantity Not Delivered'] = max(0, ordered_qty - float(item['Quantity Delivered']))
                    except (ValueError, TypeError):
                        item['Quantity Delivered'] = 0
                        item['Quantity Not Delivered'] = 0
            
            # S'assurer que les en-têtes Quantity Delivered et Quantity Not Delivered sont présents
            if 'Quantity Delivered' not in headers:
                headers.append('Quantity Delivered')
            if 'Quantity Not Delivered' not in headers and 'Quantity Delivered' in headers:
                quantity_delivered_index = headers.index('Quantity Delivered')
                headers.insert(quantity_delivered_index + 1, 'Quantity Not Delivered')
        
        # Gestion des données brutes (texte)
        elif isinstance(contenu_data, dict) and ('raw_lines' in contenu_data or 'lines' in contenu_data):
            raw_lines = contenu_data.get('raw_lines') or contenu_data.get('lines') or []
            headers = ['Line', 'Content']
            raw_data = [{'Line': i+1, 'Content': line} for i, line in enumerate(raw_lines)]
            
            if raw_lines:
                first_line = raw_lines[0]
                if '\t' in first_line:
                    headers = first_line.split('\t')
                    raw_data = []
                    for i, line in enumerate(raw_lines[1:], 1):
                        if line.strip():
                            values = line.split('\t')
                            row_data = {'Line': i}
                            for j, header in enumerate(headers):
                                row_data[header] = values[j] if j < len(values) else ''
                            raw_data.append(row_data)
                elif ',' in first_line:
                    headers = first_line.split(',')
                    raw_data = []
                    for i, line in enumerate(raw_lines[1:], 1):
                        if line.strip():
                            values = line.split(',')
                            row_data = {'Line': i}
                            for j, header in enumerate(headers):
                                row_data[header] = values[j] if j < len(values) else ''
                            raw_data.append(row_data)
        
        # Cas par défaut pour les données non reconnues
        else:
            headers = ['File', 'Content']
            raw_data = [{'File': fichier.fichier.name, 'Content': 'Unstructured data'}]

    # Initialisation des variables pour les métadonnées
    devise = None
    status_value = None
    
    # Détection automatique des colonnes importantes
    currency_key = None
    status_key = None
    quantity_delivered_key = 'Quantity Delivered'  
    ordered_quantity_key = 'Ordered Quantity' if 'Ordered Quantity' in headers else None
    
    # Ajouter les données de réception aux données brutes en utilisant l'ID de ligne
    if contenu_data and isinstance(contenu_data, list):
        for item in contenu_data:
            # Utiliser l'ID de la ligne pour la correspondance
            idx = item.get('_business_id')
            
            if idx is not None and str(idx) in receptions:
                # Si on a une réception pour cette ligne, utiliser ses valeurs
                rec = receptions[str(idx)]
                item['Quantity Delivered'] = rec['quantity_delivered']
                item['Ordered Quantity'] = rec['ordered_quantity']
                item['Quantity Not Delivered'] = rec['quantity_not_delivered']
                item['Amount Delivered'] = rec['amount_delivered']
                item['Amount Not Delivered'] = rec['amount_not_delivered']
                item['Quantity Payable'] = rec['quantity_payable']
                item['Amount Payable'] = rec['amount_payable']  # Use the desired header
            elif 'Ordered Quantity' in item:
                # Initialiser avec des valeurs par défaut si pas de réception existante
                try:
                    ordered_qty = float(item['Ordered Quantity']) if item['Ordered Quantity'] is not None else 0
                    item['Quantity Delivered'] = 0
                    item['Quantity Not Delivered'] = ordered_qty
                    item['Amount Delivered'] = 0
                    item['Amount Not Delivered'] = 0
                    item['Quantity Payable'] = 0
                    item['Amount Payable'] = 0
                except (ValueError, TypeError):
                    item['Quantity Delivered'] = 0
                    item['Quantity Not Delivered'] = 0
                    item['Amount Delivered'] = 0
                    item['Amount Not Delivered'] = 0
                    item['Quantity Payable'] = 0
                    item['Amount Payable'] = 0

        currency_key = None
        status_key = None

        for key in headers:
            key_upper = key.upper()
            if not currency_key and ('CURRENCY' in key_upper or 'DEVISE' in key_upper or 'MONNAIE' in key_upper):
                currency_key = key
            if not status_key and ('STATUS' in key_upper or 'STATUT' in key_upper or 'ETAT' in key_upper):
                status_key = key

    # Récupération des valeurs de devise et de statut depuis les données
    if raw_data:
        first_item = raw_data[0]
        
        # Récupération de la devise
        if currency_key and currency_key in first_item:
            devise = first_item[currency_key]
        
        # Récupération du statut
        if status_key and status_key in first_item:
            status_value = first_item[status_key]

    # Ajouter les nouvelles colonnes aux en-têtes si elles n'existent pas
    # Insérer Amount Delivered et Amount Not Delivered ensemble
    if 'Amount Delivered' not in headers:
        headers.append('Amount Delivered')
    
    # Insérer Amount Not Delivered juste après Amount Delivered
    if 'Amount Not Delivered' not in headers:
        try:
            amount_delivered_index = headers.index('Amount Delivered')
            headers.insert(amount_delivered_index + 1, 'Amount Not Delivered')
        except ValueError:
            headers.append('Amount Not Delivered')
    
    if 'Quantity Payable' not in headers:
        headers.append('Quantity Payable')
    if 'Amount Payable' not in headers:
        headers.append('Amount Payable')    
    
    # Récupérer les évaluations du fournisseur pour ce bon de commande
    vendor_evaluations = []
    if selected_order_number and bon_commande:
        from .models import VendorEvaluation
        vendor_evaluations = VendorEvaluation.objects.filter(
            bon_commande=bon_commande,
            supplier=supplier
        ).order_by('-date_evaluation')

    # Vérifier si le bon contient "Migration IFS" dans Line Description
    is_migration_ifs = False
    if raw_data:
        for item in raw_data:
            line_desc = str(item.get('Line Description', '')).strip().upper()
            if 'MIGRATION IFS' in line_desc:
                is_migration_ifs = True
                break
    
    # Extraire Order Description, Project Coordinator, Project Name et PIP END DATE (si présents)
    order_description = None
    project_coordinator = None
    project_name = None
    pip_end_date = None
    order_status_extracted = None
    actual_end_date = None
    if raw_data:
        first_item = raw_data[0] if isinstance(raw_data, list) else {}
        try:
            order_description = get_value_tolerant(
                first_item,
                exact_candidates=['Order Description',],
                tokens=['order', 'description']
            )
        except Exception:
            order_description = None
        try:
            project_coordinator = get_value_tolerant(
                first_item,
                exact_candidates=['Project Coordinator'],
                tokens=['project', 'coordinator']
            )
        except Exception:
            project_coordinator = None
        try:
            project_name = get_value_tolerant(
                first_item,
                exact_candidates=['Project Name'],
                tokens=['project', 'name']
            )
        except Exception:
            project_name = None
        try:
            pip_end_date = get_value_tolerant(
                first_item,
                exact_candidates=['PIP END DATE', 'PIP END'],
                tokens=['pip', 'end']
            )
        except Exception:
            pip_end_date = None
        try:
            order_status_extracted = get_value_tolerant(
                first_item,
                exact_candidates=['Order Status'],
                tokens=['status']
            )
        except Exception:
            order_status_extracted = None
        try:
            actual_end_date = get_value_tolerant(
                first_item,
                exact_candidates=['ACTUAL END DATE', 'ACTUAL END'],
                tokens=['actual', 'end']
            )
        except Exception:
            actual_end_date = None        

        # Extraire la date de création du PO à partir du contenu du fichier s'il existe
        po_creation_date = None
        try:
            po_creation_date_raw = get_value_tolerant(
                first_item,
                exact_candidates=['Creation Date', 'Order Creation Date', 'PO Creation Date'],
                tokens=['creation', 'date']
            )
            if po_creation_date_raw:
                # Essayer de parser différents formats courants
                date_str = str(po_creation_date_raw).strip()
                date_formats = [
                    '%Y-%m-%d %H:%M:%S',
                    '%Y-%m-%d',
                    '%d/%m/%Y',
                    '%d/%m/%Y %H:%M:%S',
                    '%m/%d/%Y',
                    '%m/%d/%Y %H:%M:%S',
                ]
                parsed = None
                for fmt in date_formats:
                    try:
                        parsed = datetime.strptime(date_str, fmt)
                        break
                    except ValueError:
                        continue
                # Si échec du parsing, conserver la chaîne telle quelle (le template affichera la valeur brute)
                po_creation_date = parsed if parsed else po_creation_date_raw
        except Exception:
            po_creation_date = None

    # Déterminer le libellé de l'utilisateur ayant importé le fichier
    if getattr(fichier, 'utilisateur', None):
        imported_by = (
            fichier.utilisateur.get_full_name()
            or fichier.utilisateur.email
            or 'System'
        )
    else:
        imported_by = 'System'

    context = {
        'fichier': fichier,
        'bon': fichier,  
        'bon_id': fichier.id,  
        'bon_number': bon_number,
        'file_exists': file_exists,
        'file_size': file_size,
        'selected_order_number': selected_order_number,
        'raw_data': raw_data,
        'headers': headers,
        'colonne_order': colonne_order,
        'ordered_quantity_key': 'Ordered Quantity',
        'quantity_delivered_key': 'Quantity Delivered',
        'quantity_not_delivered_key': 'Quantity Not Delivered',
        'taux_avancement': taux_avancement,
        'montant_total': montant_total,
        'montant_total_recu': montant_total_recu,
        'devise': devise,
        'nb_lignes': len(raw_data) if selected_order_number and colonne_order else (fichier.nombre_lignes if hasattr(fichier, 'nombre_lignes') else len(raw_data)),
        # Date de création provenant uniquement du contenu du fichier (pas de fallback)
        'date_creation': (po_creation_date if 'po_creation_date' in locals() and po_creation_date else None),
        'status_value': status_value,
        'order_status': order_status_extracted if order_status_extracted not in (None, '') else status_value,
        'receptions': receptions,
        'supplier': supplier,
        'currency': currency,
        'bon_commande_id': bon_commande.id if selected_order_number and hasattr(bon_commande, 'id') else None,
        'retention_rate': bon_commande.retention_rate if selected_order_number and hasattr(bon_commande, 'retention_rate') else Decimal('0'),
        'retention_cause': bon_commande.retention_cause if selected_order_number and hasattr(bon_commande, 'retention_cause') else '',
        'vendor_evaluations': vendor_evaluations,
        'is_migration_ifs': is_migration_ifs,  # Flag pour désactiver les actions
        'order_description': order_description,
        'project_coordinator': project_coordinator,
        'project_name': project_name,
        'pip_end_date': pip_end_date,
        'actual_end_date': actual_end_date,
        'imported_by': imported_by,
    }
    
    return render(request, 'orders/detail_bon.html', context)


def telecharger_fichier(request, fichier_id, format_export='xlsx'):
    """
    But:
    - Exporter les données d’un fichier dans un format téléchargeable (ex: Excel).

    Étapes:
    1) Retrouver le fichier et ses lignes.
    2) Préparer les données au bon format.
    3) Renvoyer le fichier au navigateur.

    Entrées:
    - request (HttpRequest)
    - fichier_id (int)
    - format_export (str) par défaut 'xlsx'

    Sorties:
    - HttpResponse de fichier téléchargeable (ex: .xlsx).
    """
    fichier = get_object_or_404(FichierImporte, id=fichier_id)
    
    # Récupérer les lignes du fichier depuis le modèle LigneFichier
    lignes_fichier = fichier.lignes.all().order_by('numero_ligne')
    contenu_data = [ligne.contenu for ligne in lignes_fichier]
    
    # Préparer les données pour l'export
    if contenu_data:
        # Données tabulaires (liste de dictionnaires)
        if isinstance(contenu_data[0], dict):
            df = pd.DataFrame(contenu_data)
        # Données brutes (lignes de texte)
        else:
            df = pd.DataFrame({'Ligne': contenu_data})
    else:
        # Aucune donnée trouvée
        df = pd.DataFrame({'Message': ['Aucune donnée disponible pour ce fichier.']})
    
    # Nom du fichier à télécharger
    nom_fichier = f'fichier_importe_{fichier.id}'
    
    # Export selon le format demandé
    if format_export == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename={nom_fichier}.csv'
        df.to_csv(response, index=False)
    elif format_export == 'json':
        response = HttpResponse(content_type='application/json')
        response['Content-Disposition'] = f'attachment; filename={nom_fichier}.json'
        response.write(df.to_json(orient='records'))
    else:  # xlsx par défaut
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename={nom_fichier}.xlsx'
        df.to_excel(response, index=False)
    
    return response


def search_bon(request):
    """
    But:
    - Rechercher un bon de commande (PO) par numéro et rediriger vers ses détails.

    Étapes:
    1) Lire le numéro saisi (GET: order_number).
    2) Si trouvé → rediriger vers la page détails correspondante.
    3) Sinon → message d'erreur et retour à l'accueil.

    Entrées:
    - request (HttpRequest) GET: order_number (str)

    Sorties:
    - Redirection vers `orders:details_bon` ou vers `orders:accueil` avec message.
    """
    from .models import NumeroBonCommande
    
    # Autocomplete suggestions: /orders/search-bon?q=...&limit=20
    if request.method == 'GET' and 'q' in request.GET:
        from django.http import JsonResponse
        q = (request.GET.get('q') or '').strip()
        try:
            limit = int(request.GET.get('limit', '20'))
        except (TypeError, ValueError):
            limit = 20
        limit = max(1, min(limit, 50))

        qs = NumeroBonCommande.objects.all().prefetch_related('fichiers__lignes')
        if q:
            qs = qs.filter(numero__icontains=q)
        
        # Filtrer par service de l'utilisateur
        qs = filter_bons_by_user_service(qs, request.user)

        # For each bon, also provide most recent associated fichier id if exists (for direct redirect)
        bons = []
        for bon in qs.order_by('numero')[:limit]:
            fichier_id = None
            try:
                latest_file = bon.fichiers.order_by('-date_importation').first()
                if latest_file:
                    fichier_id = latest_file.id
            except Exception:
                fichier_id = None
            # Supplier: rapide, sans parcourir toutes les lignes
            try:
                from .models import VendorEvaluation
                ve = VendorEvaluation.objects.filter(bon_commande=bon).values('supplier').first()
                supplier = ve['supplier'] if ve and ve.get('supplier') else None
            except Exception:
                supplier = None
            # Essai via business_id pour récupérer Supplier de manière ciblée
            if supplier is None:
                try:
                    from .models import Reception, LigneFichier
                    rec = Reception.objects.filter(bon_commande=bon).values('business_id', 'fichier_id').first()
                    if rec and rec.get('business_id') and rec.get('fichier_id'):
                        lf = LigneFichier.objects.filter(
                            fichier_id=rec['fichier_id'],
                            business_id=rec['business_id']
                        ).values('contenu').first()
                        contenu = lf['contenu'] if lf and lf.get('contenu') else {}
                        def norm(s: str):
                            return ' '.join(str(s).strip().lower().replace('_', ' ').replace('-', ' ').split())
                        for k, v in (contenu.items() if isinstance(contenu, dict) else []):
                            if not k:
                                continue
                            nk = norm(k)
                            if v and ('supplier' in nk or 'vendor' in nk or 'fournisseur' in nk or 'vendeur' in nk):
                                supplier = str(v)
                                break
                except Exception:
                    supplier = None
            if supplier is None and latest_file:
                try:
                    # Première ligne du dernier fichier importé
                    first_line = latest_file.lignes.order_by('numero_ligne').first()
                    contenu = getattr(first_line, 'contenu', {}) or {}
                    # Recherche tolérante des clés Supplier/Vendor/Fournisseur
                    def norm(s: str):
                        return ' '.join(str(s).strip().lower().replace('_', ' ').replace('-', ' ').split())
                    for k, v in contenu.items():
                        if not k:
                            continue
                        nk = norm(k)
                        if v and ('supplier' in nk or 'vendor' in nk or 'fournisseur' in nk or 'vendeur' in nk):
                            supplier = str(v)
                            break
                except Exception:
                    supplier = None
            bons.append({
                'numero': bon.numero,
                'fichier_id': fichier_id,
                'cpu': bon.cpu,
                'supplier': supplier,
            })

        return JsonResponse({'status': 'success', 'data': bons})

    if request.method == 'GET' and 'order_number' in request.GET:
        order_number = request.GET.get('order_number')
        
        # Search for the purchase order by number
        try:
            bon_commande = NumeroBonCommande.objects.get(numero=order_number)
            # Get the most recent associated file
            if bon_commande.fichiers.exists():
                fichier = bon_commande.fichiers.order_by('-date_importation').first()
                # Redirect to the details page of the file with the selected order number as a GET parameter
                return redirect(f'/orders/bons/{fichier.id}/?selected_order_number={order_number}')
            else:
                messages.warning(request, f'Purchase order {order_number} exists but is not associated with any file.')
                return redirect('orders:accueil')
        except NumeroBonCommande.DoesNotExist:
            messages.error(request, f"Aucun bon de commande trouvé avec le numéro '{order_number}'")
            return redirect('orders:accueil')


@login_required
def po_progress_monitoring(request):
    """
    But:
    - Afficher la page de suivi de progression des bons (vue globale).

    Étapes:
    1) Préparer le contexte minimal.
    2) Rendre le template associé (graphes/tables côté front).

    Entrées:
    - request (HttpRequest)

    Sorties:
    - Template HTML de monitoring (progression des bons).
    """
    return render(request, 'orders/po_progress_monitoring.html')



@login_required
def vendor_evaluation(request, bon_commande_id):
    """
    But:
    - Créer ou modifier l’évaluation d’un fournisseur pour un PO donné.

    Étapes:
    1) Vérifier l'accès (service/CPU de l’utilisateur).
    2) Afficher le formulaire (GET) ou sauvegarder (POST).
    3) Rediriger vers la page de détails ou lister les évaluations.

    Entrées:
    - request (HttpRequest)
    - bon_commande_id (int)

    Sorties:
    - Template HTML du formulaire ou redirection après sauvegarde.
    """
    from .models import VendorEvaluation
    
    # Récupérer le bon de commande
    bon_commande = get_object_or_404(NumeroBonCommande, id=bon_commande_id)
    
    # 🔒 SÉCURITÉ : Vérifier que l'utilisateur a accès à ce bon
    if not request.user.is_superuser:
        cpu = bon_commande.get_cpu()
        services_list = request.user.get_services_list() if hasattr(request.user, 'get_services_list') else []
        
        # Vérifier si le CPU du bon est dans la liste des services autorisés
        if not services_list or cpu.strip().upper() not in services_list:
            messages.error(request, f"❌ Vous n'avez pas accès au bon de commande {bon_commande.numero}.")
            return redirect('orders:accueil')
    
    supplier = bon_commande.get_supplier()
    
    # Récupérer le fichier_id depuis la requête (d'où vient l'utilisateur)
    fichier_id = request.GET.get('fichier_id')
    if not fichier_id:
        # Si pas de fichier_id, prendre le plus récent
        fichier = bon_commande.fichiers.order_by('-date_importation').first()
        fichier_id = fichier.id if fichier else None
    
    # Vérifier si une évaluation existe déjà POUR CET UTILISATEUR
    evaluation = None
    try:
        evaluation = VendorEvaluation.objects.get(
            bon_commande=bon_commande,
            supplier=supplier,
            evaluator=request.user  # Chaque utilisateur a sa propre évaluation
        )
    except VendorEvaluation.DoesNotExist:
        pass
    
    # Vérifier s'il existe une évaluation d'un autre utilisateur (pour affichage)
    other_evaluation = None
    if not evaluation:
        try:
            other_evaluation = VendorEvaluation.objects.filter(
                bon_commande=bon_commande,
                supplier=supplier
            ).exclude(evaluator=request.user).first()
        except VendorEvaluation.DoesNotExist:
            pass
    
    if request.method == 'POST':
        try:
            # Récupérer les données du formulaire
            delivery_compliance = int(request.POST.get('delivery_compliance'))
            delivery_timeline = int(request.POST.get('delivery_timeline'))
            advising_capability = int(request.POST.get('advising_capability'))
            after_sales_qos = int(request.POST.get('after_sales_qos'))
            vendor_relationship = int(request.POST.get('vendor_relationship'))
            
            # Créer ou mettre à jour l'évaluation
            if evaluation:
                # Mise à jour de SA PROPRE évaluation
                evaluation.delivery_compliance = delivery_compliance
                evaluation.delivery_timeline = delivery_timeline
                evaluation.advising_capability = advising_capability
                evaluation.after_sales_qos = after_sales_qos
                evaluation.vendor_relationship = vendor_relationship
                # Ne pas changer l'évaluateur !
                evaluation.save()
                
                messages.success(request, f'Votre évaluation du fournisseur "{supplier}" a été mise à jour avec succès.')
            else:
                # Création
                evaluation = VendorEvaluation.objects.create(
                    bon_commande=bon_commande,
                    supplier=supplier,
                    delivery_compliance=delivery_compliance,
                    delivery_timeline=delivery_timeline,
                    advising_capability=advising_capability,
                    after_sales_qos=after_sales_qos,
                    vendor_relationship=vendor_relationship,
                    evaluator=request.user
                )
                
                messages.success(request, f'Évaluation du fournisseur "{supplier}" créée avec succès.')
            
            # Rediriger vers la page de détail du bon de commande avec le bon fichier_id
            if fichier_id:
                return redirect(f'/orders/bons/{fichier_id}/?selected_order_number={bon_commande.numero}')
            else:
                return redirect('orders:accueil')
            
        except (ValueError, TypeError) as e:
            messages.error(request, 'Erreur dans les données saisies. Veuillez vérifier vos notes.')
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde de l'évaluation: {str(e)}")
            messages.error(request, 'Une erreur s\'est produite lors de la sauvegarde.')
    
    context = {
        'bon_commande': bon_commande,
        'supplier': supplier,
        'evaluation': evaluation,  # L'évaluation de l'utilisateur actuel
        'other_evaluation': other_evaluation,  # L'évaluation d'un collègue (si existe)
        'fichier_id': fichier_id,
    }
    
    return render(request, 'orders/notation.html', context)


@login_required
def vendor_evaluation_list(request):
    """
    But:
    - Lister les évaluations de fournisseurs avec filtres simples.

    Étapes:
    1) Restreindre aux POs autorisés (service/CPU de l’utilisateur).
    2) Appliquer les filtres (si présents) et trier.
    3) Rendre la page de liste.

    Entrées:
    - request (HttpRequest)

    Sorties:
    - Template HTML listant les évaluations visibles.
    """
    from .models import VendorEvaluation
    from django.core.paginator import Paginator
    from datetime import datetime
    
    # Récupérer toutes les évaluations
    evaluations = VendorEvaluation.objects.select_related(
        'bon_commande', 'evaluator'
    ).order_by('-date_evaluation')
    
    # Filtrage par service (CPU) : ne garder que les évaluations des bons accessibles
    if not request.user.is_superuser:
        # Récupérer les IDs des bons accessibles par l'utilisateur
        bons_accessibles = filter_bons_by_user_service(
            NumeroBonCommande.objects.all(), 
            request.user
        )
        bon_ids = list(bons_accessibles.values_list('id', flat=True))
        evaluations = evaluations.filter(bon_commande_id__in=bon_ids)
    
    # Filtrage par fournisseur
    supplier_filter = request.GET.get('supplier', '').strip()
    if supplier_filter:
        evaluations = evaluations.filter(supplier__icontains=supplier_filter)
    
    # Filtrage par score minimum
    min_score = request.GET.get('min_score', '').strip()
    if min_score:
        try:
            min_score = int(min_score)
            # Filtrer par score total minimum
            filtered_ids = []
            for eval in evaluations:
                if eval.get_total_score() >= min_score:
                    filtered_ids.append(eval.id)
            evaluations = evaluations.filter(id__in=filtered_ids)
        except ValueError:
            pass
    
    # Filtrage par date de début
    date_from = request.GET.get('date_from', '').strip()
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            evaluations = evaluations.filter(date_evaluation__date__gte=date_from_obj)
        except ValueError:
            date_from = ''
    
    # Filtrage par date de fin
    date_to = request.GET.get('date_to', '').strip()
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
            evaluations = evaluations.filter(date_evaluation__date__lte=date_to_obj)
        except ValueError:
            date_to = ''
    
    # Pagination
    paginator = Paginator(evaluations, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Statistiques
    total_evaluations = evaluations.count()
    suppliers = evaluations.values_list('supplier', flat=True).distinct()
    
    context = {
        'page_obj': page_obj,
        'supplier_filter': supplier_filter,
        'min_score': min_score,
        'date_from': date_from,
        'date_to': date_to,
        'total_evaluations': total_evaluations,
        'suppliers': suppliers,
    }
    
    return render(request, 'orders/vendor_evaluation_list.html', context)


@login_required
def vendor_evaluation_detail(request, evaluation_id):
    """
    But:
    - Afficher les détails d’une évaluation fournisseur précise.

    Étapes:
    1) Vérifier l'accès (service/CPU).
    2) Charger l’évaluation et ses infos liées.
    3) Rendre la page de détails.

    Entrées:
    - request (HttpRequest)
    - evaluation_id (int)

    Sorties:
    - Template HTML de détail d’évaluation.
    """
    from .models import VendorEvaluation
    
    evaluation = get_object_or_404(VendorEvaluation, id=evaluation_id)
    
    # Vérifier que l'utilisateur a accès à ce bon de commande (filtrage par CPU)
    if not request.user.is_superuser:
        bons_accessibles = filter_bons_by_user_service(
            NumeroBonCommande.objects.filter(id=evaluation.bon_commande.id),
            request.user
        )
        if not bons_accessibles.exists():
            messages.error(request, "You do not have access to this evaluation.")
            return redirect('orders:vendor_evaluation_list')
    
    # Calculer les statistiques
    total_score = evaluation.get_total_score()
    
    # Récupérer les descriptions des critères
    criteria_details = []
    criteria_fields = [
        ('delivery_compliance', 'Delivery Compliance to Order (Quantity & Quality)'),
        ('delivery_timeline', 'Delivery Execution Timeline'),
        ('advising_capability', 'Vendor Advising Capability'),
        ('after_sales_qos', 'After Sales Services QOS'),
        ('vendor_relationship', 'Vendor Relationship'),
    ]
    
    for field_name, field_label in criteria_fields:
        score = getattr(evaluation, field_name)
        description = evaluation.get_criteria_description(field_name, score)
        criteria_details.append({
            'label': field_label,
            'score': score,
            'description': description
        })
    
    context = {
        'evaluation': evaluation,
        'total_score': total_score,
        'criteria_details': criteria_details,
    }
    
    return render(request, 'orders/vendor_evaluation_detail.html', context)


@login_required
def timeline_delays(request, bon_commande_id):
    """
    But:
    - Gérer les retards d’un bon de commande (timeline des étapes).

    Étapes:
    1) Vérifier l’accès (service/CPU).
    2) Charger les étapes/retards existants.
    3) Rendre la page pour visualiser/éditer.

    Entrées:
    - request (HttpRequest)
    - bon_commande_id (int)

    Sorties:
    - Template HTML de gestion des retards.
    """
    from .models import TimelineDelay, LigneFichier, NumeroBonCommande
    from datetime import datetime
    
    bon = get_object_or_404(NumeroBonCommande, id=bon_commande_id)
    
    # Vérifier que l'utilisateur a accès à ce bon de commande (filtrage par CPU)
    if not request.user.is_superuser:
        bons_accessibles = filter_bons_by_user_service(
            NumeroBonCommande.objects.filter(id=bon.id),
            request.user
        )
        if not bons_accessibles.exists():
            messages.error(request, f"You do not have access to purchase order {bon.numero}.")
            return redirect('orders:accueil')
    
    # Récupérer le fichier_id depuis la requête (d'où vient l'utilisateur)
    fichier_id = request.GET.get('fichier_id')
    if not fichier_id:
        # Si pas de fichier_id, prendre le plus récent
        fichier = bon.fichiers.order_by('-date_importation').first()
        fichier_id = fichier.id if fichier else None
    
    def get_total_days_late(bon_commande):
        """Calcule total_days_late à partir des dates PIP END DATE et ACTUAL END DATE"""
        # Chercher la ligne qui correspond exactement au numéro de bon de commande
        order_number = bon_commande.numero
        
        # Récupérer les fichiers associés au bon de commande
        fichiers = bon_commande.fichiers.all().order_by('date_importation')
        
        contenu = None
        for fichier in fichiers:
            lignes = LigneFichier.objects.filter(fichier=fichier).order_by('numero_ligne')
            for ligne in lignes:
                if not ligne.contenu:
                    continue
                
                # Chercher la clé Order dans le contenu
                order_val = None
                if 'Order' in ligne.contenu:
                    order_val = str(ligne.contenu['Order']).strip()
                elif 'ORDER' in ligne.contenu:
                    order_val = str(ligne.contenu['ORDER']).strip()
                elif 'order' in ligne.contenu:
                    order_val = str(ligne.contenu['order']).strip()
                
                # Si on trouve la ligne correspondant au bon de commande
                if order_val == order_number:
                    contenu = ligne.contenu
                    break
            
            if contenu:
                break
        
        if not contenu:
            return 0
        
        pip_end = contenu.get('PIP END DATE', '')
        actual_end = contenu.get('ACTUAL END DATE', '')
        
        if pip_end and actual_end:
            try:
                # Convertir en string et nettoyer
                pip_end_str = str(pip_end).strip()
                actual_end_str = str(actual_end).strip()
                
                # Liste des formats supportés
                date_formats = [
                    '%Y-%m-%d %H:%M:%S',  # 2025-07-30 00:00:00
                    '%Y-%m-%d',           # 2025-07-30
                    '%d/%m/%Y',           # 30/07/2025
                    '%d/%m/%Y %H:%M:%S'   # 30/07/2025 00:00:00
                ]
                
                pip = None
                actual = None
                
                # Essayer chaque format pour PIP END DATE
                for fmt in date_formats:
                    try:
                        pip = datetime.strptime(pip_end_str, fmt)
                        break
                    except ValueError:
                        continue
                
                # Essayer chaque format pour ACTUAL END DATE
                for fmt in date_formats:
                    try:
                        actual = datetime.strptime(actual_end_str, fmt)
                        break
                    except ValueError:
                        continue
                
                if pip and actual:
                    return max(0, (actual - pip).days)
                else:
                    return 0
            except:
                return 0
        return 0
    
    # Créer ou récupérer le TimelineDelay
    timeline, created = TimelineDelay.objects.get_or_create(bon_commande=bon)
    
    # Récupérer le PO Amount directement depuis le bon de commande
    po_amount = bon.montant_total()
    
    # Récupérer le supplier directement depuis le bon de commande
    supplier = bon.get_supplier()

    total_days_late = get_total_days_late(bon)
    vendor_days = timeline.delay_part_vendor
    if vendor_days is None:
        vendor_days = max(0, total_days_late - timeline.delay_part_mtn - timeline.delay_part_force_majeure)

    quotite_realisee = timeline.quotite_realisee if timeline.quotite_realisee is not None else Decimal('100.00')
    quotite_non_realisee = Decimal('100.00') - quotite_realisee
    if quotite_non_realisee < Decimal('0'):
        quotite_non_realisee = Decimal('0.00')

    data = {
        'id': timeline.id,
        'po_number': bon.numero,
        'supplier': supplier,
        'total_days_late': total_days_late,
        'delay_part_mtn': timeline.delay_part_mtn,
        'delay_part_force_majeure': timeline.delay_part_force_majeure,
        'delay_part_vendor': int(vendor_days),
        'po_amount': float(po_amount),
        'retention_amount_timeline': float(timeline.retention_amount_timeline),
        'retention_rate_timeline': float(timeline.retention_rate_timeline),
        'comment_mtn': timeline.comment_mtn or '',
        'comment_force_majeure': timeline.comment_force_majeure or '',
        'comment_vendor': timeline.comment_vendor or '',
        'quotite_realisee': float(quotite_realisee),
        'quotite_non_realisee': float(quotite_non_realisee),
    }
    
    return render(request, 'orders/timeline_delays.html', {'data': data, 'bon': bon, 'fichier_id': fichier_id})


@login_required
def update_delays(request, timeline_id):
    """
    But:
    - API pour sauvegarder les parts/étapes de retard (mise à jour via POST JSON).

    Étapes:
    1) Recevoir les données (POST JSON).
    2) Valider et enregistrer les champs mis à jour.
    3) Retourner un JSON de succès/erreur.

    Entrées:
    - request (HttpRequest) POST
    - timeline_id (int)

    Sorties:
    - JsonResponse: { success: bool, ... }
    """
    if request.method == 'POST':
        import json
        from .models import TimelineDelay
        
        timeline = get_object_or_404(TimelineDelay, id=timeline_id)
        data = json.loads(request.body)
        
        # Récupérer et valider les commentaires
        comment_mtn = data.get('comment_mtn', '').strip()
        comment_force_majeure = data.get('comment_force_majeure', '').strip()
        comment_vendor = data.get('comment_vendor', '').strip()
        
        # Validation : les commentaires sont obligatoires
        errors = []
        if not comment_mtn:
            errors.append("Le commentaire Part MTN est obligatoire")
        if not comment_force_majeure:
            errors.append("Le commentaire Part Force Majeure est obligatoire")
        if not comment_vendor:
            errors.append("Le commentaire Part Fournisseur est obligatoire")
        
        if errors:
            return JsonResponse({
                'success': False,
                'errors': errors,
                'message': ' | '.join(errors)
            }, status=400)
        
        # Mettre à jour les valeurs
        timeline.delay_part_mtn = int(data.get('mtn', 0))
        timeline.delay_part_force_majeure = int(data.get('fm', 0))
        timeline.delay_part_vendor = int(data.get('vendor', 0))
        quotite_value = data.get('quotite', timeline.quotite_realisee)
        try:
            quotite_decimal = Decimal(str(quotite_value))
        except (ArithmeticError, ValueError):
            return JsonResponse({
                'success': False,
                'message': "La quotité réalisée est invalide.",
                'fields': ['quotite_realisee']
            }, status=400)

        if quotite_decimal < Decimal('0') or quotite_decimal > Decimal('100'):
            return JsonResponse({
                'success': False,
                'message': "La quotité réalisée doit être comprise entre 0 et 100%.",
                'fields': ['quotite_realisee']
            }, status=400)

        timeline.quotite_realisee = quotite_decimal
        timeline.comment_mtn = comment_mtn
        timeline.comment_force_majeure = comment_force_majeure
        timeline.comment_vendor = comment_vendor
        
        timeline.save()
        quotite_non_realisee = max(Decimal('0'), Decimal('100.00') - timeline.quotite_realisee)
        
        return JsonResponse({
            'success': True,
            'quotite_realisee': float(timeline.quotite_realisee),
            'quotite_non_realisee': float(quotite_non_realisee),
            'retention_amount_timeline': float(timeline.retention_amount_timeline),
            'retention_rate_timeline': float(timeline.retention_rate_timeline),
        })
    return JsonResponse({'success': False}, status=400)


@login_required
def vendor_ranking(request):
    """
    But:
    - Afficher un classement des fournisseurs (meilleurs/pire) avec stats par année.

    Étapes:
    1) Agréger les évaluations et calculer des scores.
    2) Construire top 10 best/worst et stats annuelles.
    3) Rendre la page de classement avec filtres.

    Entrées:
    - request (HttpRequest)

    Sorties:
    - Template HTML `orders/vendor_ranking.html` avec tableaux/graphes.
    """
    from .models import VendorEvaluation, LigneFichier, NumeroBonCommande
    from django.db.models import Avg, Count
    from decimal import Decimal
    
    # Déterminer les bons autorisés (Option A: par CPU du PO)
    allowed_ids = None
    allowed_numbers = None
    if not request.user.is_superuser:
        allowed_qs = filter_bons_by_user_service(NumeroBonCommande.objects.all(), request.user)
        allowed_ids = set(allowed_qs.values_list('id', flat=True))
        allowed_numbers = set(allowed_qs.values_list('numero', flat=True))

    # Récupérer les évaluations (filtrées si nécessaire)
    evaluations_qs = VendorEvaluation.objects.all()
    if allowed_ids is not None:
        evaluations_qs = evaluations_qs.filter(bon_commande_id__in=allowed_ids)
    
    # Grouper par supplier et calculer les statistiques
    suppliers_data = {}
    
    for eval in evaluations_qs:
        supplier = eval.supplier
        if supplier not in suppliers_data:
            suppliers_data[supplier] = {
                'name': supplier,
                'evaluations': [],
                'po_numbers': set(),
                'po_ids': set(),  # Ajouter les IDs des PO
            }
        
        suppliers_data[supplier]['evaluations'].append({
            'delivery_compliance': eval.delivery_compliance,
            'delivery_timeline': eval.delivery_timeline,
            'advising_capability': eval.advising_capability,
            'after_sales_qos': eval.after_sales_qos,
            'vendor_relationship': eval.vendor_relationship,
            'vendor_final_rating': float(eval.vendor_final_rating),
        })
        suppliers_data[supplier]['po_numbers'].add(eval.bon_commande.numero)
        suppliers_data[supplier]['po_ids'].add(eval.bon_commande.id)
    
    # Pré-calculer le mapping supplier -> nombre de PO (une seule fois pour tous les suppliers)
    # Utiliser LigneFichier directement pour plus de performance
    supplier_po_count = {}
    
    # Récupérer toutes les lignes avec leurs fichiers et bons de commande en une seule requête
    lignes = LigneFichier.objects.select_related('fichier').prefetch_related('fichier__bons_commande').all()
    
    # Créer un mapping: supplier -> set de numéros de PO
    supplier_po_numbers = {}
    
    for ligne in lignes:
        contenu = ligne.contenu or {}
        
        # Chercher la colonne Supplier/Vendor/Fournisseur
        supplier_value = None
        for key, value in contenu.items():
            if not key:
                continue
            key_lower = key.strip().lower()
            if ('supplier' in key_lower or 'vendor' in key_lower or 
                'fournisseur' in key_lower or 'vendeur' in key_lower) and value:
                supplier_value = str(value).strip()
                break
        
        if supplier_value and supplier_value != 'N/A':
            # Récupérer le numéro de PO de cette ligne
            order_number = None
            for key, value in contenu.items():
                if not key:
                    continue
                key_lower = key.strip().lower()
                if ('order' in key_lower or 'commande' in key_lower or 
                    'bon' in key_lower or 'bc' in key_lower) and value:
                    order_number = str(value).strip()
                    break
            
            if order_number:
                # Limiter aux POs autorisés si nécessaire
                if allowed_numbers is not None and order_number not in allowed_numbers:
                    continue
                if supplier_value not in supplier_po_numbers:
                    supplier_po_numbers[supplier_value] = set()
                supplier_po_numbers[supplier_value].add(order_number)
    
    # Convertir en comptage
    for supplier, po_set in supplier_po_numbers.items():
        supplier_po_count[supplier] = len(po_set)
    
    # Calculer les moyennes et statistiques pour chaque supplier
    suppliers_stats = []
    for supplier, data in suppliers_data.items():
        evals = data['evaluations']
        num_evals = len(evals)
        
        avg_delivery_compliance = sum(e['delivery_compliance'] for e in evals) / num_evals
        avg_delivery_timeline = sum(e['delivery_timeline'] for e in evals) / num_evals
        avg_advising_capability = sum(e['advising_capability'] for e in evals) / num_evals
        avg_after_sales_qos = sum(e['after_sales_qos'] for e in evals) / num_evals
        avg_vendor_relationship = sum(e['vendor_relationship'] for e in evals) / num_evals
        avg_final_rating = sum(e['vendor_final_rating'] for e in evals) / num_evals
        
        # Récupérer le nombre de PO depuis le cache pré-calculé
        po_count = supplier_po_count.get(supplier, 0)
        
        suppliers_stats.append({
            'name': supplier,
            'po_count': po_count,
            'num_evaluations': num_evals,
            'avg_delivery_compliance': round(avg_delivery_compliance, 2),
            'avg_delivery_timeline': round(avg_delivery_timeline, 2),
            'avg_advising_capability': round(avg_advising_capability, 2),
            'avg_after_sales_qos': round(avg_after_sales_qos, 2),
            'avg_vendor_relationship': round(avg_vendor_relationship, 2),
            'avg_final_rating': round(avg_final_rating, 2),
        })
    
    # Trier par moyenne finale décroissante et attribuer les rangs
    suppliers_stats.sort(key=lambda x: x['avg_final_rating'], reverse=True)
    for idx, supplier in enumerate(suppliers_stats, 1):
        supplier['rank'] = idx
    
    # Top 10 meilleurs (les 10 premiers)
    top_10_best = suppliers_stats[:10]
    
    # Top 10 pires (les 10 derniers, inversés avec nouveaux rangs)
    worst_suppliers = suppliers_stats[-10:]
    worst_suppliers.sort(key=lambda x: x['avg_final_rating'])  # Tri croissant (du pire au moins pire)
    top_10_worst = []
    for idx, supplier in enumerate(worst_suppliers, 1):
        worst_copy = supplier.copy()
        worst_copy['worst_rank'] = idx  # Nouveau rang pour l'affichage (1 = le pire)
        top_10_worst.append(worst_copy)
    
    # Supplier sélectionné (si fourni dans la requête)
    selected_supplier = request.GET.get('supplier', '')
    selected_supplier_data = None
    yearly_stats_list = []
    
    if selected_supplier:
        selected_supplier_data = next(
            (s for s in suppliers_stats if s['name'] == selected_supplier),
            None
        )
        
        # Récupérer les statistiques par année pour le fournisseur sélectionné
        if selected_supplier_data:
            # Récupérer toutes les évaluations de ce fournisseur avec optimisation
            supplier_evals = VendorEvaluation.objects.filter(
                supplier=selected_supplier
            ).select_related('bon_commande').prefetch_related('bon_commande__fichiers__lignes')
            
            # Grouper par année
            years_data = {}
            
            for eval in supplier_evals:
                # Récupérer l'année depuis la ligne du fichier Excel
                year = 'N/A'
                bon_numero = eval.bon_commande.numero
                
                # Vérifier si le bon de commande a des fichiers
                fichiers_count = eval.bon_commande.fichiers.count()
                if fichiers_count == 0:
                    year = 'N/A'
                    if year not in years_data:
                        years_data[year] = []
                    years_data[year].append({
                        'delivery_compliance': eval.delivery_compliance,
                        'delivery_timeline': eval.delivery_timeline,
                        'advising_capability': eval.advising_capability,
                        'after_sales_qos': eval.after_sales_qos,
                        'vendor_relationship': eval.vendor_relationship,
                        'vendor_final_rating': float(eval.vendor_final_rating),
                    })
                    continue
                
                # Parcourir tous les fichiers liés au bon de commande
                found = False
                for fichier in eval.bon_commande.fichiers.all():
                    if found:
                        break
                    # Utiliser filter pour limiter les lignes à parcourir
                    # Chercher seulement les lignes qui contiennent le PO dans le JSON
                    for ligne in fichier.lignes.all():
                        if not ligne.contenu:
                            continue
                            
                        ligne_po = ligne.contenu.get('Order')
                        
                        # Si le PO correspond exactement
                        if ligne_po == bon_numero:
                            ligne_supplier = ligne.contenu.get('Supplier')
                            ligne_year = ligne.contenu.get('Année')
                            
                            # Vérifier le supplier (flexible)
                            if ligne_supplier and selected_supplier:
                                if (ligne_supplier == selected_supplier or 
                                    selected_supplier in ligne_supplier or 
                                    ligne_supplier in selected_supplier):
                                    # Trouvé !
                                    if ligne_year:
                                        year = ligne_year
                                        found = True
                                        break
                
                # Ajouter l'évaluation dans l'année correspondante
                if year not in years_data:
                    years_data[year] = []
                
                years_data[year].append({
                    'delivery_compliance': eval.delivery_compliance,
                    'delivery_timeline': eval.delivery_timeline,
                    'advising_capability': eval.advising_capability,
                    'after_sales_qos': eval.after_sales_qos,
                    'vendor_relationship': eval.vendor_relationship,
                    'vendor_final_rating': float(eval.vendor_final_rating),
                })
            
            # Calculer les moyennes par année
            for year, evals in sorted(years_data.items()):
                num_evals = len(evals)
                yearly_stats_list.append({
                    'year': year,
                    'avg_delivery_compliance': round(sum(e['delivery_compliance'] for e in evals) / num_evals, 2),
                    'avg_delivery_timeline': round(sum(e['delivery_timeline'] for e in evals) / num_evals, 2),
                    'avg_advising_capability': round(sum(e['advising_capability'] for e in evals) / num_evals, 2),
                    'avg_after_sales_qos': round(sum(e['after_sales_qos'] for e in evals) / num_evals, 2),
                    'avg_vendor_relationship': round(sum(e['vendor_relationship'] for e in evals) / num_evals, 2),
                    'avg_final_rating': round(sum(e['vendor_final_rating'] for e in evals) / num_evals, 2),
                    'num_evaluations': num_evals,
                })
    
    import json
    yearly_stats_json = json.dumps(yearly_stats_list) if yearly_stats_list else '[]'
    
    context = {
        'suppliers_stats': suppliers_stats,
        'top_10_best': top_10_best,
        'top_10_worst': top_10_worst,
        'selected_supplier': selected_supplier,
        'selected_supplier_data': selected_supplier_data,
        'yearly_stats_list': yearly_stats_list,
        'yearly_stats_json': yearly_stats_json,
        'total_suppliers': len(suppliers_stats),
    }
    
    return render(request, 'orders/vendor_ranking.html', context)
