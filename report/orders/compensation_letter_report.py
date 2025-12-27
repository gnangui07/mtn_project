"""But:
- Générer le PDF de la lettre de demande de compensation.

Étapes:
- Préparer styles et gabarit (logo, en-tête, adresse, références, objet).
- Composer les paragraphes (faits, dates, jours de retard, pénalité calculée).
- Ajouter les pièces jointes et signatures.
- Construire et retourner le buffer PDF.

Entrées:
- `bon_commande`: PO concerné.
- `context`: dictionnaire avec po_number, supplier, dates, pénalités, devise, etc.
- `user_email` (optionnel): pour traçabilité.

Sorties:
- `BytesIO`: buffer mémoire positionné au début, prêt à être renvoyé.
"""
from __future__ import annotations

from datetime import datetime
import os
from decimal import Decimal
from io import BytesIO
from typing import Any, Dict

from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

# Couleurs MSRN - Palette harmonieuse
MODERN_BLUE = colors.HexColor("#1F5C99")  # Bleu foncé professionnel


def _fmt_date(value) -> str:
    """Format date for display."""
    if not value:
        return "N/A"
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y")
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return str(value)


def _fmt_amount(value, currency: str = "") -> str:
    """Format monetary amount for display."""
    if value is None:
        return "N/A"
    try:
        decimal_value = Decimal(str(value))
    except Exception:
        return "N/A"
    formatted = f"{decimal_value:,.0f}".replace(",", " ")
    return f"{formatted} {currency}" if currency else formatted


