"""But:
- Construire les données pour la fiche d'amendement de pénalité.

Étapes:
- Partir du contexte de pénalité standard (montants, dates, jours, etc.).
- Ajouter les champs propres à l'amendement (doléance, proposition, nouveau montant, statut).

Entrées:
- Objet `NumeroBonCommande`.

Sorties:
- Dictionnaire `context` prêt pour le PDF d'amendement.
"""
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
    """But:
    - Préparer le contexte nécessaire à la fiche d'amendement.

    Étapes:
    - Récupérer le contexte de pénalité de base.
    - Normaliser les montants et compléter avec les champs d'amendement.

    Entrées:
    - `bon` (NumeroBonCommande).

    Sorties:
    - `context` (dict) avec valeurs par défaut simples.
    """
    # 1) Contexte de base (calculé depuis les fichiers)
    base = collect_penalty_context(bon)

    penalty_due = _as_decimal(base.get("penalties_due"))

    # 2) Contexte d'amendement avec valeurs par défaut prêtes à afficher
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
