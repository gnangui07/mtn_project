"""
Vues d'export Excel pour les bons de commande
Contient toutes les fonctions d'export volumineuses (> 200 lignes)
"""

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Sum, F, Value, DecimalField, ExpressionWrapper, Case, When, Subquery, OuterRef, FloatField
import pandas as pd
from io import BytesIO
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter
import logging
import os
from datetime import datetime, date
from decimal import Decimal

logger = logging.getLogger(__name__)


# ============================================================================
# EXPORTS EXCEL
# ============================================================================

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
            'fichiers__lignes',
            'receptions'
        ).all()
        
        # Debug: Afficher les clés disponibles dans la première occurrence
        debug_first_occurrence = None
        
        # Étape 1: Créer un cache pour les premières occurrences de chaque bon de commande en une seule passe globale
        orders_needed = {bon.numero for bon in bons_commande}

        def find_order_key(contenu: dict):
            # 1) Cas exact 'Order'
            if 'Order' in contenu:
                return 'Order'
            # 2) Recherche tolérante (espaces/underscores/accents)
            for k in contenu.keys():
                if not k:
                    continue
                norm = ' '.join(str(k).strip().lower().replace('_', ' ').split())
                if 'order' in norm or 'commande' in norm or 'bon' in norm or norm == 'bc':
                    return k
            return None

        # Lister tous les fichiers associés, triés par date d'importation
        all_files = []
        for bon in bons_commande:
            for fichier in bon.fichiers.all():
                all_files.append(fichier)
        all_files.sort(key=lambda f: f.date_importation)

        first_occurrence_cache = {}
        for fichier in all_files:
            lignes = list(fichier.lignes.all())
            lignes.sort(key=lambda l: l.numero_ligne)
            for ligne in lignes:
                contenu = ligne.contenu or {}
                order_key = find_order_key(contenu)
                if not order_key:
                    continue
                order_val = str(contenu.get(order_key, '')).strip()
                if not order_val:
                    continue
                if order_val in orders_needed and order_val not in first_occurrence_cache:
                    first_occurrence_cache[order_val] = contenu
                    if len(first_occurrence_cache) == len(orders_needed):
                        break
            if len(first_occurrence_cache) == len(orders_needed):
                break

        # Étape 2: Préparation des données pour le DataFrame
        # Helper: récupérer une valeur par normalisation tolérante des en-têtes
        def get_value_tolerant(contenu: dict, exact_candidates=None, tokens=None):
            """Retourne la valeur pour une clé en acceptant des variantes d'en-têtes.
            - exact_candidates: liste de libellés candidats (str) comparés après normalisation
            - tokens: liste de mots qui doivent tous être présents dans l'en-tête normalisé
            Gestionne notamment: espaces de fin/début, doubles espaces, underscores, casse.
            """
            if not contenu:
                return None
            def norm(s: str):
                # strip -> lower -> remplace _ et - par espace -> compresse espaces -> retire espaces fin/début
                return ' '.join(str(s).strip().lower().replace('_', ' ').replace('-', ' ').split())
            # Construire un mapping normalisé -> (clé originale, valeur)
            normalized = {norm(k): (k, v) for k, v in contenu.items() if k}

            # 1) Essais exacts (après normalisation)
            if exact_candidates:
                for cand in exact_candidates:
                    nk = norm(cand)
                    if nk in normalized:
                        return normalized[nk][1]

            # 2) Recherche par tokens (tous présents dans la clé normalisée)
            if tokens:
                needed = [norm(t) for t in tokens]
                for nk, (_ok, v) in normalized.items():
                    if all(t in nk for t in needed):
                        return v
            return None
        data = []
        for bon in bons_commande:
            # Récupérer la première occurrence de ce bon de commande
            premiere_occurrence = first_occurrence_cache.get(bon.numero)
            
            # Récupérer l'évaluation fournisseur depuis la base de données
            from .models import VendorEvaluation
            vendor_evaluation = VendorEvaluation.objects.filter(bon_commande=bon).first()
            
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
            financial_percent = ((total_recu / total_initial) * 100) if total_initial > 0 else 0
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


            # Recalculer le retard total à partir des dates (supporte plusieurs formats)
            from datetime import datetime
            pip_end_str = premiere_occurrence.get('PIP END DATE')
            actual_end_str = premiere_occurrence.get('ACTUAL END DATE')
            total_days_late = 0
            if pip_end_str and actual_end_str:
                try:
                    # Convertir en string et nettoyer
                    pip_end_str = str(pip_end_str).strip()
                    actual_end_str = str(actual_end_str).strip()
                    
                    # Liste des formats supportés
                    date_formats = [
                        '%Y-%m-%d %H:%M:%S',  # 2025-07-30 00:00:00
                        '%Y-%m-%d',           # 2025-07-30
                        '%d/%m/%Y',           # 30/07/2025
                        '%d/%m/%Y %H:%M:%S'   # 30/07/2025 00:00:00
                    ]
                    
                    pip_end = None
                    actual_end = None
                    
                    # Essayer chaque format pour PIP END DATE
                    for fmt in date_formats:
                        try:
                            pip_end = datetime.strptime(pip_end_str, fmt)
                            break
                        except ValueError:
                            continue
                    
                    # Essayer chaque format pour ACTUAL END DATE
                    for fmt in date_formats:
                        try:
                            actual_end = datetime.strptime(actual_end_str, fmt)
                            break
                        except ValueError:
                            continue
                    
                    if pip_end and actual_end:
                        total_days_late = (actual_end - pip_end).days
                    else:
                        total_days_late = 0
                except Exception:
                    total_days_late = 0

            # Calcul du retard imputable au vendeur à partir du total et de la force majeure
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

            # Pré-calculs pour limiter les appels et accélérer
            taux_avancement_percent = float(bon.taux_avancement()) if hasattr(bon, 'taux_avancement') and callable(bon.taux_avancement) else 0.0
            current_onground = taux_avancement_percent  # Garder en pourcentage pour l'affichage
            current_onground_fraction = taux_avancement_percent / 100  # Fraction pour les calculs
            delivery_amount_cur = current_onground_fraction * po_amount
            delivery_amount_xof = current_onground_fraction * po_amount_xof
            financial_percent_float = float(financial_percent)
            receipt_amount = float(total_recu)
            invoiced_amount_value = int(float(premiere_occurrence.get("Invoiced Amount", 0))) if premiere_occurrence.get("Invoiced Amount") else 0
            retention_rate_fraction = float(bon.retention_rate) if bon.retention_rate is not None else 0.0
            pip_retention_percent_val = ((penalties / po_amount) * 100) if po_amount > 0 else 0.0
            total_retention_val = pip_retention_percent_val + retention_rate_fraction

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
                'annee': premiere_occurrence.get('Année'),
                'project_name': premiere_occurrence.get('Project Name'),
                'po_type': premiere_occurrence.get('Po type'),
                'replaced_order': premiere_occurrence.get('Replaced Order'),
                'asset_type': premiere_occurrence.get('ASSET TYPE'),
                'pip_end_date': premiere_occurrence.get('PIP END DATE'),
                'revised_end_date': premiere_occurrence.get('REVISED END DATE'),
                'actual_end_date': premiere_occurrence.get('ACTUAL END DATE'),
                'line_type': premiere_occurrence.get('Line Type'),
                'code_ifs': premiere_occurrence.get('Code - IFS'),
                'po_amount': po_amount,
                'exchange_rate': exchange_rate,
                'po_amount_xof': po_amount_xof,
                'current_onground_percent': current_onground,
                'financial_percent': financial_percent_float,  # Convertir en décimal pour le format pourcentage
                'delivery_amount_cur': delivery_amount_cur,
                'delivery_amount_xof': delivery_amount_xof,
                'receipt_amount': receipt_amount,
                'invoiced_amount': invoiced_amount_value,
                'receipt_not_invoiced': receipt_not_invoiced,
                'accruals_cur': accruals_cur,
                'day_late_due_to_mtn': premiere_occurrence.get('Day Late Due to MTN'),
                'day_late_due_to_force_majeure': premiere_occurrence.get('Day Late Due to Force Majeure'),
                'total_days_late': total_days_late,
                'day_late_due_to_vendor': day_late_due_to_vendor,
                'retention_cause': bon.retention_cause or '',
                'penalties': penalties,  # Colonne Penalties (déjà mise à jour avec la condition)
                'pip_retention_percent': pip_retention_percent_val,  # % PIP retention
                'other_retentions': retention_rate_fraction,
                'total_retention': total_retention_val,
                # Colonnes d'évaluation fournisseur: Priorité BD, fallback fichier Excel
                'Delivery_Compliance_To_Order': (
                    vendor_evaluation.delivery_compliance if vendor_evaluation else
                    get_value_tolerant(premiere_occurrence, exact_candidates=['Delivery Compliance to Order (Quantity & Quality)', 'Delivery Compliance to Order', 'Delivery Compliance To Order'], tokens=['delivery', 'compliance', 'order']) or ''
                ),
                'Delivery_Execution_Timeline': (
                    vendor_evaluation.delivery_timeline if vendor_evaluation else
                    get_value_tolerant(premiere_occurrence, exact_candidates=['Delivery Execution  Timeline', 'Delivery Execution Timeline'], tokens=['delivery', 'execution', 'timeline']) or ''
                ),
                'Vendor_Advising_Capability': (
                    vendor_evaluation.advising_capability if vendor_evaluation else
                    get_value_tolerant(premiere_occurrence, exact_candidates=['Vendor Advising Capability'], tokens=['vendor', 'advising', 'capability']) or ''
                ),
                'After_Sales_Services_QOS': (
                    vendor_evaluation.after_sales_qos if vendor_evaluation else
                    get_value_tolerant(premiere_occurrence, exact_candidates=['After Sales Services QOS', 'After Sales Services QoS', 'After Sales Service QOS'], tokens=['after', 'sales', 'services', 'qos']) or ''
                ),
                'Vendor_Relationship': (
                    vendor_evaluation.vendor_relationship if vendor_evaluation else
                    get_value_tolerant(premiere_occurrence, exact_candidates=['Vendor Relationship'], tokens=['vendor', 'relationship']) or ''
                ),
                'Vendor_Final_Rating': (
                    float(vendor_evaluation.vendor_final_rating) if vendor_evaluation else
                    get_value_tolerant(premiere_occurrence, exact_candidates=['Vendor Final Rating'], tokens=['vendor', 'final', 'rating']) or ''
                ),
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
            'code_ifs': 'Code-IFS',
            'po_amount': 'PO Amount',
            'exchange_rate': 'Exchange Rate',
            'po_amount_xof': 'PO XOF',
            'current_onground_percent': 'Current Onground (%)',
            'financial_percent': '%Financial',
            'delivery_amount_cur': 'Delivery Amount (CUR)',
            'delivery_amount_xof': 'Delivery Amount (XOF)',
            'receipt_amount': 'Receipt Amount',
            'invoiced_amount': 'Invoiced Amount',
            'receipt_not_invoiced': 'Receipt Not Invoiced (CUR)',
            'accruals_cur': 'Accruals (Cur)',
            'day_late_due_to_mtn': 'Day Late Due to MTN',
            'day_late_due_to_force_majeure': 'Day Late Due to Force Majeure',
            'total_days_late': '# Total Days Late',
            'day_late_due_to_vendor': 'Day Late Due to Vendor',
            'retention_cause': 'Cause rétention',
            'penalties': 'Penalties',
            'pip_retention_percent': '% PIP Retention',
            'other_retentions': 'Other Retentions (%)',
            'total_retention': 'Total Retention (%)',
            'Delivery_Compliance_To_Order': 'Delivery Compliance To Order',
            'Delivery_Execution_Timeline': 'Delivery Execution Timeline',
            'Vendor_Advising_Capability': 'Vendor Advising Capability',
            'After_Sales_Services_QOS': 'After Sales Services QOS',
            'Vendor_Relationship': 'Vendor Relationship',
            'Vendor_Final_Rating': 'Vendor Final Rating',
        }
        df.rename(columns=column_mapping, inplace=True)

        # Normaliser les colonnes de dates en chaînes 'YYYY-MM-DD' (format base de données)
        from datetime import date, datetime as dt
        for _col in ['PIP End Date', 'Revised End Date', 'Actual End Date']:
            if _col in df.columns:
                def _to_iso(v):
                    if v is None:
                        return ''
                    if isinstance(v, (dt, date)):
                        return v.strftime('%Y-%m-%d')
                    if isinstance(v, str):
                        s = v.strip()
                        # Déjà au format ISO
                        if len(s) >= 10 and s[4] == '-' and s[7] == '-':
                            return s[:10]
                        # Essayer dd/mm/YYYY
                        try:
                            return dt.strptime(s, '%d/%m/%Y').strftime('%Y-%m-%d')
                        except Exception:
                            pass
                        # Essayer dd-mm-YYYY
                        try:
                            return dt.strptime(s, '%d-%m-%Y').strftime('%Y-%m-%d')
                        except Exception:
                            pass
                        # Par défaut, renvoyer tel quel
                        return s
                    return str(v)
                df[_col] = df[_col].map(_to_iso)

        # Forcer l'affichage des montants sans décimales pour Invoiced Amount
        if 'Invoiced Amount' in df.columns:
            df['Invoiced Amount'] = df['Invoiced Amount'].astype(int)

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

            # Apply borders to data cells (no per-cell numeric formatting to improve speed)
            for row in worksheet.iter_rows(min_row=2, max_row=worksheet.max_row,
                                           min_col=1, max_col=worksheet.max_column):
                for cell in row:
                    cell.border = thin_border

            # Format only specific numeric columns to reduce processing time
            numeric_cols = [
                'PO Amount', 'PO XOF', 'Receipt Amount', 'Accruals (Cur)',
                'Receipt Not Invoiced (CUR)', 'Delivery Amount (CUR)', 'Delivery Amount (XOF)', 'Penalties'
            ]
            for col_name in numeric_cols:
                if col_name in df.columns:
                    col_idx = df.columns.get_loc(col_name) + 1
                    for row in range(2, worksheet.max_row + 1):
                        cell = worksheet.cell(row=row, column=col_idx)
                        cell.number_format = '0.00'

            # Format percentages
            # Note: Les valeurs sont déjà en pourcentage (10 pour 10%), format français avec virgule
            percent_columns = ['Current Onground (%)', 'Retention Rate (%)', '%Financial', '% PIP Retention', 'Other Retentions (%)', 'Total Retention (%)']
            for col_name in percent_columns:
                if col_name in df.columns:
                    col_idx = df.columns.get_loc(col_name) + 1
                    for row in range(2, worksheet.max_row + 1):
                        cell = worksheet.cell(row=row, column=col_idx)
                        if cell.value is not None:
                            # Formater avec virgule et supprimer les zéros inutiles
                            formatted = f"{float(cell.value):.2f}".replace('.', ',').rstrip('0').rstrip(',')
                            cell.value = f"{formatted}%"
                        else:
                            cell.value = ""
                        cell.number_format = '@'  # Format texte pour garder le %

            # Force text format for date-like columns to preserve original values exactly as in source file
            text_cols = ['PIP End Date', 'Revised End Date', 'Actual End Date']
            for col_name in text_cols:
                if col_name in df.columns:
                    col_idx = df.columns.get_loc(col_name) + 1
                    for row in range(2, worksheet.max_row + 1):
                        cell = worksheet.cell(row=row, column=col_idx)
                        cell.number_format = '@'  # Treat as text in Excel

            # Ensure Invoiced Amount shows without decimals
            if 'Invoiced Amount' in df.columns:
                inv_idx = df.columns.get_loc('Invoiced Amount') + 1
                for row in range(2, worksheet.max_row + 1):
                    cell = worksheet.cell(row=row, column=inv_idx)
                    cell.number_format = '0'

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

