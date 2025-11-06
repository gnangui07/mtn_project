"""But:
- Rassembler les données nécessaires à la fiche de pénalité depuis les lignes importées.

Étapes:
- Chercher la première ligne correspondant au PO.
- Extraire les champs utiles (montants, dates, fournisseur, etc.).
- Calculer les pénalités (taux, plafonds, jours, quotités).

Entrées:
- Objet `NumeroBonCommande` avec accès à ses fichiers/lignes associés.

Sorties:
- Dictionnaire `context` prêt pour la génération du PDF de pénalité.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, Optional, Tuple

from django.db.models import Prefetch

from .models import LigneFichier, NumeroBonCommande, TimelineDelay


# ---------------------------------------------------------------------------
# Helpers copied/adapted from views_export.py to work locally without Excel export
# ---------------------------------------------------------------------------

def _normalize_header(header: str) -> str:
    """Normalize a column header for tolerant comparisons."""
    # Idée simple: on met les titres en minuscules et on enlève les caractères
    # spéciaux pour mieux les comparer entre fichiers différents.
    return " ".join(str(header).strip().lower().replace("_", " ").replace("-", " ").split())


def _find_order_key(contenu: Dict[str, Any]) -> Optional[str]:
    """Locate the key that represents the PO number in a ligne."""
    # On cherche la colonne qui contient le numéro de commande (PO).
    # Les fichiers peuvent utiliser des noms différents (Order, Commande, BC, ...).
    if "Order" in contenu:
        return "Order"
    for key in contenu.keys():
        if not key:
            continue
        norm = _normalize_header(key)
        if any(token in norm for token in ("order", "commande", "bon")) or norm == "bc":
            return key
    return None


def _get_value_tolerant(
    contenu: Dict[str, Any],
    exact_candidates: Optional[Tuple[str, ...]] = None,
    tokens: Optional[Tuple[str, ...]] = None,
) -> Optional[Any]:
    """Retrieve a value from contenu using tolerant header matching."""
    # But simple: retrouver une valeur même si l'en-tête varie un peu d'un fichier à l'autre.
    if not contenu:
        return None

    normalized = {_normalize_header(k): (k, v) for k, v in contenu.items() if k}

    if exact_candidates:
        for candidate in exact_candidates:
            key = _normalize_header(candidate)
            if key in normalized:
                return normalized[key][1]

    if tokens:
        needed = tuple(_normalize_header(tok) for tok in tokens)
        for normalized_key, (_orig, value) in normalized.items():
            if all(tok in normalized_key for tok in needed):
                return value

    return None


def _parse_date(value: Any) -> Optional[datetime]:
    """Parse various date formats found in imported files."""
    # On accepte plusieurs formats de date courants. Si rien ne marche, on renvoie None.
    if not value:
        return None

    raw = str(value).strip()
    if not raw:
        return None

    formats = (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d/%m/%Y %H:%M:%S",
    )
    for fmt in formats:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _get_prefetched_list(instance: Any, attr: str):
    cache = getattr(instance, "_prefetched_objects_cache", None)
    if cache and attr in cache:
        return list(cache[attr])
    return None


def _get_first_occurrence_contenu(bon: NumeroBonCommande) -> Dict[str, Any]:
    """Return the first ligne contenu associated with the PO number."""
    # Idée simple: on parcourt les fichiers et leurs lignes jusqu'à trouver la première
    # ligne qui correspond au bon de commande demandé. Cette ligne sert de référence.
    fichiers = _get_prefetched_list(bon, "fichiers")
    if fichiers is None:
        fichiers = list(
            bon.fichiers.all().prefetch_related(
                Prefetch(
                    "lignes",
                    queryset=LigneFichier.objects.only("numero_ligne", "contenu").order_by("numero_ligne"),
                )
            )
        )
    fichiers.sort(key=lambda f: f.date_importation)

    for fichier in fichiers:
        lignes = _get_prefetched_list(fichier, "lignes")
        if lignes is None:
            lignes = list(
                fichier.lignes.only("numero_ligne", "contenu").order_by("numero_ligne")
            )
        for ligne in lignes:
            contenu = ligne.contenu or {}
            order_key = _find_order_key(contenu)
            if not order_key:
                continue
            order_value = str(contenu.get(order_key, "")).strip()
            if order_value and order_value == bon.numero:
                # On s'arrête dès qu'on trouve une ligne du bon.
                return contenu
    return {}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def collect_penalty_context(bon: NumeroBonCommande) -> Dict[str, Any]:
    """But:
    - Assembler toutes les données nécessaires à la fiche de pénalité d’un PO.

    Étapes:
    - Retrouver la première ligne du PO.
    - Extraire supplier/currency/dates/description/montant.
    - Calculer jours de retard, taux, plafonds et pénalité due.

    Entrées:
    - `bon` (NumeroBonCommande) avec M2M `fichiers` et leurs `lignes`.

    Sorties:
    - `context` (dict) complet pour le PDF et l’API.
    """
    # 1) Trouver la première ligne de données correspondant au bon
    contenu = _get_first_occurrence_contenu(bon)

    # 2) Lire les infos de base (fournisseur, devise, dates, description...)
    supplier = _get_value_tolerant(contenu, exact_candidates=("Supplier",), tokens=("supplier",))
    currency = _get_value_tolerant(contenu, exact_candidates=("Currency",))
    creation_date_raw = _get_value_tolerant(contenu, exact_candidates=("Creation Date",))
    pip_end_raw = _get_value_tolerant(contenu, exact_candidates=("PIP END DATE",))
    actual_end_raw = _get_value_tolerant(contenu, exact_candidates=("ACTUAL END DATE",))
    project_coordinator = _get_value_tolerant(
        contenu,
        tokens=("project", "coordinator"),
    )
    order_description = _get_value_tolerant(
        contenu,
        exact_candidates=("Order Description",),
        tokens=("order", "description"),
    )

    # 3) Montant du PO (avec tolérance sur le nom de colonne)
    po_amount_raw = _get_value_tolerant(
        contenu,
        exact_candidates=("Total", "PO Amount", "PO AMOUNT/MONTANT BC"),
        tokens=("po", "amount"),
    )
    try:
        po_amount = Decimal(str(po_amount_raw).replace(" ", ""))
    except Exception:
        po_amount = bon.montant_total() if hasattr(bon, "montant_total") else Decimal("0.00")
    po_amount = po_amount.quantize(Decimal("0.01")) if isinstance(po_amount, Decimal) else Decimal("0.00")

    # 4) Convertir les dates et calculer le nombre de jours de retard
    creation_date = _parse_date(creation_date_raw)
    pip_end_date = _parse_date(pip_end_raw)
    actual_end_date = _parse_date(actual_end_raw)

    total_penalty_days = 0
    if pip_end_date and actual_end_date:
        delta = (actual_end_date - pip_end_date).days
        total_penalty_days = max(delta, 0)

    # 5) Prendre en compte la répartition des retards (MTN / Force majeure / Prestataire)
    timeline: Optional[TimelineDelay] = getattr(bon, "timeline_delay", None)
    delay_mtn = timeline.delay_part_mtn if timeline else 0
    delay_force_majeure = timeline.delay_part_force_majeure if timeline else 0
    delay_vendor = timeline.delay_part_vendor if timeline else 0
    quotite_realisee = timeline.quotite_realisee if timeline else Decimal("100.00")
    quotite_non_realisee = Decimal("100.00") - quotite_realisee
    if quotite_non_realisee < Decimal("0"):
        quotite_non_realisee = Decimal("0")

    # 6) Taux de pénalité (0,30% par jour imputable au prestataire)
    penalty_rate = Decimal("0.30")  # 0,30%

    quotite_factor = (Decimal("100.00") - quotite_realisee) / Decimal("100")
    if quotite_factor < Decimal("0"):
        quotite_factor = Decimal("0")

    # 7) Calcul des pénalités, puis plafonnement à 10% du montant du PO
    penalties_calculated = (
        po_amount
        * (penalty_rate / Decimal("100"))
        * Decimal(delay_vendor or 0)
        * quotite_factor
    ).quantize(Decimal("0.01"))
    penalty_cap = (po_amount * Decimal("0.10")).quantize(Decimal("0.01"))
    penalties_due = min(penalties_calculated, penalty_cap)

    # 8) Préparer le dictionnaire final pour le PDF et l'API
    context = {
        "po_number": bon.numero,
        "supplier": supplier or "N/A",
        "currency": currency or "N/A",
        "creation_date": creation_date,
        "pip_end_date": pip_end_date,
        "actual_end_date": actual_end_date,
        "total_penalty_days": total_penalty_days,
        "delay_part_mtn": delay_mtn,
        "delay_part_force_majeure": delay_force_majeure,
        "delay_part_vendor": delay_vendor,
        "po_amount": po_amount,
        "penalty_rate": penalty_rate,
        "project_coordinator": project_coordinator or "N/A",
        "order_description": order_description or "N/A",
        "quotite_realisee": quotite_realisee,
        "quotite_non_realisee": quotite_non_realisee,
        "quotite_factor": quotite_factor,
        "observation": "",
        "penalties_calculated": penalties_calculated,
        "penalty_cap": penalty_cap,
        "penalties_due": penalties_due,
    }

    return context
