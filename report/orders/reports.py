"""
Génération des rapports MSRN (Material Service Receipt Note) en PDF.

Ce module formate et compose un PDF en une page pour un bon de commande,
incluant l'en-tête, les validations financières, les informations de paiement,
les signatures et le récapitulatif des lignes. Utilise ReportLab.
"""
 
import logging
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Image, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.lib.styles import getSampleStyleSheet
from io import BytesIO
from django.core.files import File
from django.conf import settings
import os
from .utils import generate_report_number

logger = logging.getLogger(__name__)
from datetime import datetime
from decimal import Decimal
# Safety alias to avoid any accidental local shadowing
from decimal import Decimal as _D

# Couleur bleue moderne
MODERN_BLUE = colors.HexColor('#1F5C99')  # Bleu foncé professionnel
ACCENT_BLUE = colors.HexColor('#4A90E2')  # Bleu plus clair pour accents
LIGHT_BLUE = colors.HexColor('#E6F0FA')   # Bleu très clair pour fonds

def generate_msrn_report(bon_commande, report_number=None, msrn_report=None, user_email=None):
    """
    Génère un rapport MSRN (Material Service Receipt Note) au format PDF.
    Optimisé pour tenir sur une seule page avec toutes les informations.
    
    Args:
        bon_commande: Instance du bon de commande
        report_number: Numéro de rapport à utiliser pour le PDF
        request: Objet HttpRequest optionnel pour récupérer les paramètres de rétention
    """
    buffer = BytesIO()
    # Marges réduites pour maximiser l'espace disponible
    doc = SimpleDocTemplate(buffer, pagesize=letter, 
                          rightMargin=18, leftMargin=18,
                          topMargin=18, bottomMargin=18)
    elements = []
    
    # Création des styles avec Times New Roman
    styles = getSampleStyleSheet()
    
    # Styles optimisés pour une seule page - tailles réduites mais lisibles
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Title'],
        fontName='Times-Bold',
        fontSize=11,  # Réduit mais lisible
        alignment=1,
        spaceAfter=3,
        textColor=colors.white
    )
    
    subtitle_style = ParagraphStyle(
        'SubtitleStyle',
        parent=styles['Heading2'],
        fontName='Times-Roman',
        fontSize=8,  # Réduit mais lisible
        alignment=1,
        spaceAfter=6,
        textColor=colors.white
    )
    
    heading_style = ParagraphStyle(
        'HeadingStyle',
        parent=styles['Heading2'],
        fontName='Times-Bold',
        fontSize=9,  # Réduit mais lisible
        alignment=0,
        spaceAfter=3,
        textColor=MODERN_BLUE
    )
    
    # Style spécifique pour les titres de tableaux (noir)
    table_title_style = ParagraphStyle(
        'TableTitleStyle',
        parent=styles['Heading2'],
        fontName='Times-Bold',
        fontSize=7,
        alignment=1,  # Centré
        spaceAfter=0,
        spaceBefore=0,
        leading=6,  # Réduire l'interligne
        textColor=colors.black  # Noir
    )
    
    normal_style = ParagraphStyle(
        'NormalStyle',
        parent=styles['Normal'],
        fontName='Times-Roman',
        fontSize=7,  # Réduit mais lisible
        leading=8
    )
    
    # Fonctions utilitaires de formatage
    def fmt_amount(v, decimals=2):
        """Montants: séparateur de milliers espace, nombre de décimales spécifié."""
        try:
            return f"{v:,.{decimals}f}".replace(",", " ").replace(".", ",")
        except Exception:
            try:
                return f"{float(v):,.{decimals}f}".replace(",", " ").replace(".", ",")
            except Exception:
                return str(v)
    
    def fmt_rate(v, decimals=2):
        """Taux: virgule comme séparateur décimal."""
        try:
            return ("{0:." + str(decimals) + "f}").format(float(v)).replace(".", ",")
        except Exception:
            return str(v)
    
    # Récupérer le fournisseur, la devise et le numéro de projet
    supplier = bon_commande.get_supplier()
    currency = bon_commande.get_currency()
    project_number = bon_commande.get_project_number()
    
    # Chemin vers le logo
    logo_path = os.path.join(settings.BASE_DIR, 'static', 'logo_mtn.jpeg')
    
    # ===================== EN-TÊTE AMÉLIORÉ =====================
    current_date = datetime.now().strftime("%d/%m/%Y")
    
    # Logo agrandi mais toujours compact
    logo = Image(logo_path, width=70, height=28)
    
    # Créer un style spécifique pour les en-têtes centrés
    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Normal'],
        fontName='Times-Bold',
        fontSize=7,
        alignment=TA_CENTER,
        textColor=colors.black,
        leading=8,
        spaceBefore=0,
        spaceAfter=0
    )
    
    # Extraire le texte brut des en-têtes existants
    def extract_text(para):
        if hasattr(para, 'text'):
            return para.text
        return str(para)
    
    # Recréer les en-têtes avec le nouveau style
    headers = [
        Paragraph("Enterprise Portfolio Management Office(EPMO)", header_style),
        Paragraph(f"{current_date}", header_style)
    ]
    
    # 2. Cadre EPMO ultra-compact
    center_small_style = ParagraphStyle(
        'CenterSmall',
        parent=styles['Normal'],
        alignment=1,  # Centré
        fontName='Times-Roman',
        fontSize=7,
    )
    epmo_data = [
        [headers[0]],
        [headers[1]]
    ]
    
    epmo_table = Table(epmo_data, colWidths=[115])  # Largeur réduite
    epmo_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, MODERN_BLUE),  # Bordure très fine
        ('BACKGROUND', (0, 0), (-1, -1), LIGHT_BLUE),
        ('PADDING', (0, 0), (-1, -1), 3),  # Padding très réduit
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, -1), 'Times-Roman'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),  # Police réduite
        ('GRID', (0, 0), (-1, -1), 0.25, MODERN_BLUE),  # Grille très fine
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
    ]))
    
    # Tableau d'en-tête ultra-compact
    header_data = [[logo, '', epmo_table]]
    header_table = Table(header_data, colWidths=[60, 380, 100])  # Colonnes réduites
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),    # Aligner le logo à gauche
        ('ALIGN', (2, 0), (2, 0), 'RIGHT'),   # Aligner EPMO à droite
    ]))
    elements.append(header_table)
    
    # Espace minimal
    elements.append(Spacer(1, 3))
    
    # 3. Titre ultra-compact
    title_content = Table([
        [Paragraph("MSRN - MATERIAL & SERVICE RECEIPT NOTE", title_style)],
        [Paragraph("<b>CAPEX Works Valuation Protocol / Protocole de Facturation</b>", ParagraphStyle(
            'SubtitleStyle',
            parent=styles['Heading3'],
            fontName='Times-Bold',
            fontSize=6,
            alignment=1,
            spaceBefore=0,
            spaceAfter=0,
            textColor=colors.black
        ))]
    ], colWidths=[300])  # Deux lignes, largeur réduite
    
    title_content.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), MODERN_BLUE),
        ('BACKGROUND', (0, 1), (-1, 1), colors.lightgrey),
        ('BOX', (0, 0), (-1, -1), 0.5, MODERN_BLUE),  # Bordure très fine
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 3),  # Padding très réduit
    ]))
    
    # Positionner le titre au centre - compact
    title_position = Table([[title_content]], colWidths=[540])
    title_position.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(title_position)
    elements.append(Spacer(1, 3))  # Espace minimal
    # ===================== FIN EN-TÊTE =====================
    
    # Texte de confirmation ultra-condensé
    confirmation_text = [
        Paragraph(
            f"This Certificate confirms that <b>{supplier}</b> provides MTN-CI with necessary job/material according to specifications.<br/>Ce certificat atteste que <b>{supplier}</b> a livré conformément aux spécifications:",
            normal_style
        ),
        Spacer(1, 3)  # Espace minimal
    ]
    elements.extend(confirmation_text)
    
    # 5. DETAILS OF ACCEPTANCE - Nouveau style avec bleu
    # Titre intégré directement dans le tableau
    
    # Définir les valeurs à utiliser dans le tableau ACCEPTANCE
    # Utiliser les snapshots du rapport MSRN si disponibles
    if msrn_report and msrn_report.montant_total_snapshot is not None:
        po_amount = msrn_report.montant_total_snapshot
    else:
        po_amount = bon_commande.montant_total()
        
    if msrn_report and msrn_report.progress_rate_snapshot is not None:
        progress_rate = msrn_report.progress_rate_snapshot
    else:
        progress_rate = bon_commande.taux_avancement()
    
    acceptance_data = [
        [Paragraph("<b> DETAILS OF ACCEPTANCE</b>", table_title_style), ""],  # Titre fusionné et centré
          # En-tête
        ["CERTIFICATE NUMBER", report_number],
        ["PURCHASE ORDER REFERENCE/NUMERO BC", bon_commande.numero],
        ["PROJECT ID/CODE PROJECT", project_number],
        ["SUPPLIER/FORNISSEUR", supplier],
        ["CURRENCY/DEVISE", currency],
        ["PO AMOUNT/MONTANT BC", f"{fmt_amount(po_amount)} {currency}"],
        ["DELIVERY RATE/TAUX LIVRAISON", f"{fmt_rate(progress_rate, 2)}%"],
    ]
    
    # Largeur fixe pour tous les tableaux - augmentée pour utiliser plus d'espace
    TABLE_WIDTH = 583
    acceptance_table = Table(acceptance_data, colWidths=[TABLE_WIDTH/2, TABLE_WIDTH/2])  # Largeur optimisée
    # Style de tableau compact mais complet
    acceptance_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),  # Centrer le titre
        ('ALIGN', (1, 2), (1, -1), 'LEFT'),  # Centrer les montants (colonne 2)
        ('ALIGN', (0, 2), (0, -1), 'LEFT'),    # Garder les descriptions alignées à gauche
        ('ALIGN', (2, 2), (2, -1), 'LEFT'),  
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 1), (-1, 1), 'Times-Bold'),
        ('FONTSIZE', (0, 1), (-1, -1), 7),  # Police réduite
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),  # Padding réduit
        ('TOPPADDING', (0, 0), (-1, -1), 1),
        ('LEFTPADDING', (0, 0), (-1, -1), 1),
        ('RIGHTPADDING', (0, 0), (-1, -1), 1),
        
        # Fusion des cellules pour le titre
        ('SPAN', (0, 0), (1, 0)),
        ('BACKGROUND', (0, 0), (1, 0), colors.yellow),
        ('TEXTCOLOR', (0, 0), (1, 0), colors.black),
        ('FONTSIZE', (0, 0), (1, 0), 9),
        
        # Bordures très fines
        ('BOX', (0, 0), (-1, -1), 0.5, colors.black),  # Bordure très fine
        ('LINEBELOW', (0, 1), (-1, 1), 0.5, colors.black),  # Ligne très fine
        ('GRID', (0, 1), (-1, -1), 0.25, colors.black),  # Grille très fine
        
        # Couleurs maintenues
        ('BACKGROUND', (0, 1), (-1, 1), LIGHT_BLUE),
        ('TEXTCOLOR', (0, 1), (-1, 1), colors.black),
        ('BACKGROUND', (0, 2), (0, -1), LIGHT_BLUE),
        ('BACKGROUND', (1, 2), (1, -1), colors.white),
        
        # Alternance de couleurs pour les lignes
        ('BACKGROUND', (0, 3), (-1, 3), colors.whitesmoke),
        ('BACKGROUND', (0, 5), (-1, 5), colors.whitesmoke),
    ]))
    elements.append(acceptance_table)
    elements.append(Spacer(1, 3))  # Espace minimal
    
    order_desc = bon_commande.get_order_description() if hasattr(bon_commande, 'get_order_description') else None
    if order_desc and str(order_desc).strip() and str(order_desc).strip().upper() != 'N/A':
        order_desc_style = ParagraphStyle(
            'OrderDescStyle',
            parent=styles['Normal'],
            fontName='Times-Bold',
            fontSize=6,
            alignment=1,  # Centré
            textColor=colors.black
        )
        elements.append(Paragraph(str(order_desc), order_desc_style))
        elements.append(Spacer(1, 2))

    # 6. FINANCIAL VALIDATION - Style amélioré avec bleu
    # Titre intégré directement dans le tableau
    
    # Récupérer les valeurs initiales depuis InitialReceptionBusiness (agrégation par bon)
    montant_recu_initial = _D('0')
    taux_avancement_initial = _D('0')
    try:
        from .models import InitialReceptionBusiness
        from django.db.models import Sum
        # Optimisation: Utiliser l'agrégation SQL au lieu de Python
        aggregates = InitialReceptionBusiness.objects.filter(
            bon_commande=bon_commande
        ).aggregate(
            total_recu=Sum('montant_recu_initial'),
            total_montant=Sum('montant_total_initial')
        )
        montant_recu_initial = aggregates['total_recu'] or _D('0')
        montant_total_initial = aggregates['total_montant'] or _D('0')
        if montant_total_initial > 0:
            taux_avancement_initial = (montant_recu_initial / montant_total_initial) * _D('100')
        else:
            taux_avancement_initial = _D('0')
    except Exception as e:
        print(f"Erreur lors de la récupération des valeurs initiales (InitialReceptionBusiness): {str(e)}")
    
    # Calcul du solde à réceptionner (différence entre montant reçu actuel et initial)
    # Utiliser les snapshots du rapport MSRN si disponibles
    if msrn_report and msrn_report.montant_recu_snapshot is not None:
        montant_recu_actuel = msrn_report.montant_recu_snapshot
        taux_avancement_actuel = msrn_report.progress_rate_snapshot if msrn_report.progress_rate_snapshot is not None else bon_commande.taux_avancement()
    else:
        montant_recu_actuel = bon_commande.montant_recu()
        taux_avancement_actuel = bon_commande.taux_avancement()
    
    solde_a_receptionner = montant_recu_actuel - montant_recu_initial
    
    # Différence entre taux d'avancement actuel et initial
    difference_taux = taux_avancement_actuel - taux_avancement_initial
    
    # Utiliser le snapshot du montant total si disponible
    if msrn_report and msrn_report.montant_total_snapshot is not None:
        montant_total = msrn_report.montant_total_snapshot
    else:
        montant_total = bon_commande.montant_total()
        
    financial_data = [
        [Paragraph("<b> FINANCIAL VALUATION</b>", table_title_style), "", "", ""],  # Titre fusionné et centré
        ["DESCRIPTION", "AMOUNT/MONTANT", "PERCENTAGE (%)", "COMMENTS/OBSERVATIONS"],  # Nouvel en-tête avec 4 colonnes
        ["ACTUAL DELIVERED AMOUNT / MONTANT TOTAL LIVRE", f"{fmt_amount(montant_recu_actuel)}", f"{fmt_rate(taux_avancement_actuel, 2)}%", ""],
        ["AMOUNT RECEIVED IN FUSION ", f"{fmt_amount(montant_recu_initial)}", f"{fmt_rate(taux_avancement_initial, 2)}%", ""],
        ["BALANCE TO BE CERTIFIED / SOLDE A RECEPTIONNER", f"{fmt_amount(solde_a_receptionner)}", f"{fmt_rate(difference_taux, 2)}%", ""],
        ["NOT DELIVERED AMOUNT/SOLDE NON LIVRÉ", f"{fmt_amount(montant_total - montant_recu_actuel)}", "", ""]
    ]
    
    financial_table = Table(financial_data, colWidths=[TABLE_WIDTH*0.35, TABLE_WIDTH*0.25, TABLE_WIDTH*0.15, TABLE_WIDTH*0.25])  # Largeur ajustée pour 4 colonnes
    financial_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),  # Centrer le titre
        ('ALIGN', (0, 1), (-1, 1), 'CENTER'),  # Centrer les en-têtes
        ('ALIGN', (1, 2), (1, -1), 'CENTER'),  # Centrer les montants (colonne 2)
        ('ALIGN', (2, 2), (2, -1), 'CENTER'),  # Centrer les pourcentages (colonne 3)
        ('ALIGN', (0, 2), (0, -1), 'LEFT'),    # Garder les descriptions alignées à gauche
        ('ALIGN', (3, 2), (3, -1), 'CENTER'),  # Centrer les commentaires (colonne 4)
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 1), (-1, 1), 'Times-Bold'),
        ('FONTSIZE', (0, 1), (-1, -1), 6.8),  # Police réduite
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),  # Padding réduit
        ('TOPPADDING', (0, 0), (-1, -1), 1),
        ('LEFTPADDING', (0, 0), (-1, -1), 1),
        ('RIGHTPADDING', (0, 0), (-1, -1), 1),
        
        # Fusion des cellules pour le titre
        ('SPAN', (0, 0), (3, 0)),
        ('BACKGROUND', (0, 0), (3, 0), colors.yellow),
        ('TEXTCOLOR', (0, 0), (3, 0), colors.black),
        ('FONTSIZE', (0, 0), (3, 0), 7),
        
        # Bordures très fines
        ('BOX', (0, 0), (-1, -1), 0.5, colors.black),  # Bordure très fine
        ('LINEBELOW', (0, 1), (-1, 1), 0.5, colors.black),  # Ligne très fine
        ('GRID', (0, 1), (-1, -1), 0.25, colors.black),  # Grille très fine
        
        # Couleurs maintenues
        ('BACKGROUND', (0, 1), (-1, 1), LIGHT_BLUE),
        ('TEXTCOLOR', (0, 1), (-1, 1), colors.black),
        ('BACKGROUND', (0, 2), (-1, 2), colors.white),
        ('BACKGROUND', (0, 3), (-1, 3), colors.whitesmoke),
        
        # Dernière ligne en gras avec couleur spéciale
        ('FONTNAME', (0, -1), (-1, -1), 'Times-Bold'),
        ('BACKGROUND', (0, -1), (-1, -1), LIGHT_BLUE),
    ]))
    elements.append(financial_table)
    elements.append(Spacer(1, 3))  # Espace minimal
    
    # 7. PAYMENT / PAIEMENT - Utiliser les valeurs du rapport MSRN si disponibles, sinon celles du bon de commande
    if msrn_report and msrn_report.retention_rate is not None:
        retention_rate = msrn_report.retention_rate
        retention_cause = msrn_report.retention_cause or ''
    else:
        retention_rate = bon_commande.retention_rate or _D('0')
        retention_cause = bon_commande.retention_cause or ''

    # Utiliser les snapshots du rapport MSRN pour les montants
    if msrn_report and msrn_report.montant_total_snapshot is not None:
        montant_total = msrn_report.montant_total_snapshot
        montant_recu_actuel = msrn_report.montant_recu_snapshot or Decimal('0')
    else:
        # Fallback sur les valeurs actuelles si pas de snapshot
        montant_total = bon_commande.montant_total() or _D('0')
        montant_recu_actuel = bon_commande.montant_recu() or _D('0')
    
    # OPTIMISATION: Utiliser le snapshot si disponible, sinon récupérer depuis LigneFichier
    if msrn_report and msrn_report.payment_terms_snapshot:
        payment_terms = msrn_report.payment_terms_snapshot
    else:
        payment_terms = "N/A"
        try:
            from .models import Reception, LigneFichier
            # OPTIMISATION: Récupérer Payment Terms en une seule requête optimisée
            
            # Récupérer une réception avec son business_id (une seule requête)
            reception = Reception.objects.filter(
                bon_commande=bon_commande
            ).only('business_id').first()
            
            if reception and reception.business_id:
                # Chercher la ligne correspondante via business_id (une seule requête)
                ligne = LigneFichier.objects.filter(
                    business_id=reception.business_id
                ).only('contenu').first()
                
                if ligne and ligne.contenu:
                    contenu = ligne.contenu
                    # Chercher 'Payment Terms' avec ou sans espace à la fin
                    payment_key = None
                    if 'Payment Terms ' in contenu:  # Avec espace (clé réelle dans les données)
                        payment_key = 'Payment Terms '
                    elif 'Payment Terms' in contenu:  # Sans espace (fallback)
                        payment_key = 'Payment Terms'
                    
                    if payment_key and contenu[payment_key]:
                        val = str(contenu[payment_key]).strip()
                        if val and val.lower() not in ['n/a', 'na', '', 'none']:
                            payment_terms = val
        except Exception as e:
            logger.warning(f"Erreur lors de la récupération des Payment Terms: {e}")
    
    retention_amount = (montant_total * retention_rate / _D('100')).quantize(_D('0.01'))
    payable_amount = (montant_recu_actuel - retention_amount).quantize(_D('0.01'))
    taux_payable = (payable_amount / montant_total * _D('100')).quantize(_D('0.01')) if montant_total != 0 else _D('0')
    
    payment_data = [
    [Paragraph("<b>PAYMENT / PAIEMENT</b>", table_title_style), "", "", ""],
    ["DESCRIPTION", "Amount/Montant","Percentage (%)","Comments/Observations"],
    ["TOTAL PAYABLE AMOUNT / MONTANT TOTAL PAYABLE", f"{fmt_amount(payable_amount)}",f"{fmt_rate(taux_payable, 2)}%", payment_terms],
    ["RETENTION AMOUNT / RETENUE SUR PAIEMENT *", f"{fmt_amount(retention_amount)}",f"{fmt_rate(retention_rate, 2)}%", ""],
    ["RETENTION CAUSE / CAUSE DE LA RETENUE", f"{retention_cause}", "", ""]
]
    
    # Style de base pour le tableau de paiement
    payment_table = Table(payment_data, 
                         colWidths=[TABLE_WIDTH*0.35, TABLE_WIDTH*0.25, TABLE_WIDTH*0.15, TABLE_WIDTH*0.25],  # 4 colonnes ajustées
                         rowHeights=[15, 15, 15, 15, 15])  # Hauteur réduite
    payment_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),  # Centrer le titre
        ('ALIGN', (0, 1), (-1, 1), 'CENTER'),  # Centrer les en-têtes
        ('ALIGN', (1, 2), (1, 3), 'CENTER'),  # Centrer les montants (colonne 2)
        ('ALIGN', (2, 2), (2, 3), 'CENTER'),  # Centrer les pourcentages (colonne 3)
        ('ALIGN', (0, 2), (0, -1), 'LEFT'),    # Garder les descriptions alignées à gauche
        ('ALIGN', (3, 2), (3, -1), 'CENTER'),  # Centrer les commentaires (colonne 4)
        ('ALIGN', (1, 4), (1, 4), 'LEFT'),     # Aligner la cause à gauche (ligne 4)
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),   # Alignement en haut pour la cause
        ('BOX', (0, 0), (-1, -1), 0.5, colors.black),  # Bordure autour du tableau
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.black),  # Lignes de grille
        ('FONTSIZE', (0, 0), (-1, -1), 8),     # Taille de police réduite
        ('LEADING', (0, 0), (-1, -1), 10),     # Interligne
        ('TOPPADDING', (0, 0), (-1, -1), 2),   # Espacement supérieur réduit
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2), # Espacement inférieur réduit
        ('FONTNAME', (0, 1), (-1, 1), 'Times-Bold'),
        ('FONTSIZE', (0, 1), (-1, -1), 7),  # Police réduite
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),  # Padding réduit
        ('TOPPADDING', (0, 0), (-1, -1), 1),
        ('LEFTPADDING', (0, 0), (-1, -1), 1),
        ('RIGHTPADDING', (0, 0), (-1, -1), 1),
        
        # Fusion des cellules pour le titre
        ('SPAN', (0, 0), (3, 0)),
        ('BACKGROUND', (0, 0), (3, 0), colors.yellow),
        ('TEXTCOLOR', (0, 0), (3, 0), colors.black),
        ('FONTSIZE', (0, 0), (3, 0), 9),
        
        # Fusion des cellules pour RETENTION CAUSE entre Amount, Percentage et Comments
        ('SPAN', (1, 4), (3, 4)),
        
        # Bordures très fines
        ('BOX', (0, 0), (-1, -1), 0.5, colors.black),  # Bordure très fine
        ('LINEBELOW', (0, 1), (-1, 1), 0.5, colors.black),  # Ligne très fine
        ('GRID', (0, 1), (-1, -1), 0.25, colors.black),  # Grille très fine pour toutes les lignes
        
        # Couleurs maintenues
        ('BACKGROUND', (0, 1), (-1, 1), LIGHT_BLUE),
        ('TEXTCOLOR', (0, 1), (-1, 1), colors.black),
        ('BACKGROUND', (0, 2), (-1, 2), colors.white),
        ('BACKGROUND', (0, 3), (-1, 3), colors.whitesmoke),
    ]))
    elements.append(payment_table)
    elements.append(Spacer(1, 3))  # Espace minimal
    
    # 8. SIGN OFF/SIGNATURE - Tableau conditionnel basé sur CPU
    # Récupérer la valeur CPU et les noms des rôles
    # Utiliser le bon de commande uniquement si aucun rapport MSRN n'est fourni
    # Note: Nous utilisons le bon de commande car les noms des personnes ne sont pas stockés dans des snapshots
    # Cela pourrait être amélioré en ajoutant des champs de snapshot pour ces noms dans le modèle MSRNReport
    cpu_value = bon_commande.get_cpu()
    
    # Définir les colonnes et noms selon la valeur CPU
    if cpu_value == "NWG":
        # 6 colonnes pour NTW
        headers = [
            Paragraph("PROJECT<br/>COORDINATOR", normal_style),
            Paragraph("PROJECT<br/>MANAGER", normal_style),
            Paragraph("SENIOR PM", normal_style),
            Paragraph("GM EPMO", normal_style),
            Paragraph("MANAGER<br/>PORTFOLIO", normal_style),
            Paragraph("VENDOR<br/>(Stamp/Cachet &<br/>Signature)", normal_style)
        ]
        names = [
            bon_commande.get_project_coordinator(),
            bon_commande.get_project_manager(),
            bon_commande.get_senior_pm(),
            bon_commande.get_gm_epmo(),
            bon_commande.get_manager_portfolio(),
            " "
        ]
        num_cols = 6
        col_widths = [TABLE_WIDTH/6] * 6
        
    elif cpu_value == "ITS":
        # 7 colonnes pour ITS
        headers = [
            Paragraph("PROJECT<br/>COORDINATOR", normal_style),
            Paragraph("PROJECT<br/>MANAGER", normal_style),
            Paragraph("SENIOR PM", normal_style),
            Paragraph("GM EPMO", normal_style),
            Paragraph("SENIOR<br/>TECHNICAL LEAD", normal_style),
            Paragraph("MANAGER<br/>PORTFOLIO", normal_style),
            Paragraph("VENDOR<br/>(Stamp/Cachet &<br/>Signature)", normal_style)
        ]
        names = [
            bon_commande.get_project_coordinator(),
            bon_commande.get_project_manager(),
            bon_commande.get_senior_pm(),
            bon_commande.get_gm_epmo(),
            bon_commande.get_manager_portfolio(),
            bon_commande.get_senior_technical_lead(),
            "N/A"
        ]
        num_cols = 7
        col_widths = [TABLE_WIDTH/7] * 7
        
    elif cpu_value == "FAC":
        # 5 colonnes pour FAC
        headers = [
            Paragraph("PROJECT<br/>COORDINATOR", normal_style),
            Paragraph("PROJECT<br/>MANAGER", normal_style),
            Paragraph("MANAGER<br/>PORTFOLIO", normal_style),
            Paragraph("GM EPMO", normal_style),
            Paragraph("VENDOR<br/>(Stamp/Cachet &<br/>Signature)", normal_style)
        ]
        names = [
            bon_commande.get_project_coordinator(),
            bon_commande.get_project_manager(),
            bon_commande.get_manager_portfolio(),
            bon_commande.get_gm_epmo(),
            " "
        ]
        num_cols = 5
        col_widths = [TABLE_WIDTH/5] * 5
        
    else:
        # Tableau par défaut (6 colonnes) si CPU n'est pas reconnu
        headers = [
            Paragraph("PROJECT<br/>COORDINATOR", normal_style),
            Paragraph("PROJECT<br/>MANAGER", normal_style),
            Paragraph("SENIOR PM", normal_style),
            Paragraph("GM EPMO", normal_style),
            Paragraph("MANAGER<br/>PORTFOLIO", normal_style),
            Paragraph("VENDOR<br/>(Stamp/Cachet &<br/>Signature)", normal_style)
        ]
        names = [
            bon_commande.get_project_coordinator(),
            bon_commande.get_project_manager(),
            bon_commande.get_senior_pm(),
            bon_commande.get_gm_epmo(),
            bon_commande.get_manager_portfolio(),
            " "
        ]
        num_cols = 6
        col_widths = [TABLE_WIDTH/6] * 6
    
    # Style pour les en-têtes centrés
    header_style = ParagraphStyle(
        'SignatureHeaderStyle',
        parent=styles['Normal'],
        fontName='Times-Bold',
        fontSize=7,
        alignment=TA_CENTER,
        textColor=colors.black,
        leading=8,
        spaceBefore=0,
        spaceAfter=0
    )
    
    # Recréer les en-têtes avec le style centré
    centered_headers = [
        Paragraph(header.text.replace('<br/>', '<br/>') if hasattr(header, 'text') else str(header).replace('<br/>', '<br/>'), 
                 header_style)
        for header in headers
    ]
    
    # Créer le titre fusionné
    title_row = [Paragraph("<b>SIGN OFF/SIGNATURE</b>", table_title_style)] + [""] * (num_cols - 1)
    
    # Créer la ligne de signature vide
    signature_row = [""] * num_cols
    
    # Construire les données du tableau
    signature_data = [
        title_row,
        centered_headers,
        names,
        signature_row
    ]
    
    # Créer le tableau avec les largeurs appropriées
    signature_table = Table(signature_data, colWidths=col_widths)
    
    # Styles du tableau
    signature_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),  # Centrer le titre
        ('ALIGN', (0, 1), (-1, 1), 'CENTER'),  # Centrer les en-têtes
        ('ALIGN', (0, 2), (-1, 2), 'CENTER'),  # Centrer les noms
        ('ALIGN', (0, 3), (-1, 3), 'CENTER'),  # Centrer la ligne de signature
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 1), (-1, 1), 'Times-Bold'),
        ('FONTSIZE', (0, 1), (-1, -1), 6.8),  # Police ultra-réduite
        ('TOPPADDING', (0, 0), (-1, -1), 1),  # Padding minimal pour les 3 premières lignes
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ('TOPPADDING', (0, 3), (-1, 3), 15),  # Padding augmenté pour la ligne de signature
        ('BOTTOMPADDING', (0, 3), (-1, 3), 15),  # Espace pour les signatures
        
        # Fusion des cellules pour le titre
        ('SPAN', (0, 0), (num_cols-1, 0)),
        ('BACKGROUND', (0, 0), (num_cols-1, 0), colors.yellow),
        ('TEXTCOLOR', (0, 0), (num_cols-1, 0), colors.black),
        ('FONTSIZE', (0, 0), (num_cols-1, 0), 9),
        
        ('GRID', (0, 1), (-1, -1), 0.25, colors.black),  # Grille très fine
        ('BOX', (0, 0), (-1, -1), 0.5, colors.black),  # Bordure très fine
        ('BACKGROUND', (0, 1), (-1, 1), LIGHT_BLUE),
        ('TEXTCOLOR', (0, 1), (-1, 1), colors.black),
        ('BACKGROUND', (0, 2), (-1, 2), colors.white),
        # Pas de couleur de fond pour la ligne de signature
        ('LINEBELOW', (0, 3), (-1, 3), 1, colors.lightgrey),
    ]))
    
    elements.append(signature_table)
    elements.append(Spacer(1, 3))  # Espace minimal
    
    # 8.EXTRAIT DES CONDITIONS GÉNÉRALES - Style amélioré et plus compact
    conditions_style = ParagraphStyle(
        'ConditionsStyle',
        parent=styles['Heading2'],
        fontName='Times-Bold',
        fontSize=7,  # Taille réduite
        textColor=MODERN_BLUE,
        spaceBefore=1,
        spaceAfter=1,
        leading=8
    )
    elements.append(Paragraph("EXTRAIT DES CONDITIONS GENERALES", conditions_style))
    
    # Style pour les titres de section - ultra compact
    section_style = ParagraphStyle(
        'SectionStyle',
        parent=styles['Heading2'],
        fontName='Times-Bold',
        fontSize=8,  # Taille encore plus réduite
        textColor=colors.black,
        backColor=colors.yellow,
        spaceBefore=2,  # Espacement minimal
        spaceAfter=2,
        leftIndent=0.25,
        padding=0.25
    )
    
    # Section 5: Réception et Contrôle des produits
    elements.append(Paragraph("5. Réception et Contrôle des produits", section_style))
    reception_conditions = [
        "Le Fournisseur est responsable de l'état des biens et des risques auxquels ils sont exposés jusqu'à leur réception/acceptation finale par MTN-CI.",
        "Les produits livrés sont soumis à acceptation par MTN Cl. La réception n'est définitive qu'après contrôles quantitatifs et qualitatifs effectués par le service désigné à cet effet. Sauf dispositions spécifique de la commande, le refus des produits livrés notifié par MTN Cl au Fournisseur dans un délai de 15 jours ouvrés, à compter de la livraison. Le Fournisseur procédera aux corrections requises dans un délai de 15 jours, sauf accord exprès de MTN Cl pour un délai plus long.",
        "Le refus de livraison ou la mise en jeu de la clause de garantie pourront intervenir à tout moment, même en l'absence de réserves de la part de MTN Cl lors de la prise en charge des colis. Tout produit non conforme sera retourné aux frais et risques du Fournisseur. Dans le cas d'un retour de produits pour non-conformité, MTN Cl se réserve le droit soit de demander le remplacement ou la retouche desdits produits et cela aux conditions initiales de la commande, soit de déduire des paiements dus au Fournisseur les tarifs justifiés, entrainés par la mise en conformité contractuelle tel que par exemple : frais d'identification et de marquage, transport. Dans le cas où MTN Cl se trouverait dans l'obligation de s'approvisionner auprès d'une autre source pour tout ou partie de la commande, le Fournisseur défaillant supportera de plein-droit, la différence de coût constatée entre la nouvelle commande et celle du Fournisseur défaillant."
    ]
    
    # Style plus compact pour le texte des conditions
    compact_normal_style = ParagraphStyle(
        'CompactNormal',
        parent=styles['Normal'],
        fontName='Times-Roman',
        fontSize=7,  # Taille très réduite
        leading=7,   # Interligne minimal
        spaceBefore=2,  # Augmenté à 2 points
        spaceAfter=0
    )
    
    for condition in reception_conditions:
        elements.append(Paragraph(f"• {condition}", compact_normal_style))
        elements.append(Spacer(1, 0.5))  # Espacement ultra-minimal
    
    # Section 6: Livraison
    elements.append(Paragraph("6. Livraison", section_style))
    livraison_conditions = [
        "Les biens livrés devront être conformes aux spécifications de la commande et/ou de l'offre du Fournisseur et/ou du cahier des charges et/ou de tout document accepté par les Parties. La livraison devra être effectuée selon les conditions de délais fixés sur le bon de commande.",
        "Toute modification du délai de livraison devra faire l'objet d'un accord préalable de MTN Cl. La livraison devra être matérialisée par un bordereau de livraison rappelant la référence et la nature de la commande, dûment validé par la personne désignée par MTN-CI."
    ]
    
    for condition in livraison_conditions:
        elements.append(Paragraph(f"• {condition}", compact_normal_style))
        elements.append(Spacer(1, 0.5))  # Espacement ultra-minimal
    
    # Section 7: Retard de livraison
    elements.append(Paragraph("7. Retard de livraison", section_style))
    retard_condition = "Le délai de livraison étant d'une importance capitale, le Fournisseur reconnaît le droit à MTN-CI, en cas de retard lui incombant, d'annuler irrévocablement la commande aux torts exclusifs du Fournisseur ou d'appliquer des pénalités de retard à raison de 0.3% du prix total de la marchandise, par jour calendaire de retard, sauf cas de force majeure prouvé par le Fournisseur et formellement reconnu par MTN-CI."
    elements.append(Paragraph(f"• {retard_condition}", compact_normal_style))

    # Ajouter l'email de l'utilisateur qui a généré le rapport
    if user_email:
        user_style = ParagraphStyle(
            'UserStyle',
            parent=styles['Normal'],
            fontName='Times-Italic',
            fontSize=7,
            alignment=TA_RIGHT,
            textColor=colors.grey
        )
        user_text = f"Requested By: {user_email}"
        elements.append(Spacer(1, 10))  # Ajouter un espace de 10 points
        elements.append(Paragraph(user_text, user_style))
    
    # ===================== DEUXIÈME PAGE - PURCHASE ORDER LINES =====================
    from reportlab.platypus import PageBreak
    
    # Ajouter un saut de page pour créer une nouvelle page
    elements.append(PageBreak())
    
    # Titre de la deuxième page
    elements.append(Spacer(1, 20))  # Espace en haut de la nouvelle page
    
    # Tableau titre "PURCHASE ORDER LINES" avec fond orange
    po_lines_title_data = [
        [Paragraph("<b>PURCHASE ORDER LINES DELIVERED STATUS</b>", table_title_style)]
    ]
    
    po_lines_title_table = Table(po_lines_title_data, colWidths=[TABLE_WIDTH])
    po_lines_title_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (0, 0), (-1, -1), colors.orange),  # Fond orange
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('FONTNAME', (0, 0), (-1, -1), 'Times-Bold'),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.black),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(po_lines_title_table)
    elements.append(Spacer(1, 10))
    
    # Récupérer les réceptions pour ce bon de commande
    # Utiliser les snapshots du rapport MSRN si disponibles
    if msrn_report and msrn_report.receptions_data_snapshot:
        # Utiliser les données des snapshots
        receptions_data = msrn_report.receptions_data_snapshot
        receptions_with_quantity_delivered = [r for r in receptions_data if float(r.get('quantity_delivered', 0)) > 0]
    else:
        # Optimisation: Fallback sur les données actuelles des réceptions avec prefetch
        from .models import Reception
        all_receptions = Reception.objects.filter(
            bon_commande=bon_commande,
            quantity_delivered__gt=0  # Filtrer directement en SQL
        ).select_related('fichier', 'bon_commande').order_by('business_id')
        
        # CRITIQUE: Pour 50K+ lignes, limiter à 5000 lignes max dans le PDF
        # Les autres lignes seront dans l'export Excel séparé
        MAX_LINES_IN_PDF = 5000
        total_receptions = all_receptions.count()
        receptions_with_quantity_delivered = list(all_receptions[:MAX_LINES_IN_PDF])
        
        # Stocker si le PDF est tronqué pour afficher un avertissement
        is_truncated = total_receptions > MAX_LINES_IN_PDF
        lines_not_shown = total_receptions - MAX_LINES_IN_PDF if is_truncated else 0
    
    if receptions_with_quantity_delivered:
        # Optimisation: Pré-charger toutes les lignes de fichier nécessaires en une seule requête
        from .models import LigneFichier as _LF
        business_ids = []
        for reception in receptions_with_quantity_delivered:
            if isinstance(reception, dict):
                business_ids.append(reception.get('business_id'))
            else:
                business_ids.append(reception.business_id)
        
        # CRITIQUE pour 50K+ lignes: Charger avec iterator() pour économiser la RAM
        lignes_map = {}
        if business_ids:
            # Utiliser iterator() et only() pour ne charger que les champs nécessaires
            lignes = _LF.objects.filter(
                business_id__in=business_ids
            ).only('business_id', 'contenu').order_by('-id').iterator(chunk_size=2000)
            for ligne in lignes:
                if ligne.business_id not in lignes_map:
                    lignes_map[ligne.business_id] = ligne
        
        # En-têtes du tableau de données
        po_lines_headers = [
            "Line Description",
            "Ordered Qty",
            "Delivered Qty",
            "Received Qty",
            "Payable Qty",
            "Net Qty to Receive in Fusion",
            "Line",
            "Schedule"
        ]
        
        # Données du tableau
        po_lines_data = [po_lines_headers]
        
        # Ajouter les données de chaque réception
        for reception in receptions_with_quantity_delivered:
            # Gérer les données selon le type (snapshot ou objet Reception)
            if isinstance(reception, dict):
                # Données depuis le snapshot
                line_description = reception.get('line_description', 'N/A')
                ordered_quantity = reception['ordered_quantity']
                received_quantity = reception.get('received_quantity', 0)
                quantity_delivered = reception['quantity_delivered']
                # Calcul de la nouvelle colonne: Net Qty to receive in boost = Qty payable - Received
                try:
                    from decimal import Decimal
                    quantity_payable = reception['quantity_payable']
                    net_qty_to_receipt_in_boost = Decimal(str(quantity_payable)) - Decimal(str(received_quantity))
                except Exception:
                    net_qty_to_receipt_in_boost = 0
                quantity_payable = reception['quantity_payable']
                line = reception.get('line', 'N/A')
                schedule = reception.get('schedule', 'N/A')
            else:
                # Objet Reception actuel - récupérer les informations depuis le fichier
                line_description = "N/A"
                line = "N/A"
                schedule = "N/A"
                
                # Optimisation: Utiliser le dictionnaire pré-chargé au lieu de faire des requêtes
                try:
                    lf = lignes_map.get(reception.business_id)
                    if lf:
                        contenu = lf.contenu or {}
                        # Priorité aux clés exactes
                        if 'Line Description' in contenu and contenu['Line Description']:
                            ld_val = str(contenu['Line Description']).strip()
                            if ld_val:
                                line_description = ld_val[:50] + "..." if len(ld_val) > 50 else ld_val
                        if 'Line' in contenu and contenu['Line'] not in (None, ''):
                            line = str(contenu['Line']).strip()
                        if 'Schedule' in contenu and contenu['Schedule'] not in (None, ''):
                            schedule = str(contenu['Schedule']).strip()    
                        # Fallback tolérant
                        if line_description == "N/A":
                            for key, value in contenu.items():
                                if not key:
                                    continue
                                norm = key.strip().lower().replace('_', ' ')
                                norm = ' '.join(norm.split())
                                if value and (norm == 'line description' or ('description' in norm and 'line' in norm)):
                                    v = str(value).strip()
                                    if v:
                                        line_description = v[:50] + "..." if len(v) > 50 else v
                                        break
                        if line == "N/A":
                            for key, value in contenu.items():
                                if not key:
                                    continue
                                norm = key.strip().lower().replace('_', ' ')
                                norm = ' '.join(norm.split())
                                if value and norm == 'line':
                                    line = str(value).strip()
                                    break
                                if value and ('line' in norm and 'description' not in norm and 'type' not in norm):
                                    line = str(value).strip()
                                    break
                        if schedule == "N/A":
                            for key, value in contenu.items():
                                if not key:
                                    continue
                                norm = key.strip().lower().replace('_', ' ')
                                norm = ' '.join(norm.split())
                                if value and ('schedule' in norm):
                                    schedule = str(value).strip()
                                break        
                except Exception:
                    pass
                
                ordered_quantity = reception.ordered_quantity
                received_quantity = reception.received_quantity
                quantity_delivered = reception.quantity_delivered
                quantity_payable = reception.quantity_payable
                amount_delivered = reception.amount_delivered
                amount_payable = reception.amount_payable
                quantity_not_delivered = reception.quantity_not_delivered
                
                # Calcul de la nouvelle colonne: Net Qty to Receive in boost = Qty payable - Received
                try:
                    from decimal import Decimal
                    net_qty_to_receipt_in_boost = Decimal(str(quantity_payable)) - Decimal(str(received_quantity))
                except Exception:
                    net_qty_to_receipt_in_boost = 0
            
            # Ajouter la ligne de données
            po_lines_data.append([
                line_description,
                f"{fmt_amount(ordered_quantity, 2)}",
                f"{fmt_amount(quantity_delivered, 2)}",
                f"{fmt_amount(received_quantity, 2)}",
                f"{fmt_amount(quantity_payable, 2)}",
                f"{fmt_amount(net_qty_to_receipt_in_boost, 2)}",
                line,
                schedule
            ])
        
        # Créer le tableau de données
        po_lines_table = Table(po_lines_data, colWidths=[
        TABLE_WIDTH*0.38,  # Line Description (38%) - réduite pour faire de la place
        TABLE_WIDTH*0.08,  # Ordered Quantity (8%)
        TABLE_WIDTH*0.08,  # Quantity Delivered (8%)
        TABLE_WIDTH*0.08,  # Received Quantity (8%)
        TABLE_WIDTH*0.08,  # Quantity Payable (8%)
        TABLE_WIDTH*0.16,  # NetQty to Receive in boost (16%)
        TABLE_WIDTH*0.07,  # Line (8%)
        TABLE_WIDTH*0.07,  # Schedule (14%) - nouvelle colonne
    ])
        
        # Styles du tableau de données
        po_lines_table.setStyle(TableStyle([
            # En-têtes
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Times-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 7),
            ('BACKGROUND', (0, 0), (-1, 0), LIGHT_BLUE),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            
            # Données
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),    # Line Description à gauche
            ('ALIGN', (1, 1), (-1, -1), 'CENTER'), # Autres colonnes centrées
            ('FONTNAME', (0, 1), (-1, -1), 'Times-Roman'),
            
            # Bordures et grilles
            ('BOX', (0, 0), (-1, -1), 0.5, colors.black),
            ('GRID', (0, 0), (-1, -1), 0.25, colors.black),
            
            # Padding
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
            
            # Couleurs alternées pour les lignes de données
            ('BACKGROUND', (0, 1), (-1, 1), colors.white),
            ('BACKGROUND', (0, 2), (-1, 2), colors.whitesmoke),
        ]))
        
        # Ajouter des couleurs alternées pour toutes les lignes de données
        for i in range(1, len(po_lines_data)):
            if i % 2 == 0:
                po_lines_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, i), (-1, i), colors.whitesmoke)
                ]))
            else:
                po_lines_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, i), (-1, i), colors.white)
                ]))
        
        elements.append(po_lines_table)
    else:
        # Message si aucune ligne avec quantity_delivered > 0
        no_data_msg = Paragraph(
            "<i>Aucune ligne avec des quantités reçues (quantity_delivered > 0) trouvée pour ce bon de commande.</i>",
            normal_style
        )
        elements.append(no_data_msg)
    
    # ===================== FIN DEUXIÈME PAGE =====================
    
    # Création d'un cadre autour de tout le rapport
    # On utilise un canvas pour dessiner un cadre solide autour de la page
    def add_page_frame(canvas, doc):
        canvas.saveState()
        # Dessiner un cadre solide autour de la page avec une marge intérieure
        page_width, page_height = letter
        # Bordure solide noire avec une épaisseur de 1 point
        canvas.setStrokeColor(colors.black)
        canvas.setLineWidth(1)
        # Dessiner le rectangle avec une marge de 5 points par rapport aux marges du document
        canvas.rect(doc.leftMargin - 5, doc.bottomMargin - 5, 
                   page_width - doc.leftMargin - doc.rightMargin + 10, 
                   page_height - doc.bottomMargin - doc.topMargin + 10)
        canvas.restoreState()
    
    # Génération du PDF avec le cadre
    doc.build(elements, onFirstPage=add_page_frame, onLaterPages=add_page_frame)
    buffer.seek(0)
    return buffer
