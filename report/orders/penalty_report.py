"""PDF generation for the Penalty Sheet document."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from io import BytesIO
from typing import Any, Dict

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from django.conf import settings


# Couleurs MSRN - Palette harmonieuse
MODERN_BLUE = colors.HexColor("#1F5C99")  # Bleu foncé professionnel
LIGHT_BLUE = colors.HexColor("#E6F0FA")   # Bleu très clair pour fonds
LIGHT_GREY = colors.HexColor("#F5F5F5")


def _fmt_date(value: datetime | None) -> str:
    if not value:
        return "N/A"
    return value.strftime("%d/%m/%Y")


def _fmt_amount(value: Decimal | float | int | str, currency: str | None = None) -> str:
    try:
        decimal_value = Decimal(str(value))
    except Exception:
        return "N/A"
    formatted = f"{decimal_value:,.2f}".replace(",", " ").replace(".", ",")
    return f"{formatted} {currency}" if currency else formatted


def generate_penalty_report(
    bon_commande,
    context: Dict[str, Any],
    user_email: str | None = None,
) -> BytesIO:
    """But:
    - Générer le PDF de la fiche de pénalité et le retourner en mémoire.

    Étapes:
    - Construire les sections (infos PO, pénalité, observation, signatures).
    - Formater les montants et dates.
    - Construire le document avec ReportLab et retourner le buffer.

    Entrées:
    - `bon_commande` (NumeroBonCommande), `context` (dict), `user_email` (str|None).

    Sorties:
    - `BytesIO` prêt à être servi en HTTP ou envoyé par email.
    """
    # On crée un "tampon" mémoire qui va contenir le PDF fini (pas de fichier sur disque)
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=18,
        leftMargin=18,
        topMargin=20,
        bottomMargin=20,
    )
    # "elements" = la liste des blocs (titres, tableaux, textes) à mettre dans le PDF
    elements: list[Any] = []

    # Styles de base pour formater les textes
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "Title",
        parent=styles["Title"],
        fontName="Times-Bold",
        fontSize=16,
        alignment=TA_CENTER,
        textColor=colors.white,
        spaceAfter=6,
    )
    doc_number_style = ParagraphStyle(
        "DocNumber",
        parent=styles["Normal"],
        fontName="Times-Bold",
        fontSize=9,
        alignment=TA_RIGHT,
    )
    section_header_style = ParagraphStyle(
        "SectionHeader",
        parent=styles["Normal"],
        fontName="Times-Bold",
        fontSize=10,
        alignment=TA_LEFT,
        textColor=colors.white,
        spaceAfter=4,
        leading=12,
    )
    label_style = ParagraphStyle(
        "Label",
        parent=styles["Normal"],
        fontName="Times-Bold",
        fontSize=8,
    )
    value_style = ParagraphStyle(
        "Value",
        parent=styles["Normal"],
        fontName="Times-Roman",
        fontSize=8,
    )
    small_style = ParagraphStyle(
        "Small",
        parent=styles["Normal"],
        fontName="Times-Roman",
        fontSize=7,
    )

    # Entête avec logo, titre du document et numéro généré
    logo_path = settings.BASE_DIR / "static" / "logo_mtn.jpeg"
    header_data = [
        [
            Image(str(logo_path), width=60, height=24),
            Paragraph("FICHE DE CALCUL DE PENALITES DE RETARD LIVRAISON", title_style),
            Paragraph(f"N° FP/{datetime.now():%y/%m/%d}", doc_number_style),
        ]
    ]
    header_table = Table(header_data, colWidths=[80, 350, 100])
    header_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (0, 0), "LEFT"),
                ("ALIGN", (2, 0), (2, 0), "RIGHT"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(header_table)
    elements.append(Spacer(1, 6))

    # Petit outil: crée un en-tête de section coloré (pour séparer visuellement les parties)
    def section_header(label: str):
        table = Table(
            [[Paragraph(label, section_header_style)]],
            colWidths=[530],
        )
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), MODERN_BLUE),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        elements.append(table)
        elements.append(Spacer(1, 4))

    # Petit outil: crée une ligne d'information "Étiquette : Valeur"
    def info_row(label: str, value: str):
        table = Table(
            [
                [
                    Paragraph(label, label_style),
                    Paragraph(value or "N/A", value_style),
                ]
            ],
            colWidths=[180, 350],
        )
        table.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.black),
                    ("BACKGROUND", (0, 0), (0, -1), LIGHT_BLUE),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        elements.append(table)
        elements.append(Spacer(1, 4))

    # SECTION: Demandeur (qui est responsable côté projet)
    section_header("DEMANDEUR")
    info_row("Nom du Demandeur", context.get("project_coordinator", "N/A"))

    # SECTION: Informations principales du Bon de Commande (numéro, fournisseur, montants, dates)
    section_header("INFORMATION BON DE COMMANDE")
    info_table_data = [
        [
            Paragraph("N° DU BON DE COMMANDE", label_style),
            Paragraph(context.get("po_number", "N/A"), value_style),
            Paragraph("FOURNISSEUR", label_style),
            Paragraph(context.get("supplier", "N/A"), value_style),
        ],
        [
            Paragraph("MONTANT BC", label_style),
            Paragraph(
                _fmt_amount(context.get("po_amount", Decimal("0")), context.get("currency")),
                value_style,
            ),
            Paragraph("DEVISE", label_style),
            Paragraph(context.get("currency", "N/A"), value_style),
        ],
        [
            Paragraph("DATE BC", label_style),
            Paragraph(_fmt_date(context.get("creation_date")), value_style),
            Paragraph("DATE FIN CONTRACTUELLE", label_style),
            Paragraph(_fmt_date(context.get("pip_end_date")), value_style),
        ],
        [
            Paragraph("DATE FIN RÉELLE", label_style),
            Paragraph(_fmt_date(context.get("actual_end_date")), value_style),
            Paragraph("NOMBRE JOURS DE RETARD", label_style),
            Paragraph(str(context.get("total_penalty_days", 0)), value_style),
        ],
    ]
    info_table = Table(info_table_data, colWidths=[135, 130, 135, 130])
    info_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BLUE),
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BACKGROUND", (0, 0), (-1, -1), None),
                ("BACKGROUND", (0, 0), (0, -1), LIGHT_BLUE),
                ("BACKGROUND", (2, 0), (2, -1), LIGHT_BLUE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    elements.append(info_table)
    elements.append(Spacer(1, 6))

    # SECTION: Objet de la commande (description générale)
    section_header("OBJET COMMANDE")
    info_row("Description", context.get("order_description", "N/A"))

    # SECTION: Mode de calcul des pénalités (jours de retard, taux, répartition, montants)
    section_header("MODE DE CALCUL PENALITES")
    penalty_data = [
        [
            Paragraph("Date fin contractuelle", label_style),
            Paragraph(_fmt_date(context.get("pip_end_date")), value_style),
            Paragraph("Date fin réelle", label_style),
            Paragraph(_fmt_date(context.get("actual_end_date")), value_style),
        ],
        [
            Paragraph("Nombre jours de retard", label_style),
            Paragraph(str(context.get("total_penalty_days", 0)), value_style),
            Paragraph("Taux de pénalité (calendaire)", label_style),
            Paragraph(f"{context.get('penalty_rate', Decimal('0'))}%", value_style),
        ],
        [
            Paragraph("Jours imputables MTN", label_style),
            Paragraph(str(context.get("delay_part_mtn", 0)), value_style),
            Paragraph("Jours imputables Forces Majeures", label_style),
            Paragraph(str(context.get("delay_part_force_majeure", 0)), value_style),
        ],
        [
            Paragraph("Jours imputables Prestataire", label_style),
            Paragraph(str(context.get("delay_part_vendor", 0)), value_style),
            Paragraph("Quotité réalisée", label_style),
            Paragraph(f"{context.get('quotite_realisee', Decimal('0'))}%", value_style),
        ],
        [
            Paragraph("Quotité non réalisée", label_style),
            Paragraph(f"{context.get('quotite_non_realisee', Decimal('0'))}%", value_style),
            Paragraph("Pénalités calculées", label_style),
            Paragraph(
                _fmt_amount(context.get("penalties_calculated", Decimal("0")), context.get("currency")),
                value_style,
            ),
        ],
        [
            Paragraph("Plafond de pénalité (10%)", label_style),
            Paragraph(
                _fmt_amount(context.get("penalty_cap", Decimal("0")), context.get("currency")),
                value_style,
            ),
            Paragraph("Pénalités dues", label_style),
            Paragraph(
                _fmt_amount(context.get("penalties_due", Decimal("0")), context.get("currency")),
                value_style,
            ),
        ],
    ]
    penalty_table = Table(penalty_data, colWidths=[150, 115, 150, 115])
    penalty_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BACKGROUND", (0, 0), (-1, -1), None),
                ("BACKGROUND", (0, 0), (-1, -1), None),
                ("BACKGROUND", (0, 0), (-1, -1), None),
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BACKGROUND", (0, 0), (-1, -1), None),
                ("BACKGROUND", (0, 0), (-1, -1), None),
                ("BACKGROUND", (0, 0), (-1, -1), None),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    elements.append(penalty_table)
    elements.append(Spacer(1, 6))

    # SECTION: Zone d'observation (texte libre pour commentaires)
    section_header("OBSERVATION")
    observation_text = context.get("observation", "") or " " * 5
    observation_table = Table(
        [[Paragraph(observation_text, value_style)]],
        colWidths=[530],
    )
    observation_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.5, colors.black),
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 40),
            ]
        )
    )
    elements.append(observation_table)
    elements.append(Spacer(1, 12))

    # SECTION: Signatures (emplacements pour validation interne)
    section_header("SIGNATURES")
    signature_labels = [
        " Project Coordinator",
        "Project Manager",
        "Senior Project Manager",
        "Manager Portfolio Financial Assurance & Reporting",
        "General Manager EPMO",
    ]
    signature_rows = [
        [Paragraph(label, small_style) for label in signature_labels],
        [Spacer(1, 30) for _ in signature_labels],
    ]
    signatures_table = Table(
        signature_rows,
        colWidths=[110, 105, 105, 105, 105],
        rowHeights=[None, 55],
    )
    signatures_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )
    elements.append(signatures_table)

    # Option: afficher qui a généré le document et quand
    if user_email:
        elements.append(Spacer(1, 8))
        elements.append(
            Paragraph(
                f"Document généré par : {user_email} le {datetime.now():%d/%m/%Y %H:%M}",
                small_style,
            )
        )

    # Construction finale du PDF à partir de la liste d'éléments
    doc.build(elements)
    # Remettre le curseur au début pour permettre la lecture du PDF
    buffer.seek(0)
    return buffer
