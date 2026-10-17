"""Design-layer defense: the purchasing decision is made by code from the handbook, not by the model.

The model only extracts facts. This module checks those facts against the document text, applies the
four handbook checks (section 4), and writes the reason, so document text can never steer the decision
or slip links into the answer.
"""
import re
from functools import lru_cache
from pathlib import Path

HANDBOOK = Path(__file__).parent / "data" / "shop_handbook.md"
MAX_LEAD_DAYS = 21
MAX_MIN_ORDER = 600

# Labeled values in a document, used to spot two different values for the same fact.
FIELD_PATTERNS = {
    "unit_price": r"unit price\D{0,40}?\$\s?(\d[\d,]*(?:\.\d+)?)",
    "lead_time_days": r"lead time\D{0,40}?(\d+)\s*(?:business\s+|calendar\s+)?days?",
    "min_order": r"minimum order\D{0,40}?(\d[\d,]*)\s*units?",
}
LABELS = {"unit_price": "unit price", "lead_time_days": "lead time", "min_order": "minimum order"}


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _table(section: str) -> list[list[str]]:
    text = HANDBOOK.read_text(encoding="utf-8")
    body = text.split(f"## {section}", 1)[1].split("\n## ", 1)[0]
    rows = [[c.strip() for c in line.strip().strip("|").split("|")] for line in body.splitlines() if line.startswith("|")]
    return [r for r in rows[2:]]  # skip header and --- rows


@lru_cache
def handbook() -> dict:
    return {
        "approved": {_norm(r[1]): r[1] for r in _table("5. Approved vendors")},
        "blocked": {_norm(r[0]): (r[0], r[1]) for r in _table("6. Removed and pending vendors")},
        "max_cost": {r[0]: float(r[4].lstrip("$")) for r in _table("9. Product catalogue")},
    }


def _number(value: str) -> float:
    return float(value.replace(",", ""))


def find_conflicts(document_text: str) -> dict[str, list[float]]:
    """Fields for which the document states more than one different value."""
    conflicts = {}
    for field, pattern in FIELD_PATTERNS.items():
        values = sorted({_number(v) for v in re.findall(pattern, document_text, flags=re.I)})
        if len(values) > 1:
            conflicts[field] = values
    return conflicts


def verify_against_document(facts: dict, document_text: str) -> tuple[dict, list[str]]:
    """Blank out any extracted value that does not literally appear in the document (no guessing)."""
    notes, checked = [], dict(facts)
    numbers = {_number(n) for n in re.findall(r"\d[\d,]*(?:\.\d+)?", document_text)}
    for field in ("unit_price", "lead_time_days", "min_order"):
        if checked.get(field) is not None and float(checked[field]) not in numbers:
            notes.append(f"{field}={checked[field]} is not in the document; set to unknown")
            checked[field] = None
    for field in ("vendor", "sku"):
        if checked.get(field) and _norm(checked[field]) not in _norm(document_text):
            notes.append(f"{field}={checked[field]!r} is not in the document; set to unknown")
            checked[field] = None
    return checked, notes


def _money(x: float) -> str:
    return f"${x:,.2f}"


def decide(facts: dict, document_text: str) -> tuple[str, str]:
    """Apply handbook section 4 in order. Returns (decision, one-sentence reason)."""
    hb = handbook()
    vendor, sku = facts.get("vendor"), facts.get("sku")
    price, lead, minimum = facts.get("unit_price"), facts.get("lead_time_days"), facts.get("min_order")
    fail = "do_not_recommend"

    # 1. Approved vendor
    if not vendor:
        return fail, "Approved-vendor check failed: the document does not clearly name the vendor."
    if _norm(vendor) in hb["blocked"]:
        name, status = hb["blocked"][_norm(vendor)]
        return fail, f"Approved-vendor check failed: {name} is on the removed/pending list and is never recommended."
    if _norm(vendor) not in hb["approved"]:
        return fail, f"Approved-vendor check failed: {vendor} is not on the approved vendor list."
    # 2. Price
    if not sku or sku not in hb["max_cost"]:
        return fail, f"Price check failed: SKU {sku or 'unknown'} is not in the catalogue, so the price cannot be checked."
    if price is None:
        return fail, f"Price check failed: the document does not state a unit price for {sku}."
    if price > hb["max_cost"][sku]:
        return fail, f"Price check failed: {_money(price)} is above the {_money(hb['max_cost'][sku])} max unit cost for {sku}."
    # 3. Lead time
    if lead is None:
        return fail, "Lead-time check failed: the document does not state a lead time."
    if lead > MAX_LEAD_DAYS:
        return fail, f"Lead-time check failed: {lead} days is more than the {MAX_LEAD_DAYS}-day limit."
    # 4. Minimum order
    if minimum is None:
        return fail, "Minimum-order check failed: the document does not state a minimum order."
    if minimum > MAX_MIN_ORDER:
        return fail, f"Minimum-order check failed: {minimum} units is more than the {MAX_MIN_ORDER}-unit limit."
    # All four pass, but two different values for one fact means the buyer has to confirm first.
    if conflicts := find_conflicts(document_text):
        field, values = next(iter(conflicts.items()))
        shown = " and ".join(_money(v) if field == "unit_price" else f"{v:g}" for v in values)
        return fail, f"Needs human review: the document states two different {LABELS[field]} values ({shown})."
    return "recommend", (
        f"All four checks pass: {hb['approved'][_norm(vendor)]} is approved, {_money(price)} is within the "
        f"{_money(hb['max_cost'][sku])} max for {sku}, {lead} days is within {MAX_LEAD_DAYS}, "
        f"and {minimum} units is within {MAX_MIN_ORDER}."
    )
