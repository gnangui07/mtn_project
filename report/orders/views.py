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




@login_required
def msrn_archive(request):
    """
    Page d'archive des rapports MSRN pour les utilisateurs (miroir de l'admin).
    Affiche: report_number, bon_commande, user, created_at, lien de téléchargement.
    Inclut une recherche simple et une pagination.
    """
    # Imports locaux pour éviter d'altérer les imports globaux existants
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    from django.db.models import Q
    from .models import MSRNReport

    base_qs = MSRNReport.objects.select_related('bon_commande').order_by('-created_at')
    qs = base_qs

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
    }
    return render(request, 'orders/msrn_archive.html', context)


@require_http_methods(["GET"])
@login_required
def download_msrn_report(request, report_id):
    """
    Télécharge un rapport MSRN existant depuis l'archive
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


def accueil(request):
    """
    Page d'accueil qui sert de point d'entrée principal pour l'application.
    Affiche les options pour importer un fichier ou consulter les fichiers existants.
    Inclut la liste des numéros de bons de commande pour le popup.
    """
    from .models import NumeroBonCommande
    
    # Récupérer tous les numéros de bons de commande pour le popup
    numeros_bons = NumeroBonCommande.objects.all().order_by('numero')
    
    return render(request, 'orders/reception.html', {
        'numeros_bons': numeros_bons,
    })


def import_fichier(request):
    """
    Vue pour importer un fichier de n'importe quel type (Excel, CSV, JSON, etc.)
    Le fichier est traité automatiquement lors de l'enregistrement (save method override)
    """
    if request.method == 'POST':
        form = UploadFichierForm(request.POST, request.FILES)
        if form.is_valid():
            # L'extraction des données se fait automatiquement dans le save() du modèle
            fichier = form.save()
            messages.success(request, f'Fichier importé avec succès. {fichier.nombre_lignes} lignes extraites.')
            return redirect('orders:details_bon', bon_id=fichier.id)
    else:
        form = UploadFichierForm()
    
    return render(request, 'orders/reception.html', {
        'form': form,
    })


def consultation(request):
    """
    Vue pour la page de consultation des bons de commande.
    Utilise le template consultation.html existant.
    """
    # Dans le futur, cette vue pourrait offrir des filtres et des fonctionnalités de recherche avancées
    # Pour l'instant, elle affiche simplement le template avec un message
    return render(request, 'orders/consultation.html')


def details_bon(request, bon_id):
    """
    Vue pour afficher les détails d'un fichier importé comme un bon de commande.
    Filtre les lignes pour n'afficher que celles correspondant au numéro de bon de commande sélectionné.
    Affiche les données brutes du fichier importé exactement comme elles apparaissent dans le fichier d'origine.
    """
    selected_order_number = None

    if request.method == 'GET' and 'selected_order_number' in request.GET:
        selected_order_number = request.GET.get('selected_order_number')

    if bon_id == 'search' and request.method == 'GET' and 'order_number' in request.GET:
        selected_order_number = request.GET.get('order_number')
        try:
            bon_commande = NumeroBonCommande.objects.get(numero=selected_order_number)
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
    if fichier.fichier and not os.path.exists(fichier.fichier.path):
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
        # Récupérer toutes les lignes du fichier avec leur ID
        lignes_fichier = fichier.lignes.all().order_by('numero_ligne')
        
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
        contenu_data = []
        for ligne in lignes_fichier:
            data = ligne.contenu.copy()
            data['_business_id'] = ligne.business_id  # Store business ID instead of row index
            data = extract_numeric_values(data)  # Extraire les valeurs numériques
            contenu_data.append(data)
        
        # Initialiser le dictionnaire des réceptions indexé par business_id
        receptions = {}
        
        # Si un numéro de bon de commande est sélectionné, charger les réceptions existantes
        if selected_order_number:
            try:
                # Récupérer le bon de commande
                bon_commande = NumeroBonCommande.objects.get(numero=selected_order_number)
                
                # Récupérer les réceptions pour ce bon de commande et ce fichier
                receptions_queryset = Reception.objects.filter(
                    bon_commande=bon_commande,
                    fichier=fichier
                ).select_related('fichier', 'bon_commande').order_by('business_id')
                
                # Convertir les réceptions en dictionnaire indexé par business_id
                for reception in receptions_queryset:
                    receptions[str(reception.business_id)] = {
                        'quantity_delivered': reception.quantity_delivered,
                        'ordered_quantity': reception.ordered_quantity,
                        'quantity_not_delivered': reception.quantity_not_delivered,
                        'amount_delivered': reception.amount_delivered,
                        'quantity_payable': reception.quantity_payable,
                        'unit_price': reception.unit_price,
                        'amount_payable': reception.amount_payable  # Use the desired header
                    }
                    
            except NumeroBonCommande.DoesNotExist:
                # Si le bon de commande n'existe pas encore, on continue avec un dictionnaire vide
                pass
                
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
                item['Quantity Payable'] = rec['quantity_payable']
                item['Amount Payable'] = rec['amount_payable']  # Use the desired header
            elif 'Ordered Quantity' in item:
                # Initialiser avec des valeurs par défaut si pas de réception existante
                try:
                    ordered_qty = float(item['Ordered Quantity']) if item['Ordered Quantity'] is not None else 0
                    item['Quantity Delivered'] = 0
                    item['Quantity Not Delivered'] = ordered_qty
                    item['Amount Delivered'] = 0
                    item['Quantity Payable'] = 0
                    item['Amount Payable'] = 0
                except (ValueError, TypeError):
                    item['Quantity Delivered'] = 0
                    item['Quantity Not Delivered'] = 0
                    item['Amount Delivered'] = 0
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
    if 'Amount Delivered' not in headers:
        headers.append('Amount Delivered')
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
    
    context = {
        'fichier': fichier,
        'bon': fichier,  
        'bon_id': fichier.id,  
        'bon_number': bon_number,
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
        'date_creation': fichier.date_importation if hasattr(fichier, 'date_importation') else None,
        'status_value': status_value,
        'receptions': receptions,
        'supplier': supplier,
        'currency': currency,
        'bon_commande_id': bon_commande.id if selected_order_number and hasattr(bon_commande, 'id') else None,
        'retention_rate': bon_commande.retention_rate if selected_order_number and hasattr(bon_commande, 'retention_rate') else Decimal('0'),
        'retention_cause': bon_commande.retention_cause if selected_order_number and hasattr(bon_commande, 'retention_cause') else '',
        'vendor_evaluations': vendor_evaluations,
        'is_migration_ifs': is_migration_ifs,  # Flag pour désactiver les actions

    }
    
    return render(request, 'orders/detail_bon.html', context)


def telecharger_fichier(request, fichier_id, format_export='xlsx'):
    """
    Permet de télécharger les données d'un fichier dans différents formats
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