@login_required
def export_msrn_po_lines(request, msrn_id):
    """
    Exporte les Purchase Order Lines d'un rapport MSRN en Excel
    """
    try:
        from .models import MSRNReport, Reception, LigneFichier
        from decimal import Decimal
        import pandas as pd
        from io import BytesIO
        from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
        from openpyxl.utils import get_column_letter
        
        # Récupérer le rapport MSRN
        msrn_report = get_object_or_404(MSRNReport, id=msrn_id)
        bon_commande = msrn_report.bon_commande
        retention_rate = msrn_report.retention_rate or Decimal('0')
        
        # Récupérer les réceptions depuis la base de données
        receptions = Reception.objects.filter(bon_commande=bon_commande).order_by('business_id')
        
        # Extraire les lignes de commande
        po_lines = list(receptions)
        
        if not po_lines:
            return HttpResponse("No Purchase Order Lines found for this MSRN", status=404)
        
        # Préparer les données pour le DataFrame
        data = []
        for reception in po_lines:
            # Récupérer les informations de ligne depuis le fichier
            line_description = "N/A"
            line = "N/A"
            schedule = "N/A"
            
            try:
                lf = LigneFichier.objects.filter(business_id=reception.business_id).order_by('-id').first()
                if lf and lf.contenu:
                    line_description = lf.contenu.get('Line Description', 'N/A')
                    line = lf.contenu.get('Line', 'N/A')
                    schedule = lf.contenu.get('Schedule', 'N/A')
            except Exception:
                pass
            
            # Calculer Net Qty to Receipt in Boost
            quantity_payable = reception.quantity_payable or 0
            received_quantity = reception.received_quantity or 0
            net_qty_to_receipt = Decimal(str(quantity_payable)) - Decimal(str(received_quantity))
            
            # Calculer Amount Payable avec retention
            amount_delivered = reception.amount_delivered or 0
            retention_amount = amount_delivered * (retention_rate / Decimal('100'))
            amount_payable = amount_delivered - retention_amount
            
            row = {
                'Purchase Order': bon_commande.numero if bon_commande else 'N/A',
                'Line': line,
                'Schedule': schedule,
                'Line Description': line_description,
                'Ordered Quantity': float(reception.ordered_quantity or 0),
                'Received Quantity': float(received_quantity),
                'Quantity Delivered': float(reception.quantity_delivered or 0),
                'Unit Price': float(reception.unit_price or 0),
                'Amount Delivered': float(amount_delivered),
                'Net Qty to Receipt in Boost': float(net_qty_to_receipt),
                'Quantity Payable': float(quantity_payable),
                'Amount Payable': float(amount_payable),
            }
            data.append(row)
        
        # Créer le DataFrame pour les lignes PO
        df_lines = pd.DataFrame(data)
        
        # Préparer les données du MSRN (en-tête)
        msrn_info = {
            'Field': [
                'MSRN Number',
                'Purchase Order',
                'Supplier',
                'Currency',
                'PO Amount',
                'Amount Delivered',
                'Delivery Rate (%)',
                'Payment Retention Rate (%)',
                'Retention Cause',
                'Created Date',
            ],
            'Value': [
                msrn_report.report_number,
                bon_commande.numero if bon_commande else 'N/A',
                bon_commande.get_supplier() if bon_commande and callable(getattr(bon_commande, 'get_supplier', None)) else 'N/A',
                bon_commande.get_currency() if bon_commande and callable(getattr(bon_commande, 'get_currency', None)) else 'N/A',
                float(bon_commande.montant_total()) if bon_commande and callable(getattr(bon_commande, 'montant_total', None)) else 0,
                float(bon_commande.montant_recu()) if bon_commande and callable(getattr(bon_commande, 'montant_recu', None)) else 0,
                float(msrn_report.progress_rate_snapshot or 0),
                float(retention_rate),
                msrn_report.retention_cause or 'N/A',
                msrn_report.created_at.strftime('%Y-%m-%d %H:%M:%S') if msrn_report.created_at else 'N/A',
            ]
        }
        df_msrn = pd.DataFrame(msrn_info)
        
        # Créer le fichier Excel avec mise en forme
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Onglet 1: Informations MSRN
            df_msrn.to_excel(writer, index=False, sheet_name='MSRN Information')
            
            # Onglet 2: Purchase Order Lines
            df_lines.to_excel(writer, index=False, sheet_name='Purchase Order Lines')
            
            workbook = writer.book
            
            # ===== FORMATAGE ONGLET MSRN INFORMATION =====
            ws_msrn = writer.sheets['MSRN Information']
            
            # Styles pour MSRN Info
            header_font = Font(bold=True, color="FFFFFF")
            header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
            field_font = Font(bold=True)
            field_fill = PatternFill(start_color="E8F4F8", end_color="E8F4F8", fill_type="solid")
            alignment_center = Alignment(horizontal="center", vertical="center")
            alignment_left = Alignment(horizontal="left", vertical="center")
            thin_border = Border(
                left=Side(style='thin'),
                right=Side(style='thin'),
                top=Side(style='thin'),
                bottom=Side(style='thin')
            )
            
            # Format header MSRN
            for col_num in range(1, 3):
                cell = ws_msrn.cell(row=1, column=col_num)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = alignment_center
                cell.border = thin_border
            
            ws_msrn.column_dimensions['A'].width = 30
            ws_msrn.column_dimensions['B'].width = 50
            
            # Format data cells MSRN
            for row in range(2, ws_msrn.max_row + 1):
                # Colonne Field (A)
                cell_field = ws_msrn.cell(row=row, column=1)
                cell_field.font = field_font
                cell_field.fill = field_fill
                cell_field.alignment = alignment_left
                cell_field.border = thin_border
                
                # Colonne Value (B)
                cell_value = ws_msrn.cell(row=row, column=2)
                cell_value.alignment = alignment_left
                cell_value.border = thin_border
                
                # Format numérique si applicable
                if isinstance(cell_value.value, (int, float)):
                    cell_value.number_format = '#,##0.00'
            
            # ===== FORMATAGE ONGLET PURCHASE ORDER LINES =====
            worksheet = writer.sheets['Purchase Order Lines']
            
            # Styles
            header_font = Font(bold=True, color="FFFFFF")
            header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
            alignment_center = Alignment(horizontal="center", vertical="center")
            alignment_right = Alignment(horizontal="right", vertical="center")
            thin_border = Border(
                left=Side(style='thin'),
                right=Side(style='thin'),
                top=Side(style='thin'),
                bottom=Side(style='thin')
            )
            
            # Format header
            for col_num, value in enumerate(df_lines.columns.values, 1):
                cell = worksheet.cell(row=1, column=col_num)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = alignment_center
                cell.border = thin_border
                worksheet.column_dimensions[get_column_letter(col_num)].width = max(len(str(value)) + 2, 15)
            
            # Format data cells
            for row in worksheet.iter_rows(min_row=2, max_row=worksheet.max_row,
                                           min_col=1, max_col=worksheet.max_column):
                for cell in row:
                    cell.border = thin_border
                    # Aligner les nombres à droite
                    if isinstance(cell.value, (int, float)):
                        cell.alignment = alignment_right
                        cell.number_format = '#,##0.00'
            
            # Ajouter une ligne de total si nécessaire
            total_row = worksheet.max_row + 2
            worksheet.cell(row=total_row, column=1, value="TOTAL")
            worksheet.cell(row=total_row, column=1).font = Font(bold=True)
            
        # Préparer la réponse HTTP
        output.seek(0)
        response = HttpResponse(
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        filename = f"MSRN_{msrn_report.report_number}_PO_Lines.xlsx"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
        
    except Exception as e:
        logger.error(f"Erreur lors de l'export des PO Lines: {str(e)}")
        return HttpResponse(
            f"Une erreur s'est produite lors de l'export: {str(e)}",
            status=500
        )

@login_required
def export_vendor_evaluations(request):
    """
    Exporte toutes les évaluations des fournisseurs en Excel avec logique robuste
    """
    from .models import VendorEvaluation, NumeroBonCommande
    import pandas as pd
    from io import BytesIO
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    from datetime import datetime
    from decimal import Decimal
    
    # Helper: fonction pour trouver la clé 'Order' de manière tolérante
    def find_order_key(contenu: dict):
        if 'Order' in contenu:
            return 'Order'
        for k in contenu.keys():
            if not k:
                continue
            norm = ' '.join(str(k).strip().lower().replace('_', ' ').split())
            if 'order' in norm or 'commande' in norm or 'bon' in norm or norm == 'bc':
                return k
        return None
    
    # Helper: récupérer une valeur par normalisation tolérante des en-têtes
    def get_value_tolerant(contenu: dict, exact_candidates=None, tokens=None):
        if not contenu:
            return None
        def norm(s: str):
            return ' '.join(str(s).strip().lower().replace('_', ' ').replace('-', ' ').split())
        normalized = {norm(k): (k, v) for k, v in contenu.items() if k}
        
        # Essais exacts (après normalisation)
        if exact_candidates:
            for cand in exact_candidates:
                nk = norm(cand)
                if nk in normalized:
                    return normalized[nk][1]
        
        # Recherche par tokens
        if tokens:
            needed = [norm(t) for t in tokens]
            for nk, (_ok, v) in normalized.items():
                if all(t in nk for t in needed):
                    return v
        return None
    
    # Récupérer les évaluations avec filtres (mêmes que la liste)
    evaluations = VendorEvaluation.objects.select_related(
        'bon_commande', 'evaluator'
    ).prefetch_related('bon_commande__fichiers__lignes').order_by('supplier', '-date_evaluation')
    
    # Appliquer les filtres de la requête
    supplier_filter = request.GET.get('supplier', '').strip()
    if supplier_filter:
        evaluations = evaluations.filter(supplier__icontains=supplier_filter)
    
    min_score = request.GET.get('min_score', '').strip()
    if min_score:
        try:
            min_score_int = int(min_score)
            filtered_ids = []
            for eval in evaluations:
                if eval.get_total_score() >= min_score_int:
                    filtered_ids.append(eval.id)
            evaluations = evaluations.filter(id__in=filtered_ids)
        except ValueError:
            pass
    
    date_from = request.GET.get('date_from', '').strip()
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            evaluations = evaluations.filter(date_evaluation__date__gte=date_from_obj)
        except ValueError:
            pass
    
    date_to = request.GET.get('date_to', '').strip()
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
            evaluations = evaluations.filter(date_evaluation__date__lte=date_to_obj)
        except ValueError:
            pass
    
    # Étape 1: Créer un cache pour les premières occurrences de chaque bon de commande
    orders_needed = {eval.bon_commande.numero for eval in evaluations}
    
    all_files = []
    for evaluation in evaluations:
        for fichier in evaluation.bon_commande.fichiers.all():
            if fichier not in all_files:
                all_files.append(fichier)
    all_files.sort(key=lambda f: f.date_importation)
    
    first_occurrence_cache = {}
    for fichier in all_files:
        lignes = list(fichier.lignes.all())
        lignes.sort(key=lambda l: l.numero_ligne)
        for ligne in lignes:
            contenu = ligne.contenu or {}
            order_key = find_order_key(contenu)
            if not order_key:
                continue
            order_val = str(contenu.get(order_key, '')).strip()
            if not order_val:
                continue
            if order_val in orders_needed and order_val not in first_occurrence_cache:
                first_occurrence_cache[order_val] = contenu
                if len(first_occurrence_cache) == len(orders_needed):
                    break
        if len(first_occurrence_cache) == len(orders_needed):
            break
    
    # Étape 2: Construire les données
    data = []
    
    for evaluation in evaluations:
        bon = evaluation.bon_commande
        supplier = evaluation.supplier
        
        # Récupérer la première occurrence de ce bon de commande
        premiere_occurrence = first_occurrence_cache.get(bon.numero)
        
        if premiere_occurrence:
            # Extraire les informations avec get_value_tolerant
            item = get_value_tolerant(premiere_occurrence, 
                exact_candidates=['Order Description', 'Item Description', 'Description'],
                tokens=['order', 'description']) or 'N/A'
            
            pm = get_value_tolerant(premiere_occurrence,
                exact_candidates=['Project Manager', 'PM', 'Manager'],
                tokens=['project', 'manager']) or 'N/A'
            
            pip_end_date_raw = get_value_tolerant(premiere_occurrence,
                exact_candidates=['PIP END DATE', 'PIP End Date', 'Pip End Date'],
                tokens=['pip', 'end', 'date']) or ''
            
            actual_end_date_raw = get_value_tolerant(premiere_occurrence,
                exact_candidates=['ACTUAL END DATE', 'Actual End Date', 'Real End Date'],
                tokens=['actual', 'end', 'date']) or ''
            
            # Normaliser les dates au format YYYY-MM-DD (comme dans PO Progress)
            def normalize_date(date_val):
                """Normalise une date au format YYYY-MM-DD"""
                if not date_val:
                    return ''
                
                date_str = str(date_val).strip()
                
                # Si déjà au format ISO avec timestamp, extraire la date
                if len(date_str) >= 10 and date_str[4] == '-' and date_str[7] == '-':
                    return date_str[:10]  # Prendre seulement YYYY-MM-DD
                
                # Essayer de parser d'autres formats
                date_formats = ['%d/%m/%Y', '%d-%m-%Y', '%Y/%m/%d']
                for fmt in date_formats:
                    try:
                        parsed = datetime.strptime(date_str, fmt)
                        return parsed.strftime('%Y-%m-%d')
                    except ValueError:
                        continue
                
                # Par défaut, retourner tel quel
                return date_str
            
            pip_end_date = normalize_date(pip_end_date_raw)
            actual_end_date = normalize_date(actual_end_date_raw)
            
            # Calculer le nombre de jours de retard (supporte plusieurs formats)
            total_days_late = 0
            if pip_end_date and actual_end_date:
                try:
                    # Convertir en string et nettoyer
                    pip_end_str = str(pip_end_date).strip()
                    actual_end_str = str(actual_end_date).strip()
                    
                    # Liste des formats supportés
                    date_formats = [
                        '%Y-%m-%d %H:%M:%S',  # 2025-07-30 00:00:00
                        '%Y-%m-%d',           # 2025-07-30
                        '%d/%m/%Y',           # 30/07/2025
                        '%d/%m/%Y %H:%M:%S'   # 30/07/2025 00:00:00
                    ]
                    
                    pip_end = None
                    actual_end = None
                    
                    # Essayer chaque format pour PIP END DATE
                    for fmt in date_formats:
                        try:
                            pip_end = datetime.strptime(pip_end_str, fmt)
                            break
                        except ValueError:
                            continue
                    
                    # Essayer chaque format pour ACTUAL END DATE
                    for fmt in date_formats:
                        try:
                            actual_end = datetime.strptime(actual_end_str, fmt)
                            break
                        except ValueError:
                            continue
                    
                    if pip_end and actual_end:
                        total_days_late = max(0, (actual_end - pip_end).days)
                    else:
                        total_days_late = 0
                except Exception as e:
                    total_days_late = 0
        else:
            item = 'N/A'
            pm = 'N/A'
            pip_end_date = ''
            actual_end_date = ''
            total_days_late = 0
        
        # Récupérer le montant total du PO
        montant_total = bon.montant_total() if callable(getattr(bon, 'montant_total', None)) else Decimal('0')
        
        # Construire la ligne de données
        row = {
            'N° PO': bon.numero,
            'FOURNISSEURS': supplier,
            'ITEM': str(item),
            'MONTANT PO': float(montant_total),
            'PM': str(pm),
            'Conformité de la commande (quantité & qualité)': evaluation.delivery_compliance,
            'Délai de livraison, implémentation, exécution,…': evaluation.delivery_timeline,
            'Capacité à conseiller (transfert de compétence, formation, Autonomie du client)': evaluation.advising_capability,
            'Qualité du SAV': evaluation.after_sales_qos,
            'Contact relationnel': evaluation.vendor_relationship,
            'NOTE GLOBALE': float(evaluation.vendor_final_rating),
            'DATE DE FIN CONTRACTUELLE(PIP)': pip_end_date,
            'DATE DE FIN REELLE': actual_end_date,
            'NOMBRE TOTAL DE JOURS DE RETARD': total_days_late,
            'PART MTN': getattr(bon.timeline_delay, 'delay_part_mtn', 0) if hasattr(bon, 'timeline_delay') else 0,
            'PART FORCE MAJEURE': getattr(bon.timeline_delay, 'delay_part_force_majeure', 0) if hasattr(bon, 'timeline_delay') else 0,
            'PART FOURNISSEUR': getattr(bon.timeline_delay, 'delay_part_vendor', 0) if hasattr(bon, 'timeline_delay') else 0,
            'Montant Rétention Timeline': float(getattr(bon.timeline_delay, 'retention_amount_timeline', 0)) if hasattr(bon, 'timeline_delay') else 0,
            'Taux Rétention Timeline (%)': f"{float(getattr(bon.timeline_delay, 'retention_rate_timeline', 0)) if hasattr(bon, 'timeline_delay') else 0:.2f}%".replace('.', ','),
        }
        
        data.append(row)
    
    # Créer le DataFrame
    df = pd.DataFrame(data)
    
    # Remplacer les valeurs vides par des chaînes vides pour éviter NaT
    df['DATE DE FIN CONTRACTUELLE(PIP)'] = df['DATE DE FIN CONTRACTUELLE(PIP)'].fillna('')
    df['DATE DE FIN REELLE'] = df['DATE DE FIN REELLE'].fillna('')
    
    # Créer le fichier Excel
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Vendor Evaluations')
        
        # Récupérer le workbook et la feuille
        workbook = writer.book
        worksheet = writer.sheets['Vendor Evaluations']
        
        # Styles
        header_font = Font(bold=True, color="000000", size=11)
        header_fill = PatternFill(start_color="FFCC00", end_color="FFCC00", fill_type="solid")
        alignment_center = Alignment(horizontal="center", vertical="center", wrap_text=True)
        alignment_left = Alignment(horizontal="left", vertical="center")
        alignment_right = Alignment(horizontal="right", vertical="center")
        thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        
        # Formater l'en-tête
        for col_num, column_title in enumerate(df.columns, 1):
            cell = worksheet.cell(row=1, column=col_num)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = alignment_center
            cell.border = thin_border
            
            # Ajuster la largeur des colonnes
            if 'DATE' in column_title or 'N° PO' in column_title:
                worksheet.column_dimensions[get_column_letter(col_num)].width = 20
            elif 'MONTANT' in column_title or 'Rétention' in column_title:
                worksheet.column_dimensions[get_column_letter(col_num)].width = 18
            elif 'NOTE' in column_title:
                worksheet.column_dimensions[get_column_letter(col_num)].width = 15
            elif len(column_title) > 40:
                worksheet.column_dimensions[get_column_letter(col_num)].width = 35
            else:
                worksheet.column_dimensions[get_column_letter(col_num)].width = max(len(column_title) + 2, 15)

        # Formater les colonnes de dates en texte (pour préserver le format YYYY-MM-DD)
        date_cols = ['DATE DE FIN CONTRACTUELLE(PIP)', 'DATE DE FIN REELLE']
        for col_name in date_cols:
            if col_name in df.columns:
                col_idx = df.columns.get_loc(col_name) + 1
                for row_idx in range(2, worksheet.max_row + 1):
                    cell = worksheet.cell(row=row_idx, column=col_idx)
                    cell.number_format = '@'  # Format texte
        
        # Formater les cellules de données
        for row in worksheet.iter_rows(min_row=2, max_row=worksheet.max_row, min_col=1, max_col=worksheet.max_column):
            for idx, cell in enumerate(row):
                cell.border = thin_border
                
                # Alignement selon le type de données
                column_name = df.columns[idx]
                if 'MONTANT' in column_name or 'Rétention' in column_name or 'NOTE' in column_name or 'JOURS' in column_name:
                    cell.alignment = alignment_right
                    if 'MONTANT' in column_name or 'Rétention' in column_name:
                        cell.number_format = '#,##0.00'
                    elif 'NOTE' in column_name:
                        cell.number_format = '0.00'
                elif any(x in column_name for x in ['Conformité', 'Délai', 'Capacité', 'Qualité', 'Contact']):
                    cell.alignment = alignment_center
                elif 'DATE' in column_name:
                    cell.alignment = alignment_center
                else:
                    cell.alignment = alignment_left
    
    # Préparer la réponse HTTP
    output.seek(0)
    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    filename = f"Vendor_Evaluations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response


@login_required
def export_vendor_ranking(request):
    """
    Export Excel optimisé pour le Vendor Ranking
    Une ligne par PO unique avec toutes les informations demandées
    """
    try:
        from .models import VendorEvaluation, NumeroBonCommande, LigneFichier
        from datetime import datetime
        import pandas as pd
        from decimal import Decimal
        from django.http import HttpResponse
        
        # Récupérer TOUS les bons de commande (pas seulement ceux évalués)
        bons_commande = NumeroBonCommande.objects.prefetch_related(
            'fichiers__lignes'
        ).all()
        
        if not bons_commande.exists():
            messages.warning(request, "Aucun bon de commande disponible pour l'export.")
            return redirect('orders:vendor_ranking')
        
        # Créer un dictionnaire des évaluations par bon de commande
        evaluations_dict = {}
        evaluations = VendorEvaluation.objects.select_related('bon_commande', 'evaluator').all()
        for evaluation in evaluations:
            evaluations_dict[evaluation.bon_commande.numero] = evaluation
        
        # Fonction helper pour trouver la clé "Order" dans le contenu
        def find_order_key(contenu: dict):
            # 1) Cas exact 'Order'
            if 'Order' in contenu:
                return 'Order'
            # 2) Recherche tolérante (espaces/underscores/accents)
            for k in contenu.keys():
                if not k:
                    continue
                norm = ' '.join(str(k).strip().lower().replace('_', ' ').split())
                if 'order' in norm or 'commande' in norm or 'bon' in norm or norm == 'bc':
                    return k
            return None
        
        # Fonction helper pour récupérer une valeur avec normalisation tolérante
        def get_value_tolerant(contenu: dict, exact_candidates=None, tokens=None):
            if not contenu:
                return None
            def norm(s: str):
                return ' '.join(str(s).strip().lower().replace('_', ' ').replace('-', ' ').split())
            normalized = {norm(k): (k, v) for k, v in contenu.items() if k}
            
            if exact_candidates:
                for cand in exact_candidates:
                    nk = norm(cand)
                    if nk in normalized:
                        return normalized[nk][1]
            
            if tokens:
                needed = [norm(t) for t in tokens]
                for nk, (_ok, v) in normalized.items():
                    if all(t in nk for t in needed):
                        return v
            return None
        
        # Étape 1: Créer un cache pour les premières occurrences de chaque bon de commande en une seule passe globale
        orders_needed = {bon.numero for bon in bons_commande}
        
        # Lister tous les fichiers associés, triés par date d'importation (du plus ancien au plus récent)
        all_files = []
        for bon in bons_commande:
            for fichier in bon.fichiers.all():
                if fichier not in all_files:
                    all_files.append(fichier)
        all_files.sort(key=lambda f: f.date_importation)
        
        # Construire le cache des premières occurrences
        first_occurrence_cache = {}
        for fichier in all_files:
            lignes = list(fichier.lignes.all())
            lignes.sort(key=lambda l: l.numero_ligne)
            for ligne in lignes:
                contenu = ligne.contenu or {}
                order_key = find_order_key(contenu)
                if not order_key:
                    continue
                order_val = str(contenu.get(order_key, '')).strip()
                if not order_val:
                    continue
                # Ajouter au cache seulement si pas encore présent (première occurrence)
                if order_val in orders_needed and order_val not in first_occurrence_cache:
                    first_occurrence_cache[order_val] = contenu
                    # Early break: si on a trouvé toutes les commandes, arrêter
                    if len(first_occurrence_cache) == len(orders_needed):
                        break
            # Early break au niveau fichier aussi
            if len(first_occurrence_cache) == len(orders_needed):
                break
        
        # Étape 2: Construire les données pour TOUS les bons de commande
        data = []
        
        for bon in bons_commande:
            # Récupérer l'évaluation si elle existe
            evaluation = evaluations_dict.get(bon.numero)
            supplier = evaluation.supplier if evaluation else 'N/A'
            
            # Récupérer la première occurrence de ce bon de commande
            premiere_occurrence = first_occurrence_cache.get(bon.numero)
            
            if premiere_occurrence:
                # Extraire les informations
                order_status = get_value_tolerant(premiere_occurrence,
                    exact_candidates=['Order Status', 'Status', 'Statut'],
                    tokens=['order', 'status']) or 'N/A'
                
                # Utiliser .get() direct pour Closed Date (comme dans le fichier)
                closed_date = premiere_occurrence.get('Closed Date') or ''
                
                project_manager = get_value_tolerant(premiere_occurrence,
                    exact_candidates=['Project Manager', 'PM', 'Manager'],
                    tokens=['project', 'manager']) or 'N/A'
                
                buyer = get_value_tolerant(premiere_occurrence,
                    exact_candidates=['Buyer', 'Acheteur', 'Purchaser'],
                    tokens=['buyer']) or 'N/A'
                
                order_description = get_value_tolerant(premiere_occurrence,
                    exact_candidates=['Order Description', 'Item Description', 'Description'],
                    tokens=['order', 'description']) or 'N/A'
                
                # Utiliser .get() direct pour Currency et Conversion Rate (comme export_po_progress)
                currency = premiere_occurrence.get('Currency') or 'XOF'
                
                # Utiliser bon.montant_total() comme dans export_po_progress
                po_amount_value = float(bon.montant_total()) if callable(getattr(bon, 'montant_total', None)) else 0.0
                
                # Calculer le montant en XOF (exactement comme dans export_po_progress)
                if currency == 'XOF':
                    exchange_rate = 1.0
                else:
                    # Récupérer le taux de conversion de la première occurrence
                    exchange_rate_str = premiere_occurrence.get('Conversion Rate')
                    try:
                        exchange_rate = float(exchange_rate_str) if exchange_rate_str else 1.0
                    except (TypeError, ValueError):
                        exchange_rate = 1.0
                
                po_amount_xof = po_amount_value * exchange_rate
            else:
                order_status = 'N/A'
                close_date = ''
                project_manager = 'N/A'
                buyer = 'N/A'
                order_description = 'N/A'
                currency = 'XOF'
                po_amount_value = 0
                po_amount_xof = 0
            
            # Construire la ligne de données
            row = {
                'Purchase Order': bon.numero,
                'Statut PO': str(order_status),
                'Date de fermeture PO': str(closed_date),
                'Demandeur': str(project_manager),
                'Acheteur': str(buyer),
                'Description de la commande': str(order_description),
                'Devise': str(currency),
                'Montant en devise': float(po_amount_value),
                'Montant en XOF': float(po_amount_xof),
                'Conformité de la commande (quantité & qualité)': evaluation.delivery_compliance if evaluation else 0,
                'Délai de livraison, implémentation, exécution': evaluation.delivery_timeline if evaluation else 0,
                'Capacité à conseiller (transfert de compétence, formation, autonomie du client)': evaluation.advising_capability if evaluation else 0,
                'Qualité du SAV': evaluation.after_sales_qos if evaluation else 0,
                'Contact relationnel': evaluation.vendor_relationship if evaluation else 0,
                'Moyenne évaluation demandeur': float(evaluation.vendor_final_rating) if evaluation else 0,
                'Observation': '',  # Colonne vide pour observations manuelles
            }
            
            data.append(row)
        
        # Créer le DataFrame
        df = pd.DataFrame(data)
        
        # Remplacer les valeurs vides
        df['Date de fermeture PO'] = df['Date de fermeture PO'].fillna('')
        
        # Créer la réponse HTTP avec le fichier Excel
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        response['Content-Disposition'] = f'attachment; filename="vendor_ranking_export_{timestamp}.xlsx"'
        
        # Écrire le DataFrame dans le fichier Excel
        with pd.ExcelWriter(response, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Vendor Ranking')
            
            # Formater le fichier Excel
            from openpyxl.utils import get_column_letter
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
            
            workbook = writer.book
            worksheet = writer.sheets['Vendor Ranking']
            
            # Styles (couleurs MTN: Noir et Jaune)
            header_font = Font(bold=True, color="000000", size=11)
            header_fill = PatternFill(start_color="FFCC00", end_color="FFCC00", fill_type="solid")
            alignment_center = Alignment(horizontal="center", vertical="center", wrap_text=True)
            alignment_left = Alignment(horizontal="left", vertical="center")
            alignment_right = Alignment(horizontal="right", vertical="center")
            thin_border = Border(
                left=Side(style='thin'),
                right=Side(style='thin'),
                top=Side(style='thin'),
                bottom=Side(style='thin')
            )
            
            # Appliquer le style aux en-têtes
            for col_idx, col_name in enumerate(df.columns, 1):
                cell = worksheet.cell(row=1, column=col_idx)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = alignment_center
                cell.border = thin_border
            
            # Appliquer les styles et bordures aux cellules de données
            for row_idx in range(2, len(df) + 2):
                for col_idx, col_name in enumerate(df.columns, 1):
                    cell = worksheet.cell(row=row_idx, column=col_idx)
                    cell.border = thin_border
                    
                    # Alignement selon le type de colonne
                    if col_name in ['Purchase Order', 'Statut PO', 'Demandeur', 
                                    'Acheteur', 'Description de la commande', 'Devise', 'Observation']:
                        cell.alignment = alignment_left
                    elif col_name in ['Montant en devise', 'Montant en XOF',
                                      'Conformité de la commande (quantité & qualité)',
                                      'Délai de livraison, implémentation, exécution',
                                      'Capacité à conseiller (transfert de compétence, formation, autonomie du client)',
                                      'Qualité du SAV', 'Contact relationnel', 'Moyenne évaluation demandeur']:
                        cell.alignment = alignment_right
                    else:
                        cell.alignment = alignment_center
            
            # Ajuster la largeur des colonnes
            for idx, col in enumerate(df.columns, 1):
                max_length = max(
                    df[col].astype(str).apply(len).max(),
                    len(col)
                ) + 2
                column_letter = get_column_letter(idx)
                worksheet.column_dimensions[column_letter].width = min(max_length, 50)
        
        return response
        
    except Exception as e:
        logger.error(f"Erreur lors de l'export Vendor Ranking: {str(e)}")
        messages.error(request, f"Erreur lors de l'export: {str(e)}")
        return redirect('orders:vendor_ranking')


@login_required
def export_fichier_complet(request, fichier_id):
    """
    Exporte toutes les données d'un fichier importé en Excel avec les données mises à jour des réceptions.
    Cette fonction réutilise la logique de fusion des données de export_bon_excel mais sans filtrer par numéro de commande.
    """
    from .models import FichierImporte, Reception
    
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
def export_bon_excel(request, bon_id):
    """
    Exporte les données d'un bon de commande en Excel avec les données mises à jour des réceptions.
    Cette fonction réutilise la logique de fusion des données de details_bon.
    """
    from .models import NumeroBonCommande, FichierImporte, Reception
    
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
        currency = 'N/A'
        
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
                
                # Récupérer la devise depuis le bon de commande
                currency = bon_commande.get_currency() if callable(getattr(bon_commande, 'get_currency', None)) else 'N/A'
                    
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
            
            # Trier les en-têtes par ordre alphabétique
            headers = sorted(list(all_keys))
            
            # Debug: afficher les headers disponibles
            print(f"[DEBUG export_bon_excel] Headers disponibles ({len(headers)}): {headers}")
            
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
                'Information': ['Devise', 'Montant Total', 'Montant Total Reçu', 'Taux d\'Avancement'],
                'Valeur': [
                    currency,
                    f"{montant_total:,.2f}",
                    f"{montant_recu:,.2f}",
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

