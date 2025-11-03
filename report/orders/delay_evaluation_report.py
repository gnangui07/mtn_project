"""PDF generation for the Delivery Delay Evaluation document."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from io import BytesIO
from typing import Any, Dict, List

from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


# Couleurs MSRN - Palette harmonieuse
MODERN_BLUE = colors.HexColor("#1F5C99")  # Bleu foncé professionnel
LIGHT_BLUE = colors.HexColor("#E6F0FA")   # Bleu très clair pour fonds


def _fmt_date(value: datetime | None) -> str:
    if not value:
        return "N/A"
    return value.strftime("%d/%m/%Y")


def _fmt_datetime(value: datetime | None) -> str:
    if not value:
        return "N/A"
    return value.strftime("%d/%m/%Y %H:%M")


def _fmt_amount(value: Decimal | float | int | str | None, currency: str | None = None) -> str:
    if value is None:
        return "N/A"
    try:
        decimal_value = Decimal(str(value))
    except Exception:
        return "N/A"
    formatted = f"{decimal_value:,.2f}".replace(",", " ").replace(".", ",")
    return f"{formatted} {currency}" if currency else formatted


def _build_section_title(label: str) -> Table:
    table = Table([[Paragraph(label, SECTION_HEADER_STYLE)]], colWidths=[530])
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
    return table


def _info_row(label: str, value: str) -> Table:
    table = Table(
        [[Paragraph(label, LABEL_STYLE), Paragraph(value or "N/A", VALUE_STYLE)]],
        colWidths=[180, 350],
    )
    table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.5, colors.black),
                ("BACKGROUND", (0, 0), (0, -1), LIGHT_BLUE),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return table


def _multiline_block(label: str, content: str) -> Table:
    block = Table(
        [
            [Paragraph(label, LABEL_STYLE)],
            [Paragraph(content or " ", VALUE_STYLE)],
        ],
        colWidths=[530],
    )
    block.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.5, colors.black),
                ("BACKGROUND", (0, 0), (0, 0), LIGHT_BLUE),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, 0), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return block


STYLE_CACHE_INITIALISED = False
SECTION_HEADER_STYLE: ParagraphStyle
LABEL_STYLE: ParagraphStyle
VALUE_STYLE: ParagraphStyle
TITLE_STYLE: ParagraphStyle
DOC_NUM_STYLE: ParagraphStyle
SMALL_STYLE: ParagraphStyle


def _ensure_styles():
    global STYLE_CACHE_INITIALISED
    global SECTION_HEADER_STYLE, LABEL_STYLE, VALUE_STYLE, TITLE_STYLE, DOC_NUM_STYLE, SMALL_STYLE

    if STYLE_CACHE_INITIALISED:
        return

    styles = getSampleStyleSheet()
    TITLE_STYLE = ParagraphStyle(
        "DelayEvalTitle",
        parent=styles["Title"],
        fontName="Times-Bold",
        fontSize=16,
        alignment=TA_CENTER,
        textColor=colors.white,
        spaceAfter=6,
    )
    DOC_NUM_STYLE = ParagraphStyle(
        "DocNumber",
        parent=styles["Normal"],
        fontName="Times-Bold",
        fontSize=9,
        alignment=TA_LEFT,
    )
    SECTION_HEADER_STYLE = ParagraphStyle(
        "SectionHeader",
        parent=styles["Normal"],
        fontName="Times-Bold",
        fontSize=10,
        alignment=TA_LEFT,
        textColor=colors.white,
        spaceAfter=4,
        leading=12,
    )
    LABEL_STYLE = ParagraphStyle(
        "Label",
        parent=styles["Normal"],
        fontName="Times-Bold",
        fontSize=8,
    )
    VALUE_STYLE = ParagraphStyle(
        "Value",
        parent=styles["Normal"],
        fontName="Times-Roman",
        fontSize=8,
    )
    SMALL_STYLE = ParagraphStyle(
        "Small",
        parent=styles["Normal"],
        fontName="Times-Roman",
        fontSize=7,
    )
    STYLE_CACHE_INITIALISED = True


SIGNATURE_LABELS: List[str] = [
    "Project Coordinator",
    "Project Manager",
    "Senior Manager Project",
    "Manager Portfolio Financial Assurance & Reporting",
    "General Manager EPMO",
]


def generate_delay_evaluation_report(
    bon_commande,
    context: Dict[str, Any],
    user_email: str | None = None,
) -> BytesIO:
    """Generate the Delivery Delay Evaluation PDF."""
    _ensure_styles()

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=18,
        leftMargin=18,
        topMargin=20,
        bottomMargin=20,
    )

    elements: List[Any] = []

    logo_path = settings.BASE_DIR / "static" / "logo_mtn.jpeg"
    header_data = [
        [
            Image(str(logo_path), width=60, height=24),
            Paragraph("EVALUATION DES DELAIS DE LIVRAISON", TITLE_STYLE),
            Paragraph(f"N° ED/{datetime.now():%y/%m/%d}", DOC_NUM_STYLE),
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

    # Project Manager section
    elements.append(_build_section_title("NOM DU PROJECT MANAGER"))
    elements.append(Spacer(1, 4))
    elements.append(_info_row("Project Manager", context.get("project_manager", "N/A")))
    elements.append(Spacer(1, 6))

    # PO info section
    elements.append(_build_section_title("INFORMATION BON DE COMMANDE"))
    elements.append(Spacer(1, 4))

    info_table_data = [
        [
            Paragraph("N° DU BON DE COMMANDE", LABEL_STYLE),
            Paragraph(context.get("po_number", "N/A"), VALUE_STYLE),
            Paragraph("FOURNISSEUR", LABEL_STYLE),
            Paragraph(context.get("supplier", "N/A"), VALUE_STYLE),
        ],
        [
            Paragraph("MONTANT BC", LABEL_STYLE),
            Paragraph(
                _fmt_amount(context.get("po_amount"), context.get("currency")),
                VALUE_STYLE,
            ),
            Paragraph("DEVISE", LABEL_STYLE),
            Paragraph(context.get("currency", "N/A"), VALUE_STYLE),
        ],
        [
            Paragraph("DATE BC", LABEL_STYLE),
            Paragraph(_fmt_date(context.get("creation_date")), VALUE_STYLE),
            Paragraph("DATE FIN CONTRACTUELLE", LABEL_STYLE),
            Paragraph(_fmt_date(context.get("pip_end_date")), VALUE_STYLE),
        ],
    ]
    info_table = Table(info_table_data, colWidths=[135, 130, 135, 130])
    info_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BACKGROUND", (0, 0), (0, -1), LIGHT_BLUE),
                ("BACKGROUND", (2, 0), (2, -1), LIGHT_BLUE),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    elements.append(info_table)
    elements.append(Spacer(1, 6))

    # Contract object
    elements.append(_build_section_title("OBJET DU CONTRAT"))
    elements.append(Spacer(1, 4))
    elements.append(_multiline_block("Description", context.get("order_description", "N/A")))
    elements.append(Spacer(1, 6))

    # Evaluation de retard section
    elements.append(_build_section_title("EVALUATION DE RETARD"))
    elements.append(Spacer(1, 4))

    chronology_table = Table(
        [
            [
                Paragraph("Date fin contractuelle", LABEL_STYLE),
                Paragraph(_fmt_date(context.get("pip_end_date")), VALUE_STYLE),
                Paragraph("Date fin réelle", LABEL_STYLE),
                Paragraph(_fmt_date(context.get("actual_end_date")), VALUE_STYLE),
            ],
            [
                Paragraph("Nombre total de jours de retard", LABEL_STYLE),
                Paragraph(str(context.get("total_delay_days", 0)), VALUE_STYLE),
                Paragraph("Date d'évaluation", LABEL_STYLE),
                Paragraph(_fmt_datetime(context.get("evaluation_date")), VALUE_STYLE),
            ],
        ],
        colWidths=[135, 130, 135, 130],
    )
    chronology_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("BACKGROUND", (0, 0), (0, -1), LIGHT_BLUE),
                ("BACKGROUND", (2, 0), (2, -1), LIGHT_BLUE),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    elements.append(chronology_table)
    elements.append(Spacer(1, 6))

    repartition_data = [
        [
            Paragraph("Jours imputables MTN", LABEL_STYLE),
            Paragraph("Jours imputables Prestataire", LABEL_STYLE),
            Paragraph("Jours imputables F. Majeures", LABEL_STYLE),
        ],
        [
            Paragraph(str(context.get("delay_part_mtn", 0)), VALUE_STYLE),
            Paragraph(str(context.get("delay_part_vendor", 0)), VALUE_STYLE),
            Paragraph(str(context.get("delay_part_force_majeure", 0)), VALUE_STYLE),
        ],
        [
            Paragraph(context.get("comment_mtn", " "), VALUE_STYLE),
            Paragraph(context.get("comment_vendor", " "), VALUE_STYLE),
            Paragraph(context.get("comment_force_majeure", " "), VALUE_STYLE),
        ],
    ]
    repartition_table = Table(repartition_data, colWidths=[176, 176, 178])
    repartition_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("BACKGROUND", (0, 0), (-1, 0), LIGHT_BLUE),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (0, 1), (-1, 1), "CENTER"),
            ]
        )
    )
    elements.append(repartition_table)
    elements.append(Spacer(1, 6))

    # Criteria details table (if available)
    criteria_details: List[Dict[str, Any]] = context.get("criteria_details", [])
    if criteria_details:
        criteria_table_data = [
            [
                Paragraph("Critère", LABEL_STYLE),
                Paragraph("Note (/10)", LABEL_STYLE),
                Paragraph("Description", LABEL_STYLE),
            ]
        ]
        for criterion in criteria_details:
            criteria_table_data.append(
                [
                    Paragraph(str(criterion.get("label", "")), VALUE_STYLE),
                    Paragraph(str(criterion.get("score", "")), VALUE_STYLE),
                    Paragraph(str(criterion.get("description", "")), VALUE_STYLE),
                ]
            )
        criteria_table = Table(criteria_table_data, colWidths=[170, 60, 290])
        criteria_table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                    ("BACKGROUND", (0, 0), (-1, 0), LIGHT_BLUE),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        elements.append(criteria_table)
        elements.append(Spacer(1, 6))

    # Signatures
    elements.append(_build_section_title("SIGNATURES"))
    elements.append(Spacer(1, 4))

    signature_table_data = [
        [Paragraph(label, LABEL_STYLE) for label in SIGNATURE_LABELS],
        [Spacer(1, 40) for _ in SIGNATURE_LABELS],
    ]
    signatures_table = Table(
        signature_table_data,
        colWidths=[105, 105, 105, 105, 105],
        rowHeights=[None, 65],
    )
    signatures_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )
    elements.append(signatures_table)
    elements.append(Spacer(1, 8))

    # Extrait des conditions générales
    elements.append(_build_section_title("EXTRAIT DES CONDITIONS GÉNÉRALES - RETARD DE LIVRAISON"))
    elements.append(Spacer(1, 4))
    retard_condition = (
        "Le délai de livraison étant d'une importance capitale, le Fournisseur reconnaît le droit à MTN-CI, "
        "en cas de retard lui incombant, d'annuler irrévocablement la commande aux torts exclusifs du Fournisseur "
        "ou d'appliquer des pénalités de retard à raison de 0.3% du prix total de la marchandise, par jour calendaire "
        "de retard, sauf cas de force majeure prouvé par le Fournisseur et formellement reconnu par MTN-CI."
    )
    conditions_table = Table(
        [[Paragraph(f"• {retard_condition}", VALUE_STYLE)]],
        colWidths=[530],
    )
    conditions_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.5, colors.black),
                ("BACKGROUND", (0, 0), (-1, -1), colors.whitesmoke),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(conditions_table)

    if user_email:
        elements.append(Spacer(1, 8))
        elements.append(
            Paragraph(
                f"Document généré par : {user_email} le {datetime.now():%d/%m/%Y %H:%M}",
                SMALL_STYLE,
            )
        )

    doc.build(elements)
    buffer.seek(0)
    return buffer