def api_statistiques_commande(request, order):
    """API pour les statistiques des commandes (pour compatibilité)"""
    return JsonResponse({
        'success': True,
        'message': 'Fonction simplifiée',
        'data': {
            'nom_fichier': f'PO-{order}',
            'lignes': 0,
            'date': '2023-01-01',
        }
    })


def search_bon(request):
    """
    View for searching purchase orders by order number
    Redirects to the details page if found, otherwise redirects to the home page with error
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

        qs = NumeroBonCommande.objects.all()
        if q:
            qs = qs.filter(numero__icontains=q)

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
            bons.append({
                'numero': bon.numero,
                'fichier_id': fichier_id,
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
    Vue pour la page de monitoring de progression des bons de commande
    """
    return render(request, 'orders/po_progress_monitoring.html')



@login_required
def vendor_evaluation(request, bon_commande_id):
    """
    Vue pour créer ou modifier l'évaluation d'un fournisseur
    """
    from .models import VendorEvaluation
    
    # Récupérer le bon de commande
    bon_commande = get_object_or_404(NumeroBonCommande, id=bon_commande_id)
    supplier = bon_commande.get_supplier()
    
    # Récupérer le fichier_id depuis la requête (d'où vient l'utilisateur)
    fichier_id = request.GET.get('fichier_id')
    if not fichier_id:
        # Si pas de fichier_id, prendre le plus récent
        fichier = bon_commande.fichiers.order_by('-date_importation').first()
        fichier_id = fichier.id if fichier else None
    
    # Vérifier si une évaluation existe déjà
    evaluation = None
    try:
        evaluation = VendorEvaluation.objects.get(
            bon_commande=bon_commande,
            supplier=supplier
        )
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
                # Mise à jour
                evaluation.delivery_compliance = delivery_compliance
                evaluation.delivery_timeline = delivery_timeline
                evaluation.advising_capability = advising_capability
                evaluation.after_sales_qos = after_sales_qos
                evaluation.vendor_relationship = vendor_relationship
                evaluation.evaluator = request.user
                evaluation.save()
                
                messages.success(request, f'Évaluation du fournisseur "{supplier}" mise à jour avec succès.')
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
        'evaluation': evaluation,
        'fichier_id': fichier_id,
    }
    
    return render(request, 'orders/notation.html', context)


