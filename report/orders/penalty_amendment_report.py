"""But:
- Générer le PDF de la Fiche d'Amendement de Pénalité.

Étapes:
- Construire les sections: entête, infos BC, objet, pénalité, répartition, doléances/proposition, statut, nouvelle pénalité, signatures.
- Mettre en forme des montants et des dates.
- Retourner un buffer mémoire prêt à être envoyé.

Entrées:
- `bon_commande` (NumeroBonCommande), `context` (dict) avec valeurs calculées + saisies, `user_email` (str|None).

Sorties:
- `BytesIO` contenant le PDF.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from io import BytesIO
from typing import Any, Dict, Iterable

from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


# Couleurs MSRN - Palette harmonieuse
MODERN_BLUE = colors.HexColor("#1F5C99")  # Bleu foncé professionnel
LIGHT_BLUE = colors.HexColor("#E6F0FA")   # Bleu très clair pour fonds


def _fmt_date(value) -> str:
    if not value:
        return "N/A"
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y")
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:  # pragma: no cover - fallback only
        return str(value)


def _fmt_amount(value: Decimal | float | int | str, currency: str | None = None) -> str:
    if value is None:
        return "N/A"
    try:
        decimal_value = Decimal(str(value))
    except Exception:
        return "N/A"
    formatted = f"{decimal_value:,.2f}".replace(",", " ").replace(".", ",")
    return f"{formatted} {currency}" if currency else formatted


def _section_bar(text: str, *, style: ParagraphStyle, fill: colors.Color = MODERN_BLUE) -> Table:
    bar = Table([[Paragraph(text, style)]], colWidths=[552])
    bar.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), fill),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return bar


def _key_value_rows(rows: Iterable[tuple[str, str]], label_style: ParagraphStyle, value_style: ParagraphStyle) -> Table:
    data = []
    for label, value in rows:
        data.append(
            [
                Paragraph(label, label_style),
                Paragraph(value or "N/A", value_style),
            ]
        )
    table = Table(data, colWidths=[180, 372])
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("BACKGROUND", (0, 0), (0, -1), LIGHT_BLUE),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return table


def generate_penalty_amendment_report(
    bon_commande,
    context: Dict[str, Any],
    user_email: str | None = None,
) -> BytesIO:
    """Build the Penalty Amendment Sheet PDF."""
    # Créer un tampon mémoire pour stocker le PDF (aucun fichier écrit sur disque)
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=20,
        rightMargin=20,
        topMargin=20,
        bottomMargin=20,
    )
    # Styles de base pour uniformiser les polices et tailles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "Title",
        parent=styles["Title"],
        fontName="Times-Bold",
        fontSize=11,
        alignment=TA_CENTER,
        textColor=colors.black,
    )
    doc_number_style = ParagraphStyle(
        "DocNumber",
        parent=styles["Normal"],
        fontName="Times-Bold",
        fontSize=8,
        alignment=TA_RIGHT,
    )
    section_header_style = ParagraphStyle(
        "SectionHeader",
        parent=styles["Normal"],
        fontName="Times-Bold",
        fontSize=7,
        alignment=TA_LEFT,
        textColor=colors.white,
    )
    subsection_style = ParagraphStyle(
        "SubSection",
        parent=styles["Normal"],
        fontName="Times-Bold",
        fontSize=7,
        textColor=colors.black,
    )
    label_style = ParagraphStyle(
        "Label",
        parent=styles["Normal"],
        fontName="Times-Bold",
        fontSize=6.5,
    )
    value_style = ParagraphStyle(
        "Value",
        parent=styles["Normal"],
        fontName="Times-Roman",
        fontSize=6.5,
    )
    long_text_style = ParagraphStyle(
        "LongText",
        parent=styles["Normal"],
        fontName="Times-Roman",
        fontSize=6.5,
        leading=7.5,
    )
    small_style = ParagraphStyle(
        "Small",
        parent=styles["Normal"],
        fontName="Times-Roman",
        fontSize=7,
        alignment=TA_RIGHT,
        textColor=colors.grey,
    )

    # La liste des "éléments" (titres, tableaux, textes) qui composent le PDF
    elements: list[Any] = []

    logo_path = settings.BASE_DIR / "static" / "logo_mtn.jpeg"
    # Entête avec logo, titre et numéro de document
    header_table = Table(
        [
            [
                Image(str(logo_path), width=60, height=24),
                Paragraph("FICHE D'AMENDEMENT DE PENALITE", title_style),
                Paragraph("N° AP/15/001", doc_number_style),
            ]
        ],
        colWidths=[80, 360, 100],
    )
    header_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (0, -1), "LEFT"),
                ("ALIGN", (1, 0), (1, 0), "CENTER"),
                ("ALIGN", (2, 0), (2, 0), "RIGHT"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(header_table)
    elements.append(Spacer(1, 6))

    # Section: Demandeur (qui initie la demande)
    elements.append(_section_bar("DEMANDEUR", style=section_header_style))
    elements.append(Spacer(1, 2))
    # Ligne simple "Étiquette : Valeur"
    requester_table = _key_value_rows([( "demandeur", context.get("requester", "N/A"))], label_style, value_style)
    elements.append(requester_table)
    elements.append(Spacer(1, 6))

    # Section: Information Bon de Commande (PO principal)
    elements.append(_section_bar("INFORMATION BON DE COMMANDE", style=section_header_style))
    elements.append(Spacer(1, 2))
    info_rows = [
        ("N° DU BON DE COMMANDE", str(context.get("po_number", "N/A"))),
        ("FOURNISSEUR", context.get("supplier", "N/A")),
        (
            "MONTANT DU BON DE COMMANDE",
            _fmt_amount(context.get("po_amount"), context.get("currency")),
        ),
        ("DEVISE DU BON DE COMMANDE", context.get("currency", "N/A")),
        ("DATE DU BON DE COMMANDE", _fmt_date(context.get("order_date"))),
    ]
    info_table = _key_value_rows(info_rows, label_style, value_style)
    elements.append(info_table)
    elements.append(Spacer(1, 6))

    # Section: Objet du contrat (texte libre)
    elements.append(_section_bar("OBJET DU CONTRAT", style=section_header_style))
    elements.append(Spacer(1, 2))
    # Bloc de texte sous forme de tableau pour encadrer la zone
    contract_table = Table(
        [[Paragraph(context.get("order_description", "N/A"), long_text_style)]],
        colWidths=[552],
    )
    contract_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.5, colors.black),
                ("BACKGROUND", (0, 0), (-1, -1), colors.whitesmoke),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    elements.append(contract_table)
    elements.append(Spacer(1, 6))

    # Section: Pénalité (rappel des dates et calcul initial)
    elements.append(_section_bar("PENALITE", style=section_header_style))
    elements.append(Spacer(1, 3))

    # Dates et calcul - intégré dans le tableau
    dates_data = [
        [Paragraph("Dates et calcul", subsection_style)],
    ]
    dates_rows_data = [
        [Paragraph("DATE DE FIN CONTRACTUELLE", label_style), Paragraph(_fmt_date(context.get("pip_end_date")), value_style)],
        [Paragraph("DATE DE FIN REELLE", label_style), Paragraph(_fmt_date(context.get("actual_end_date")), value_style)],
        [Paragraph("NOMBRE DE JOURS TOTAL DE PENALITE", label_style), Paragraph(str(context.get("total_penalty_days", 0)), value_style)],
    ]
    
    # Tableau des dates avec un entête sur toute la largeur
    dates_table = Table([dates_data[0]] + dates_rows_data, colWidths=[180, 372])
    dates_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("SPAN", (0, 0), (1, 0)),  # Merge header across columns
                ("BACKGROUND", (0, 0), (1, 0), MODERN_BLUE),
                ("BACKGROUND", (0, 1), (0, -1), LIGHT_BLUE),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    elements.append(dates_table)
    elements.append(Spacer(1, 4))

    # Répartition des jours - intégré dans le tableau (MTN / Prestataire / Force majeure)
    repartition_data = [
        [Paragraph("Répartition des jours", subsection_style)],
        [Paragraph("MTN", label_style), Paragraph("Prestataire", label_style), Paragraph("Forces majeures", label_style)],
        [
            Paragraph(str(context.get("delay_part_mtn", 0)), value_style),
            Paragraph(str(context.get("delay_part_vendor", 0)), value_style),
            Paragraph(str(context.get("delay_part_force_majeure", 0)), value_style),
        ],
    ]
    repartition_table = Table(repartition_data, colWidths=[184, 184, 184])
    repartition_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("SPAN", (0, 0), (2, 0)),  # Merge header across all columns
                ("BACKGROUND", (0, 0), (2, 0), MODERN_BLUE),
                ("BACKGROUND", (0, 1), (-1, 1), LIGHT_BLUE),
                ("ALIGN", (0, 2), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    elements.append(repartition_table)
    elements.append(Spacer(1, 6))

    # Section: Pénalité due (montant initial avant amendement)
    elements.append(_section_bar("PENALITE DUE", style=section_header_style))
    elements.append(Spacer(1, 2))
    penalty_due_table = Table(
        [[
            Paragraph("PENALITE DUE :", label_style),
            Paragraph(_fmt_amount(context.get("penalty_due"), context.get("currency")), value_style),
        ]],
        colWidths=[180, 372],
    )
    penalty_due_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("BACKGROUND", (0, 0), (0, -1), LIGHT_BLUE),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    elements.append(penalty_due_table)
    elements.append(Spacer(1, 6))

    # Section: Doléances / Proposition (champs libres)
    elements.append(_section_bar("DOLEANCE DU FOURNISSEUR / PROPOSITION DU PM", style=section_header_style))
    elements.append(Spacer(1, 2))
    # Deux colonnes pour juxtaposer les textes
    pleas_table = Table(
        [
            [
                Paragraph("DOLEANCE DU FOURNISSEUR", subsection_style),
                Paragraph("PROPOSITION DU PM", subsection_style),
            ],
            [
                Paragraph(context.get("supplier_plea", "") or " ", long_text_style),
                Paragraph(context.get("pm_proposal", "") or " ", long_text_style),
            ],
        ],
        colWidths=[276, 276],
    )
    pleas_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.5, colors.black),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("BACKGROUND", (0, 0), (-1, 0), MODERN_BLUE),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    elements.append(pleas_table)
    elements.append(Spacer(1, 6))

    # Section: Statut de la pénalité (case cochée visuelle)
    elements.append(_section_bar("STATUT DE LA PENALITE", style=section_header_style))
    elements.append(Spacer(1, 2))
    status_labels = [
        ("ANNULEE", "annulee"),
        ("REDUITE", "reduite"),
        ("RECONDUITE", "reconduite"),
    ]
    current_status = str(context.get("penalty_status") or "").lower()
    
    # Create two-row table: labels on first row, indicator on second row
    # First row: labels
    label_cells = []
    for label, key in status_labels:
        label_cells.append(Paragraph(label, value_style))
    
    # Deuxième ligne: case cochée uniquement sous l'option choisie
    indicator_cells = []
    for label, key in status_labels:
        checked = current_status == key
        if checked:
            # Green check mark under checked option
            indicator_cells.append(Paragraph("✓", value_style))
        else:
            # Empty for unchecked options
            indicator_cells.append(Paragraph("", value_style))
    
    status_table = Table([label_cells, indicator_cells], colWidths=[184, 184, 184])
    status_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    elements.append(status_table)
    elements.append(Spacer(1, 6))

    # Section: Nouvelle pénalité due (montant modifié après amendement)
    elements.append(_section_bar("NOUVELLE PENALITE DUE", style=section_header_style))
    elements.append(Spacer(1, 2))
    new_penalty_table = Table(
        [[
            Paragraph("NOUVELLE PENALITE DUE :", label_style),
            Paragraph(_fmt_amount(context.get("new_penalty_due"), context.get("currency")), value_style),
        ]],
        colWidths=[180, 372],
    )
    new_penalty_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("BACKGROUND", (0, 0), (0, -1), LIGHT_BLUE),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    elements.append(new_penalty_table)
    elements.append(Spacer(1, 6))

    # Section: Validation du management (emplacements de signature)
    elements.append(_section_bar("VALIDATION DU MANAGEMENT", style=section_header_style))
    elements.append(Spacer(1, 2))

    # Toutes les signatures sur une seule ligne (5 postes)
    signature_labels = [
        "Project Manager",
        "Senior Manager",
        "Senior Manager Supply Chain",
        "General Manager EPMO",
        "Chief Financial Officer",
    ]
    signatures_table = Table(
        [[Paragraph(label, label_style) for label in signature_labels], [Spacer(1, 30) for _ in signature_labels]],
        colWidths=[110, 110, 110, 110, 112],
        rowHeights=[None, 35],
    )
    signatures_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("BACKGROUND", (0, 0), (-1, 0), LIGHT_BLUE),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    elements.append(signatures_table)

    # Optionnel: afficher qui a généré le document et quand
    if user_email:
        elements.append(Spacer(1, 10))
        elements.append(
            Paragraph(
                f"Document généré par : {user_email} le {datetime.now():%d/%m/%Y %H:%M}",
                small_style,
            )
        )

    # Générer le PDF final et réinitialiser le tampon
    doc.build(elements)
    buffer.seek(0)
    return buffer
