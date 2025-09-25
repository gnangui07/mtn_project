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

    if contenu_data:
        # Utiliser les en-têtes stockés dans le fichier importé
        
        # Traitement des données structurées (liste de dictionnaires)
        if isinstance(contenu_data, list) and len(contenu_data) > 0 and isinstance(contenu_data[0], dict):
            # Récupérer tous les en-têtes uniques
            all_keys = set()
            for item in contenu_data:
                all_keys.update(item.keys())
            
            # Trier les en-têtes de manière cohérente
            headers = sorted(list(all_keys))
            
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

    }
    
    return render(request, 'orders/detail_bon.html', context)


def export_bon_excel(request, bon_id):
    """
    Exporte les données d'un bon de commande en Excel avec les données mises à jour des réceptions.
    Cette fonction réutilise la logique de fusion des données de details_bon.
    """
    selected_order_number = request.GET.get('selected_order_number')

    if bon_id == 'search' and 'order_number' in request.GET:
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
    
    # Récupérer les données depuis le modèle LigneFichier
    try:
        # Récupérer toutes les lignes du fichier avec leur ID
        lignes_fichier = fichier.lignes.all().order_by('numero_ligne')
        
        # Ajouter une fonction utilitaire pour extraire les valeurs numériques
        def extract_numeric_values(data):
            numeric_fields = ['Ordered Quantity','Quantity Delivered', 'Quantity Not Delivered', 'Price']
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
        
        # Variables pour les informations financières
        montant_total = 0
        montant_recu = 0
        taux_avancement = 0
        
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
                
                # Calculer les montants totaux pour l'onglet d'information
                montant_total = bon_commande.montant_total()
                montant_recu = bon_commande.montant_recu()
                if montant_total > 0:
                    taux_avancement = (montant_recu / montant_total) * 100
                else:
                    taux_avancement = 0
                    
            except NumeroBonCommande.DoesNotExist:
                # Si le bon de commande n'existe pas encore, on continue avec un dictionnaire vide
                pass
                
    except Exception as e:
        messages.error(request, f"Erreur lors de la récupération des données : {str(e)}")
        return redirect('orders:details_bon', bon_id=bon_id)
        
    raw_data = []
    headers = []
    colonne_order = None
    
    if contenu_data:
        # Utiliser les en-têtes stockés dans le fichier importé
        
        # Traitement des données structurées (liste de dictionnaires)
        if isinstance(contenu_data, list) and len(contenu_data) > 0 and isinstance(contenu_data[0], dict):
            # Récupérer tous les en-têtes uniques
            all_keys = set()
            for item in contenu_data:
                all_keys.update(item.keys())
            
            # Trier les en-têtes de manière cohérente
            headers = sorted(list(all_keys))
            
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
    
    # Ajouter les données de réception aux données brutes en utilisant l'ID de ligne
    if contenu_data and isinstance(contenu_data, list):
        for item in contenu_data:
            # Utiliser l'ID de la ligne pour la correspondance
            idx = item.get('_business_id')
            
            if idx is not None and str(idx) in receptions:
                # Si on a une réception pour cette ligne, utiliser ses valeurs
                rec = receptions[str(idx)]
                # Renommer Quantity Delivered en Receipt
                item['Quantity Delivered'] = rec['quantity_delivered']
                item['Ordered Quantity'] = rec['ordered_quantity']
                item['Quantity Not Delivered'] = rec['quantity_not_delivered']
                item['Amount Delivered'] = rec['amount_delivered']
                item['Quantity Payable'] = rec['quantity_payable']
                item['Amount Payable'] = rec['amount_payable']
                
                # Supprimer l'ancienne colonne Quantity Delivered si elle existe
                # if 'Quantity Delivered' in item:
                #     del item['Quantity Delivered']
            elif 'Ordered Quantity' in item:
                # Initialiser avec des valeurs par défaut si pas de réception existante
                try:
                    ordered_qty = float(item['Ordered Quantity']) if item['Ordered Quantity'] is not None else 0
                    # Utiliser Quantity Delivered au lieu de Quantity Delivered
                    item['Quantity Delivered'] = 0
                    item['Quantity Not Delivered'] = ordered_qty
                    item['Amount Delivered'] = 0
                    item['Quantity Payable'] = 0
                    item['Amount Payable'] = 0
                    
                    # Supprimer l'ancienne colonne Quantity Delivered si elle existe
                    # if 'Quantity Delivered' in item:
                    #     del item['Quantity Delivered']
                except (ValueError, TypeError):
                    item['Quantity Delivered'] = 0
                    item['Quantity Not Delivered'] = 0
                    item['Amount Delivered'] = 0
                    item['Quantity Payable'] = 0
                    item['Amount Payable'] = 0                    
                    # Supprimer l'ancienne colonne Quantity Delivered si elle existe
                    # if 'Quantity Delivered' in item:
                    #     del item['Quantity Delivered']
    
    # Nettoyer les données avant export: retirer lignes d'erreur et totalement vides
    filtered_raw = []
    for item in raw_data:
        if not isinstance(item, dict):
            continue
        # Exclure toute ligne d'erreur explicite
        if 'error' in item:
            continue
        # Considérer vides les lignes dont toutes les valeurs non techniques sont vides/None
        non_tech_keys = [k for k in item.keys() if not k.startswith('_')]
        has_value = any(
            (item.get(k) is not None and str(item.get(k)).strip() != '')
            for k in non_tech_keys
        )
        if not has_value:
            continue
        filtered_raw.append(item)
    raw_data = filtered_raw

    # Supprimer les clés techniques qui ne doivent pas apparaître dans l'export
    for item in raw_data:
        if '_business_id' in item:
            del item['_business_id']
    
    # Générer le fichier Excel
    import pandas as pd
    from django.http import HttpResponse
    from io import BytesIO
    
    # Créer un DataFrame pandas avec les données
    df = pd.DataFrame(raw_data)
    
    # Créer un buffer en mémoire pour stocker le fichier Excel
    output = BytesIO()
    
    # Déterminer le nom du fichier
    filename = f"PO_{selected_order_number}_updated.xlsx" if selected_order_number else f"Fichier_{fichier.id}_updated.xlsx"
    
    # Créer un writer Excel
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Premier onglet avec les données principales
        df.to_excel(writer, index=False, sheet_name='Données')
        
        # Deuxième onglet avec les informations financières
        if selected_order_number:
            # Créer un DataFrame pour les informations financières
            info_data = {
                'Information': ['Montant Total', 'Montant Total Reçu', 'Taux d\'Avancement'],
                'Valeur': [
                    f"{montant_total:,.2f} FCFA",
                    f"{montant_recu:,.2f} FCFA",
                    f"{taux_avancement:.2f}%"
                ]
            }
            info_df = pd.DataFrame(info_data)
            info_df.to_excel(writer, index=False, sheet_name='Informations')
    
    # Configurer la réponse HTTP
    output.seek(0)
    response = HttpResponse(
        output.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response



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
            return redirect('accueil')


def export_fichier_complet(request, fichier_id):
    """
    Exporte toutes les données d'un fichier importé en Excel avec les données mises à jour des réceptions.
    Cette fonction réutilise la logique de fusion des données de export_bon_excel mais sans filtrer par numéro de commande.
    """
    try:
        # Récupérer le fichier importé
        fichier = get_object_or_404(FichierImporte, id=fichier_id)
        
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
        
        # Récupérer toutes les réceptions pour ce fichier
        receptions_queryset = Reception.objects.filter(
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
                'amount_payable': reception.amount_payable  # Use the desired header
            }
        
        # Ajouter les données de réception aux données brutes en utilisant l'ID de ligne
        if contenu_data and isinstance(contenu_data, list):
            for item in contenu_data:
                # Utiliser l'ID de la ligne pour la correspondance
                idx = item.get('_business_id')
                
                if idx is not None and str(idx) in receptions:
                    # Si on a une réception pour cette ligne, utiliser ses valeurs
                    rec = receptions[str(idx)]
                    # Ajouter les données de réception
                    item['Quantity Delivered'] = rec['quantity_delivered']
                    item['Ordered Quantity'] = rec['ordered_quantity']
                    item['Quantity Not Delivered'] = rec['quantity_not_delivered']
                    item['Amount Delivered'] = rec['amount_delivered']
                    item['Quantity Payable'] = rec['quantity_payable']
                    item['Amount Payable'] = rec['amount_payable']
                elif 'Ordered Quantity' in item:
                    # Initialiser avec des valeurs par défaut si pas de réception existante
                    try:
                        ordered_qty = float(item['Ordered Quantity']) if item['Ordered Quantity'] is not None else 0
                        # Initialiser les valeurs par défaut
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
                        
                        # Conserver la colonne Quantity Delivered
        
        # Supprimer les clés techniques qui ne doivent pas apparaître dans l'export
        for item in contenu_data:
            if '_business_id' in item:
                del item['_business_id']
        
        # Générer le fichier Excel
        import pandas as pd
        from django.http import HttpResponse
        from io import BytesIO
        
        # Créer un DataFrame pandas avec les données
        df = pd.DataFrame(contenu_data)
        
        # Créer un buffer en mémoire pour stocker le fichier Excel
        output = BytesIO()
        
        # Déterminer le nom du fichier
        filename = f"Fichier_complet_{fichier.id}_updated.xlsx"
        
        # Créer un writer Excel
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Premier onglet avec les données principales
            df.to_excel(writer, index=False, sheet_name='Données')
            
            # Deuxième onglet avec les informations sur le fichier
            info_data = {
                'Information': ['Nom du fichier', 'Date d\'importation', 'Nombre de lignes'],
                'Valeur': [
                    os.path.basename(fichier.fichier.name),
                    fichier.date_importation.strftime('%Y-%m-%d %H:%M'),
                    fichier.nombre_lignes
                ]
            }
            info_df = pd.DataFrame(info_data)
            info_df.to_excel(writer, index=False, sheet_name='Informations')
        
        # Configurer la réponse HTTP
        output.seek(0)
        response = HttpResponse(
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
        
    except Exception as e:
        messages.error(request, f"Erreur lors de l'exportation du fichier : {str(e)}")
        return redirect('admin:orders_fichierimporte_changelist')


@login_required
def po_progress_monitoring(request):
    """
    Vue pour la page de monitoring de progression des bons de commande
    """
    return render(request, 'orders/po_progress_monitoring.html')

# orders/views.py
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.db.models import F, Value, DecimalField, ExpressionWrapper, Case, When, Sum, Subquery, OuterRef, FloatField
import pandas as pd
from io import BytesIO
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter
import logging


logger = logging.getLogger(__name__)

@login_required
def export_po_progress_monitoring(request):
    """
    Export Excel optimisé pour le suivi des bons de commande
    Une seule ligne par numéro de bon de commande avec toutes les colonnes demandées
    """
    try:
        from .models import NumeroBonCommande, InitialReceptionBusiness, LigneFichier

        # Récupération des données des fichiers liés aux bons de commande
        bons_commande = NumeroBonCommande.objects.prefetch_related(
            'fichiers__lignes'
        ).all()
        
        # Debug: Afficher les clés disponibles dans la première occurrence
        debug_first_occurrence = None
        
        # Étape 1: Créer un cache pour les premières occurrences de chaque bon de commande
        first_occurrence_cache = {}

        # Parcourir tous les bons de commande et leurs fichiers/lignes
        for bon in bons_commande:
            # Initialiser à None pour ce bon
            first_occurrence_cache[bon.numero] = None

            # Parcourir les fichiers et les lignes dans l'ordre d'importation (par date d'importation croissante)
            for fichier in bon.fichiers.order_by('date_importation'):
                for ligne in fichier.lignes.order_by('numero_ligne'):
                    contenu = ligne.contenu
                    # Vérifier si cette ligne correspond au bon de commande (en fonction de la colonne 'Order')
                    if contenu.get('Order') == bon.numero:
                        # Stocker la première occurrence et sortir des boucles pour ce bon
                        first_occurrence_cache[bon.numero] = contenu
                        break
                if first_occurrence_cache[bon.numero] is not None:
                    break

        # Étape 2: Préparation des données pour le DataFrame
        data = []
        for bon in bons_commande:
            # Récupérer la première occurrence de ce bon de commande
            premiere_occurrence = first_occurrence_cache.get(bon.numero)
            
            # Debug: Stocker la première occurrence pour inspection
            if debug_first_occurrence is None and premiere_occurrence:
                debug_first_occurrence = premiere_occurrence
                print("Debug - Clés disponibles dans la première occurrence:", sorted(premiere_occurrence.keys()))

            # Si aucune occurrence n'a été trouvée, passer à la suite
            if premiere_occurrence is None:
                print(f"Avertissement: Aucune occurrence trouvée pour le bon de commande {bon.numero}")
                continue

            # Récupération des montants avec conversion en float pour éviter les problèmes de type
            from decimal import Decimal
            montants = InitialReceptionBusiness.objects.filter(
                bon_commande=bon
            ).aggregate(
                total_recu=Sum('montant_recu_initial'),
                total_initial=Sum('montant_total_initial')
            )

            # Conversion des valeurs décimales en float
            montants = {k: float(v if v is not None else 0) for k, v in montants.items()}

            # Calcul du pourcentage financier
            total_initial = montants['total_initial'] or 0
            total_recu = montants['total_recu'] or 0
            financial_percent = (total_recu / total_initial) if total_initial > 0 else 0
            currency = premiere_occurrence.get('Currency')
            if currency == 'XOF':
                exchange_rate = 1.0
            else:
                # Récupérer le taux de conversion de la première occurrence
                exchange_rate_str = premiere_occurrence.get('Conversion Rate')
                try:
                    exchange_rate = float(exchange_rate_str) if exchange_rate_str else 1.0
                except (TypeError, ValueError):
                    exchange_rate = 1.0

            # Calcul du PO en XOF
            po_amount = float(bon.montant_total()) if callable(getattr(bon, 'montant_total', None)) else 0.0
            po_amount_xof = po_amount * exchange_rate


            # Calcul du retard total
            from datetime import datetime
            pip_end_str = premiere_occurrence.get('PIP END DATE')
            actual_end_str = premiere_occurrence.get('ACTUAL END DATE')
            total_days_late = 0
            if pip_end_str and actual_end_str:
                try:
                    pip_end = datetime.strptime(pip_end_str, '%Y-%m-%d')
                    actual_end = datetime.strptime(actual_end_str, '%Y-%m-%d')
                    total_days_late = (actual_end - pip_end).days
                except Exception:
                    total_days_late = 0

            # Calcul du retard imputable au vendeur
            force_majeure_value = premiere_occurrence.get('Day Late Due to Force Majeure')
            if force_majeure_value is None:
                force_majeure_value = 0
            try:
                day_late_force_majeure = float(force_majeure_value)
            except (TypeError, ValueError):
                day_late_force_majeure = 0

            day_late_due_to_vendor = max(0, total_days_late - day_late_force_majeure)

            # Calcul de Accruals (Cur)
            montant_recu = float(bon.montant_recu()) if callable(getattr(bon, 'montant_recu', None)) else 0.0
            accruals_cur = montant_recu - float(total_recu)

            # Calcul de Receipt Not Invoiced (CUR)
            invoiced_amount_str = premiere_occurrence.get("Invoiced Amount")
            try:
                invoiced_amount = float(invoiced_amount_str) if invoiced_amount_str else 0.0
            except (TypeError, ValueError):
                invoiced_amount = 0.0
            receipt_not_invoiced = float(total_recu) - invoiced_amount

            # Calcul de Année
            project_name = premiere_occurrence.get('Project Name', '')
            annee = project_name[:4] if project_name else ''

            # Calcul des nouvelles colonnes
            po_amount = float(bon.montant_total()) if callable(getattr(bon, 'montant_total', None)) else 0.0
            
            # 1. Calcul initial de Penalties (0.3% * Day Late due to Vendor * PO Amount)
            penalties = 0.003 * day_late_due_to_vendor * po_amount
            
            # 2. Calcul de Rate PO Amount (PO Amount * 10%)
            rate_po_amount = po_amount * 0.10
            
            # 3. Application de la condition : 
            # Si penalties > rate_po_amount, on prend rate_po_amount, sinon on garde penalties
            if penalties > rate_po_amount:
                penalties = rate_po_amount

            # Préparation de la ligne de données
            data.append({
                'numero': bon.numero,
                'cpu': premiere_occurrence.get('CPU'),
                'sponsor': premiere_occurrence.get('Sponsor'),
                'project_number': premiere_occurrence.get('Project Number'),
                'project_manager': premiere_occurrence.get(' Project Manager') or premiere_occurrence.get('Project Manager') or premiere_occurrence.get('Project Manager Name') or premiere_occurrence.get('Project_Manager') or premiere_occurrence.get('ProjectManager') or premiere_occurrence.get('PM') or '',
                'project_coordinator': premiere_occurrence.get('Project Coordinator'),
                'senior_technical_lead': premiere_occurrence.get('Senior Technical Lead'),
                'supplier': premiere_occurrence.get('Supplier'),
                'order_description': premiere_occurrence.get('Order Description'),
                'currency': premiere_occurrence.get('Currency'),
                'annee': annee,
                'project_name': premiere_occurrence.get('Project Name'),
                'po_type': premiere_occurrence.get('Po type'),
                'replaced_order': premiere_occurrence.get('Replaced Order'),
                'asset_type': premiere_occurrence.get('ASSET TYPE'),
                'pip_end_date': premiere_occurrence.get('PIP END DATE'),
                'revised_end_date': premiere_occurrence.get('REVISED END DATE'),
                'actual_end_date': premiere_occurrence.get('ACTUAL END DATE'),
                'line_type': premiere_occurrence.get('Line Type'),
                'code_ifs': premiere_occurrence.get('Code IFS'),
                'receipt_amount': float(total_recu),
                'po_amount': po_amount,
                'exchange_rate': exchange_rate,
                'po_amount_xof': po_amount_xof,
                'financial_percent': float(financial_percent),  # Convertir en décimal pour le format pourcentage
                'current_onground_percent': float(bon.taux_avancement() / 100) if hasattr(bon, 'taux_avancement') and callable(bon.taux_avancement) else 0.0,
                'retention_cause': bon.retention_cause or '',
                'day_late_due_to_mtn': premiere_occurrence.get("Day Late Due to MTN"),
                'day_late_due_to_force_majeure': premiere_occurrence.get("Day Late Due to Force Majeure"),
                'total_days_late': total_days_late,
                'day_late_due_to_vendor': day_late_due_to_vendor,
                'invoiced_amount': premiere_occurrence.get("Invoiced Amount"),
                'Delivery_Compliance_To_Order': premiere_occurrence.get("Delivery Compliance To Order"),
                'Delivery_Execution_Timeline': premiere_occurrence.get("Delivery Execution Timeline"),
                'Vendor_Advising_Capability': premiere_occurrence.get("Vendor Advising Capability"),
                'After_Sales_Services_QOS': premiere_occurrence.get("After Sales Services QOS"),
                'Vendor_Relationship': premiere_occurrence.get("Vendor Relationship"),
                'Vendor_Final_Rating': premiere_occurrence.get("Vendor Final Rating"),
                'accruals_cur': accruals_cur,
                'receipt_not_invoiced': receipt_not_invoiced,
                'penalties': penalties,  # Colonne Penalties (déjà mise à jour avec la condition)
                'pip_retention_percent': (penalties / po_amount) if po_amount > 0 else 0.0,  # % PIP retention
                'other_retentions': float(bon.retention_rate) / 100 if bon.retention_rate is not None else 0.0,
                'total_retention': (penalties / po_amount if po_amount > 0 else 0.0) + (float(bon.retention_rate) / 100 if bon.retention_rate is not None else 0.0),
                
            })

        # Création du DataFrame à partir des données préparées
        df = pd.DataFrame(data)

        # Renommage des colonnes pour l'export
        column_mapping = {
            'numero': 'Order Number',
            'cpu': 'CPU',
            'sponsor': 'Sponsor',
            'project_number': 'Project Number',
            'project_manager': 'Project Manager',
            'project_coordinator': 'Project Coordinator',
            'senior_technical_lead': 'Senior Technical Lead',
            'supplier': 'Supplier Name',
            'penalties': 'Penalties',
            'order_description': 'Order Description',
            'currency': 'Currency',
            'annee': 'Année',
            'project_name': 'Project Name',
            'po_type': 'PO Type',
            'replaced_order': 'Replaced Order',
            'asset_type': 'Asset Type',
            'pip_end_date': 'PIP End Date',
            'revised_end_date': 'Revised End Date',
            'actual_end_date': 'Actual End Date',
            'line_type': 'Line Type',
            'code_ifs': 'Code IFS',
            'current_onground_percent': 'Current Onground (%)',
            'retention_cause': 'Cause rétention',
            'receipt_amount': 'Receipt Amount',
            'po_amount': 'PO Amount',  # Ajouter le mapping pour la nouvelle colonne
            'exchange_rate': 'Exchange Rate',
            'po_amount_xof': 'PO XOF',
            'financial_percent': '%Financial',
            'day_late_due_to_mtn': 'Day Late Due to MTN',
            'day_late_due_to_force_majeure': 'Day Late Due to Force Majeure',
            'total_days_late': '# Total Days Late',
            'day_late_due_to_vendor': 'Day Late Due to Vendor',
            'invoiced_amount': 'Invoiced Amount',
            'Delivery_Compliance_To_Order': 'Delivery Compliance To Order',
            'Delivery_Execution_Timeline': 'Delivery Execution Timeline',
            'Vendor_Advising_Capability': 'Vendor Advising Capability',
            'After_Sales_Services_QOS': 'After Sales Services QOS',
            'Vendor_Relationship': 'Vendor Relationship',
            'Vendor_Final_Rating': 'Vendor Final Rating',
            'accruals_cur': 'Accruals (Cur)',
            'receipt_not_invoiced': 'Receipt Not Invoiced (CUR)',
            'pip_retention_percent': '% PIP Retention',
            'other_retentions': 'Other Retentions (%)',
            'total_retention': 'Total Retention (%)',
        }
        df.rename(columns=column_mapping, inplace=True)

        # Création du fichier Excel avec mise en forme
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='PO Progress Monitoring')
            workbook = writer.book
            worksheet = writer.sheets['PO Progress Monitoring']

            # Styles
            header_font = Font(bold=True, color="FFFFFF")
            header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
            alignment = Alignment(horizontal="center", vertical="center")
            thin_border = Border(
                left=Side(style='thin'),
                right=Side(style='thin'),
                top=Side(style='thin'),
                bottom=Side(style='thin')
            )

            # Format header
            for col_num, value in enumerate(df.columns.values, 1):
                cell = worksheet.cell(row=1, column=col_num)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = alignment
                cell.border = thin_border
                worksheet.column_dimensions[get_column_letter(col_num)].width = max(len(value) + 2, 15)

            # Format data cells
            for row in worksheet.iter_rows(min_row=2, max_row=worksheet.max_row,
                                           min_col=1, max_col=worksheet.max_column):
                for cell in row:
                    cell.border = thin_border
                    if isinstance(cell.value, (int, float)):
                        cell.number_format = '0.00'

            # Format percentages
            percent_columns = ['Current Onground (%)', 'Retention Rate (%)', '%Financial', 'PIP Retention (%)', 'Over Retentions (%)', 'Total Retention (%)']
            for col_name in percent_columns:
                if col_name in df.columns:
                    col_idx = df.columns.get_loc(col_name) + 1
                    for row in range(2, worksheet.max_row + 1):
                        cell = worksheet.cell(row=row, column=col_idx)
                        cell.number_format = '0.00%'

        # Préparer la réponse HTTP
        output.seek(0)
        response = HttpResponse(
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="po_progress_monitoring.xlsx"'

        return response

    except Exception as e:
        logger.error(f"Erreur lors de l'export PO Progress Monitoring: {str(e)}")
        return HttpResponse(
            f"Une erreur s'est produite lors de l'export: {str(e)}",
            status=500
        )
