"""Data collector for the Penalty Amendment Sheet."""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict

from .penalty_data import collect_penalty_context


def _as_decimal(value: Any) -> Decimal:
    try:
        if isinstance(value, Decimal):
            return value
        if value is None:
            return Decimal("0.00")
        return Decimal(str(value).replace(" ", ""))
    except Exception:
        return Decimal("0.00")


def collect_penalty_amendment_context(bon) -> Dict[str, Any]:
    """Assemble the context required to render the penalty amendment sheet."""
    base = collect_penalty_context(bon)

    penalty_due = _as_decimal(base.get("penalties_due"))

    context: Dict[str, Any] = {
        "po_number": base.get("po_number", "N/A"),
        "supplier": base.get("supplier", "N/A"),
        "po_amount": _as_decimal(base.get("po_amount")),
        "currency": base.get("currency", "N/A"),
        "order_date": base.get("creation_date"),
        "order_description": base.get("order_description", "N/A"),
        "pip_end_date": base.get("pip_end_date"),
        "actual_end_date": base.get("actual_end_date"),
        "total_penalty_days": base.get("total_penalty_days", 0) or 0,
        "delay_part_mtn": base.get("delay_part_mtn", 0) or 0,
        "delay_part_vendor": base.get("delay_part_vendor", 0) or 0,
        "delay_part_force_majeure": base.get("delay_part_force_majeure", 0) or 0,
        "penalty_due": penalty_due,
        "requester": base.get("project_coordinator") or "N/A",
        "supplier_plea": "",
        "pm_proposal": "",
        "penalty_status": None,
        "new_penalty_due": penalty_due,
    }

    return context