def generate_compensation_letter(
    bon_commande,
    context: Dict[str, Any],
    user_email: str | None = None,
) -> BytesIO:
    """But:
    - Construire le PDF de la lettre de compensation.

    Étapes:
    - Initialiser le document et les styles.
    - Injecter les données du contexte (PO, fournisseur, montants, dates).
    - Générer les sections (adresse, objet, corps, PJ, signatures).
    - `doc.build()` puis `seek(0)` et retourner le buffer.

    Entrées:
    - bon_commande: objet du bon de commande.
    - context: données nécessaires à la lettre.
    - user_email: email de l'émetteur (optionnel).

    Sorties:
    - BytesIO: PDF en mémoire.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=50,
        rightMargin=50,
        topMargin=50,
        bottomMargin=50,
    )

    styles = getSampleStyleSheet()
    
    # Styles personnalisés
    header_style = ParagraphStyle(
        "Header",
        parent=styles["Normal"],
        fontName="Times-Roman",
        fontSize=11,
        alignment=TA_RIGHT,
        textColor=colors.black,
    )
    
    date_style = ParagraphStyle(
        "Date",
        parent=styles["Normal"],
        fontName="Times-Roman",
        fontSize=11,
        alignment=TA_RIGHT,
        textColor=colors.black,
        spaceAfter=20,
    )
    
    address_style = ParagraphStyle(
        "Address",
        parent=styles["Normal"],
        fontName="Times-Roman",
        fontSize=11,
        alignment=TA_LEFT,
        textColor=colors.black,
        spaceAfter=15,
    )
    
    ref_style = ParagraphStyle(
        "Reference",
        parent=styles["Normal"],
        fontName="Times-Roman",
        fontSize=11,
        alignment=TA_LEFT,
        textColor=colors.black,
        spaceAfter=10,
    )
    
    object_style = ParagraphStyle(
        "Object",
        parent=styles["Normal"],
        fontName="Times-Bold",
        fontSize=11,
        alignment=TA_LEFT,
        textColor=colors.black,
        spaceAfter=20,
    )
    
    salutation_style = ParagraphStyle(
        "Salutation",
        parent=styles["Normal"],
        fontName="Times-Roman",
        fontSize=11,
        alignment=TA_LEFT,
        textColor=colors.black,
        spaceAfter=15,
    )
    
    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontName="Times-Roman",
        fontSize=11,
        alignment=TA_JUSTIFY,
        textColor=colors.black,
        spaceAfter=12,
        leading=16,
    )
    
    signature_style = ParagraphStyle(
        "Signature",
        parent=styles["Normal"],
        fontName="Times-Roman",
        fontSize=11,
        alignment=TA_RIGHT,
        textColor=colors.black,
        spaceAfter=8,
    )

    elements = []

    # Logo MTN (si disponible)
    logo_path = os.path.join(settings.BASE_DIR, "static", "logo_mtn.jpeg")
    if os.path.exists(logo_path):
        logo = Image(str(logo_path), width=80, height=40)
        logo.hAlign = 'LEFT'
        elements.append(logo)
        elements.append(Spacer(1, 20))

    # Date
    current_date = datetime.now().strftime("%d %B %Y")
    elements.append(Paragraph(f"Abidjan le {current_date}", date_style))

    # Fournisseur
    supplier_name = context.get("supplier", "N/A")
    elements.append(Paragraph(f"<b>{supplier_name}</b>", address_style))

    # Destinataire
    elements.append(Paragraph("A Monsieur le Directeur Général", address_style))

    # Références
    letter_ref = context.get("letter_reference")
    if not letter_ref:
        letter_ref = f"EPMO/ED/LDC/{datetime.now():%m-%Y}/000"
    elements.append(Paragraph(f"Nos réf : {letter_ref}", ref_style))

    # Objet
    elements.append(Paragraph("<b>Objet : Demande de compensation</b>", object_style))

    # Salutation
    elements.append(Paragraph("Monsieur le Directeur Général,", salutation_style))

    # Corps de la lettre - Paragraphe 1
    po_number = context.get("po_number", "N/A")
    order_description = context.get("order_description", "N/A")
    
    paragraph1 = f"""Nous venons par la présente vous informer que, suivant notre bon de commande 
    Numéro <b>{po_number}</b> relatif à <b>{order_description}</b> vous avez accusé un considérable 
    retard dans la livraison."""
    
    elements.append(Paragraph(paragraph1, body_style))

    # Corps de la lettre - Paragraphe 2
    date_prevue = _fmt_date(context.get("pip_end_date"))
    date_livraison = _fmt_date(context.get("actual_end_date"))
    nombre_jours = context.get("total_penalty_days", 0)
    jours_supplier = context.get("delay_part_vendor", 0)
    
    paragraph2 = f"""En effet, prévue pour le <b>{date_prevue}</b> conformément au bon de commande, 
    l'intégralité des prestations et/ou équipements a été livrée le <b>{date_livraison}</b>, 
    soit plus de <b>{nombre_jours}</b> jours après la date prévue (dont <b>{jours_supplier}</b> jours 
    vous sont imputables)."""
    
    elements.append(Paragraph(paragraph2, body_style))

    # Corps de la lettre - Paragraphe 3
    # Taux effectif global appliqué au bon : (pénalités dues / montant BC) * 100
    penalties_due = context.get("penalties_due")
    po_amount = context.get("po_amount")
    penalty_rate_contractuel = context.get("penalty_rate", Decimal("0.30"))

    taux_effectif = penalty_rate_contractuel
    try:
        if penalties_due is not None and po_amount not in (None, 0, "0", "0.00"):
            po_amount_dec = Decimal(str(po_amount))
            if po_amount_dec != 0:
                taux_effectif = (Decimal(str(penalties_due)) / po_amount_dec * Decimal("100")).quantize(Decimal("0.01"))
    except Exception:
        # En cas de problème de données, on retombe sur le taux contractuel
        taux_effectif = penalty_rate_contractuel

    # Formater le taux pour l'affichage : 8, 8.5 ou 8.49 (pas de zéros inutiles)
    taux_str = format(taux_effectif, "f")
    if "." in taux_str:
        taux_str = taux_str.rstrip("0").rstrip(".")
    pourcentage_penalite = taux_str
    montant_penalite = _fmt_amount(penalties_due, context.get("currency"))
    
    paragraph3 = f"""Au regard de ce qui précède et en application des clauses pertinentes de nos 
    conditions générales d'achat, régulièrement portées à votre connaissance, nous vous appliquons 
    une pénalité de <b>{pourcentage_penalite}%</b> soit <b>{montant_penalite}</b> Hors Taxes."""
    
    elements.append(Paragraph(paragraph3, body_style))

    # Corps de la lettre - Paragraphe 4
    paragraph4 = "Vous trouverez en annexe à la présente, le détail des pénalités."
    elements.append(Paragraph(paragraph4, body_style))

    # Formule de politesse
    elements.append(Paragraph("Vous en souhaitant bonne réception,", body_style))
    
    politesse = """Veuillez agréer, Monsieur le Directeur Général, l'expression de nos 
    sentiments distingués."""
    elements.append(Paragraph(politesse, body_style))

    elements.append(Spacer(1, 20))

    # Pièces jointes
    pj_style = ParagraphStyle(
        "PJ",
        parent=styles["Normal"],
        fontName="Times-Bold",
        fontSize=11,
        alignment=TA_LEFT,
        textColor=colors.black,
        spaceAfter=5,
    )
    
    elements.append(Paragraph("<b>PJ :</b>", pj_style))
    elements.append(Paragraph("- Fiche de pénalité", body_style))
    elements.append(Paragraph("- Copie du Bon de Commande", body_style))

    elements.append(Spacer(1, 30))

    # Signatures - Espacées à gauche et droite
    
    signature_right_style = ParagraphStyle(
        "SignatureRight",
        parent=styles["Normal"],
        fontName="Times-Roman",
        fontSize=11,
        alignment=TA_RIGHT,
        textColor=colors.black,
    )
    
    signatures_data = [
        [
            "",
            Paragraph("<b>Moriba BAMBA</b><br/>Senior Manager. Supply Chain Management", signature_right_style)
        ]
    ]
    
    signatures_table = Table(signatures_data, colWidths=[256, 256])
    signatures_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (0, -1), 0),
                ("RIGHTPADDING", (1, 0), (1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    elements.append(signatures_table)

    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer
