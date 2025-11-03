"""Collects data for the delivery evaluation PDF."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.utils import timezone

from .models import NumeroBonCommande, VendorEvaluation
from .penalty_data import (
    _get_first_occurrence_contenu,
    _get_prefetched_list,
    _get_value_tolerant,
    _parse_date,
)


CRITERIA_LABELS = {
    "delivery_compliance": "Conformité livraison",
    "delivery_timeline": "Respect des délais",
    "advising_capability": "Capacité de conseil",
    "after_sales_qos": "Service après-vente",
    "vendor_relationship": "Relation fournisseur",
}


def _format_decimal(value: Decimal | float | int | str | None) -> Decimal:
    if value is None:
        return Decimal("0.00")
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except Exception:
        return Decimal("0.00")


def _get_project_manager(contenu: Dict[str, Any]) -> str:
    return (
        _get_value_tolerant(
            contenu,
            exact_candidates=(
                "Project Manager",
                " Project Manager",
                "Project Manager Name",
                "Project_Manager",
                "ProjectManager",
                "PM",
            ),
            tokens=("project", "manager"),
        )
        or "N/A"
    )


def _get_order_description(contenu: Dict[str, Any]) -> str:
    return (
        _get_value_tolerant(
            contenu,
            exact_candidates=("Order Description",),
            tokens=("order", "description"),
        )
        or "N/A"
    )


def _resolve_supplier(contenu: Dict[str, Any], fallback: str) -> str:
    supplier = _get_value_tolerant(contenu, exact_candidates=("Supplier",), tokens=("supplier",))
    return supplier or fallback or "N/A"


def _resolve_currency(contenu: Dict[str, Any], fallback: str | None) -> str:
    currency = _get_value_tolerant(contenu, exact_candidates=("Currency",))
    return currency or fallback or "N/A"


def collect_delay_evaluation_context(bon: NumeroBonCommande) -> Dict[str, Any]:
    """Assemble toutes les données nécessaires à la fiche d'évaluation des délais."""
    contenu = _get_first_occurrence_contenu(bon)

    supplier = _resolve_supplier(contenu, getattr(bon, "fournisseur", ""))
    currency = _resolve_currency(contenu, getattr(bon, "devise", None))
    project_manager = _get_project_manager(contenu)
    order_description = _get_order_description(contenu)

    creation_raw = _get_value_tolerant(contenu, exact_candidates=("Creation Date",))
    pip_end_raw = _get_value_tolerant(contenu, exact_candidates=("PIP END DATE",))
    actual_end_raw = _get_value_tolerant(contenu, exact_candidates=("ACTUAL END DATE",))

    creation_date = _parse_date(creation_raw)
    pip_end_date = _parse_date(pip_end_raw)
    actual_end_date = _parse_date(actual_end_raw)

    po_amount_raw = _get_value_tolerant(
        contenu,
        exact_candidates=("Total", "PO Amount", "PO AMOUNT/MONTANT BC"),
        tokens=("po", "amount"),
    )
    po_amount = _format_decimal(po_amount_raw)

    total_delay_days = 0
    if pip_end_date and actual_end_date:
        total_delay_days = max((actual_end_date - pip_end_date).days, 0)

    timeline = getattr(bon, "timeline_delay", None)
    delay_part_mtn = timeline.delay_part_mtn if timeline else 0
    delay_part_vendor = timeline.delay_part_vendor if timeline else 0
    delay_part_force_majeure = timeline.delay_part_force_majeure if timeline else 0

    comment_mtn = (timeline.comment_mtn if timeline and timeline.comment_mtn else "").strip()
    comment_vendor = (timeline.comment_vendor if timeline and timeline.comment_vendor else "").strip()
    comment_force_majeure = (
        timeline.comment_force_majeure if timeline and timeline.comment_force_majeure else ""
    ).strip()

    vendor_evaluation = (
        VendorEvaluation.objects.filter(bon_commande=bon).order_by("-date_evaluation").first()
    )

    criteria_details: List[Dict[str, Any]] = []
    total_score = 0
    final_rating = Decimal("0.00")
    evaluation_date: Optional[datetime] = None
    evaluator_name = "N/A"
    observation = ""

    if vendor_evaluation:
        evaluation_date = vendor_evaluation.date_evaluation
        final_rating = vendor_evaluation.vendor_final_rating
        observation = getattr(vendor_evaluation, "comments", "") or ""

        evaluator = vendor_evaluation.evaluator
        if evaluator:
            evaluator_name = evaluator.get_full_name() or evaluator.email or "Utilisateur"

        scores = [
            vendor_evaluation.delivery_compliance,
            vendor_evaluation.delivery_timeline,
            vendor_evaluation.advising_capability,
            vendor_evaluation.after_sales_qos,
            vendor_evaluation.vendor_relationship,
        ]
        total_score = sum(filter(lambda s: s is not None, scores))

        for field_name, label in CRITERIA_LABELS.items():
            score = getattr(vendor_evaluation, field_name, None)
            if score is None:
                continue
            description = vendor_evaluation.get_criteria_description(field_name, score)
            criteria_details.append({
                "key": field_name,
                "label": label,
                "score": score,
                "description": description,
            })
    else:
        final_rating = Decimal("0.00")

    context: Dict[str, Any] = {
        "po_number": bon.numero,
        "supplier": supplier,
        "currency": currency,
        "po_amount": po_amount,
        "creation_date": creation_date,
        "pip_end_date": pip_end_date,
        "actual_end_date": actual_end_date,
        "total_delay_days": total_delay_days,
        "project_manager": project_manager,
        "order_description": order_description,
        "delay_part_mtn": delay_part_mtn,
        "delay_part_vendor": delay_part_vendor,
        "delay_part_force_majeure": delay_part_force_majeure,
        "comment_mtn": comment_mtn,
        "comment_vendor": comment_vendor,
        "comment_force_majeure": comment_force_majeure,
        "evaluation_date": evaluation_date,
        "evaluator_name": evaluator_name,
        "total_score": total_score,
        "final_rating": final_rating,
        "criteria_details": criteria_details,
        "observation": observation,
    }

    return context