@login_required
def vendor_evaluation_list(request):
    """
    Vue pour lister toutes les évaluations de fournisseurs avec filtres
    """
    from .models import VendorEvaluation
    from django.core.paginator import Paginator
    from datetime import datetime
    
    # Récupérer toutes les évaluations
    evaluations = VendorEvaluation.objects.select_related(
        'bon_commande', 'evaluator'
    ).order_by('-date_evaluation')
    
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
    Vue pour afficher les détails d'une évaluation de fournisseur
    """
    from .models import VendorEvaluation
    
    evaluation = get_object_or_404(VendorEvaluation, id=evaluation_id)
    
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
    """Vue simple pour gérer les retards d'un bon de commande"""
    from .models import TimelineDelay, LigneFichier, NumeroBonCommande
    from datetime import datetime
    
    bon = get_object_or_404(NumeroBonCommande, id=bon_commande_id)
    
    # Récupérer le fichier_id depuis la requête (d'où vient l'utilisateur)
    fichier_id = request.GET.get('fichier_id')
    if not fichier_id:
        # Si pas de fichier_id, prendre le plus récent
        fichier = bon.fichiers.order_by('-date_importation').first()
        fichier_id = fichier.id if fichier else None
    
    def get_total_days_late(bon_commande):
        """Calcule total_days_late comme dans export_po_progress_monitoring"""
        lignes = LigneFichier.objects.filter(fichier__bons_commande=bon_commande).order_by('numero_ligne').first()
        if not lignes:
            return 0
        
        contenu = lignes.contenu or {}
        pip_end = contenu.get('PIP END DATE', '')
        actual_end = contenu.get('ACTUAL END DATE', '')
        
        if pip_end and actual_end:
            try:
                try:
                    pip = datetime.strptime(str(pip_end), '%d/%m/%Y')
                    actual = datetime.strptime(str(actual_end), '%d/%m/%Y')
                except ValueError:
                    pip = datetime.strptime(str(pip_end), '%Y-%m-%d')
                    actual = datetime.strptime(str(actual_end), '%Y-%m-%d')
                return max(0, (actual - pip).days)
            except:
                return 0
        return 0
    
    # Créer ou récupérer le TimelineDelay
    timeline, created = TimelineDelay.objects.get_or_create(bon_commande=bon)
    
    # Récupérer le PO Amount directement depuis le bon de commande
    po_amount = bon.montant_total()
    
    total_days_late = get_total_days_late(bon)
    supplier = bon.get_supplier()
    
    data = {
        'id': timeline.id,
        'po_number': bon.numero,
        'supplier': supplier,
        'total_days_late': total_days_late,
        'delay_part_mtn': timeline.delay_part_mtn,
        'delay_part_force_majeure': timeline.delay_part_force_majeure,
        'delay_part_vendor': max(0, total_days_late - timeline.delay_part_mtn - timeline.delay_part_force_majeure),
        'po_amount': float(po_amount),
        'retention_amount_timeline': float(timeline.retention_amount_timeline),
        'retention_rate_timeline': float(timeline.retention_rate_timeline),
    }
    
    return render(request, 'orders/timeline_delays.html', {'data': data, 'bon': bon, 'fichier_id': fichier_id})


@login_required
def update_delays(request, timeline_id):
    """API pour sauvegarder les parts"""
    if request.method == 'POST':
        import json
        from .models import TimelineDelay
        
        timeline = get_object_or_404(TimelineDelay, id=timeline_id)
        data = json.loads(request.body)
        
        timeline.delay_part_mtn = int(data.get('mtn', 0))
        timeline.delay_part_force_majeure = int(data.get('fm', 0))
        timeline.delay_part_vendor = int(data.get('vendor', 0))
        timeline.save()
        
        return JsonResponse({'success': True})
    return JsonResponse({'success': False}, status=400)


@login_required
def vendor_ranking(request):
    """
    Vue pour afficher le classement des fournisseurs avec statistiques consolidées
    """
    from .models import VendorEvaluation, LigneFichier
    from django.db.models import Avg, Count
    from decimal import Decimal
    
    # Récupérer toutes les évaluations
    evaluations = VendorEvaluation.objects.all()
    
    # Grouper par supplier et calculer les statistiques
    suppliers_data = {}
    
    for eval in evaluations:
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
    from .models import NumeroBonCommande
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


