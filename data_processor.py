"""
Preprocess and normalize Monday.com data to minimize hallucination.
All logic works on in-memory data fetched from API — no local paths.
"""
import re
from datetime import datetime
from typing import Any


# Common date patterns in real-world data
DATE_PATTERNS = [
    (re.compile(r"^\d{4}-\d{2}-\d{2}$"), "%Y-%m-%d"),
    (re.compile(r"^\d{2}/\d{2}/\d{4}$"), "%d/%m/%Y"),
    (re.compile(r"^\d{2}-\d{2}-\d{4}$"), "%d-%m-%Y"),
    (re.compile(r"^\d{1,2}\s+\w+\s+\d{4}$", re.I), None),  # e.g. "15 Jan 2025" - parse flexibly
]


def normalize_value(val: Any) -> str:
    """Normalize a single value: empty -> N/A, strip, consistent empty representation."""
    if val is None:
        return "N/A"
    s = str(val).strip()
    if s.lower() in ("", "nan", "none", "null", "n/a", "-", "na"):
        return "N/A"
    return s


def normalize_date(s: str) -> str:
    """Try to parse and normalize date strings to YYYY-MM-DD for consistency."""
    if not s or normalize_value(s) == "N/A":
        return "N/A"
    s = str(s).strip()
    for pattern, fmt in DATE_PATTERNS:
        if pattern.match(s):
            if fmt:
                try:
                    return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
                except ValueError:
                    pass
            else:
                try:
                    from dateutil import parser as date_parser
                    return date_parser.parse(s).strftime("%Y-%m-%d")
                except Exception:
                    pass
            break
    return s


def safe_float(s: Any, default: float = 0.0) -> float:
    """Parse number; return default for invalid/missing. Reduces hallucination from bad numbers."""
    if s is None or (isinstance(s, str) and normalize_value(s) == "N/A"):
        return default
    try:
        cleaned = re.sub(r"[^\d.\-eE]", "", str(s))
        if not cleaned:
            return default
        return float(cleaned)
    except (ValueError, TypeError):
        return default


def normalize_row(row: dict, date_columns: set[str], numeric_columns: set[str]) -> dict:
    """Normalize one row: dates, numbers, empty values."""
    out = {}
    for k, v in row.items():
        if k.startswith("_"):
            out[k] = v
            continue
        n = normalize_value(v)
        if k in date_columns and n != "N/A":
            n = normalize_date(v) if v else "N/A"
        if k in numeric_columns and n != "N/A":
            out[k] = safe_float(v)
        else:
            out[k] = n
    return out


# Column names that are typically dates (match CSV / Monday board titles)
WORK_ORDER_DATE_COLUMNS = {
    "Data Delivery Date", "Date of PO/LOI", "Probable Start Date", "Probable End Date",
    "Last invoice date", "Expected Billing Month", "Actual Billing Month", "Actual Collection Month",
    "Collection Date",
}
DEAL_DATE_COLUMNS = {"Close Date (A)", "Tentative Close Date", "Created Date"}

# Columns that are numeric (amounts, quantities)
WORK_ORDER_NUMERIC = {
    "Amount in Rupees (Excl of GST) (Masked)", "Amount in Rupees (Incl of GST) (Masked)",
    "Billed Value in Rupees (Excl of GST.) (Masked)", "Billed Value in Rupees (Incl of GST.) (Masked)",
    "Collected Amount in Rupees (Incl of GST.) (Masked)",
    "Amount to be billed in Rs. (Exl. of GST) (Masked)", "Amount to be billed in Rs. (Incl of GST) (Masked)",
    "Amount Receivable (Masked)", "Quantity by Ops", "Quantities as per PO", "Quantity billed (till date)",
    "Balance in quantity",
}
DEAL_NUMERIC = {"Masked Deal value", "Closure Probability"}


def normalize_work_orders(rows: list[dict]) -> list[dict]:
    """Normalize work order rows: dates, numbers, nulls. Filter duplicate header-like rows."""
    if not rows:
        return []
    out = []
    for r in rows:
        # Skip rows that look like header repeats (e.g. "Deal Status" in first data column)
        name = (r.get("Deal name masked") or r.get("_item_name") or "").strip()
        if name and name in ("Deal Status", "Deal name masked", "Deal Name"):
            continue
        date_cols = WORK_ORDER_DATE_COLUMNS | {k for k in r if "date" in k.lower() or "month" in k.lower()}
        num_cols = WORK_ORDER_NUMERIC | {k for k in r if "amount" in k.lower() or "quantity" in k.lower()}
        out.append(normalize_row(r, date_cols, num_cols))
    return out


def normalize_deals(rows: list[dict]) -> list[dict]:
    """Normalize deal rows and filter duplicate header rows."""
    if not rows:
        return []
    out = []
    for r in rows:
        name = (r.get("Deal Name") or r.get("_item_name") or "").strip()
        if name and name in ("Deal Status", "Deal Name", "Close Date (A)"):
            continue
        date_cols = DEAL_DATE_COLUMNS | {k for k in r if "date" in k.lower()}
        num_cols = DEAL_NUMERIC | {k for k in r if "value" in k.lower() or "probability" in k.lower()}
        out.append(normalize_row(r, date_cols, num_cols))
    return out


def build_summary_for_llm(work_orders: list[dict], deals: list[dict]) -> str:
    """
    Build a compact, factual summary and key metrics from the data.
    Feeding this to the LLM reduces hallucination by grounding answers in real numbers.
    """
    wo = work_orders
    dl = deals

    def _get_value(row: dict, keys: list[str], contains: list[str] | None = None) -> Any:
        """Fetch a value by exact key or by contains-match (case-insensitive)."""
        for k in keys:
            if k in row:
                return row.get(k)
        if contains:
            for rk in row.keys():
                rkl = rk.lower()
                if all(c.lower() in rkl for c in contains):
                    return row.get(rk)
        return None

    # Work order metrics (use normalized numeric columns where available)
    wo_total = len(wo)
    sectors_wo = {}
    status_wo = {}
    for r in wo:
        s = normalize_value(_get_value(r, ["Sector", "Sector/service"], contains=["sector"]))
        sectors_wo[s] = sectors_wo.get(s, 0) + 1
        st = normalize_value(
            _get_value(
                r,
                ["Execution Status", "WO Status (billed)", "Billing Status", "Invoice Status"],
                contains=["status"],
            )
        )
        status_wo[st] = status_wo.get(st, 0) + 1

    total_billed = 0.0
    total_receivable = 0.0
    for r in wo:
        billed_val = _get_value(
            r,
            ["Billed Value in Rupees (Excl of GST.) (Masked)"],
            contains=["billed", "excl"],
        )
        recv_val = _get_value(
            r,
            ["Amount Receivable (Masked)"],
            contains=["receivable"],
        )
        total_billed += safe_float(billed_val)
        total_receivable += safe_float(recv_val)

    # Deals metrics
    deals_open = [r for r in dl if normalize_value(_get_value(r, ["Deal Status"], contains=["deal", "status"])).lower() == "open"]
    deals_dead = [r for r in dl if normalize_value(_get_value(r, ["Deal Status"], contains=["deal", "status"])).lower() == "dead"]
    sector_deals = {}
    stage_deals = {}
    for r in dl:
        s = normalize_value(_get_value(r, ["Sector/service", "Sector"], contains=["sector"]))
        sector_deals[s] = sector_deals.get(s, 0) + 1
        st = normalize_value(_get_value(r, ["Deal Stage"], contains=["stage"]))
        stage_deals[st] = stage_deals.get(st, 0) + 1

    pipeline_value = 0.0
    for r in deals_open:
        pipeline_value += safe_float(_get_value(r, ["Masked Deal value"], contains=["deal", "value"]))
    pipeline_by_sector = {}
    for r in deals_open:
        s = normalize_value(_get_value(r, ["Sector/service", "Sector"], contains=["sector"]))
        pipeline_by_sector[s] = pipeline_by_sector.get(s, 0) + safe_float(_get_value(r, ["Masked Deal value"], contains=["deal", "value"]))

    lines = [
        "## Work Orders (execution data)",
        f"- Total work orders: {wo_total}",
        f"- Sectors (count): {dict(sectors_wo)}",
        f"- Execution status (count): {dict(status_wo)}",
        f"- Total billed value (excl GST): {total_billed:.2f}",
        f"- Total amount receivable: {total_receivable:.2f}",
        "",
        "## Deals (pipeline)",
        f"- Total deals: {len(dl)} (Open: {len(deals_open)}, Dead: {len(deals_dead)})",
        f"- Pipeline value (open deals, masked): {pipeline_value:.2f}",
        f"- Deals by sector (count): {dict(sector_deals)}",
        f"- Deals by stage (count): {dict(stage_deals)}",
        f"- Pipeline by sector (masked value): {dict(pipeline_by_sector)}",
    ]
    return "\n".join(lines)


def _sample_rows(rows: list[dict], preferred_keys: list[str], n: int) -> str:
    """Format first n rows as readable lines for LLM context. Uses preferred keys if present, else all non-internal keys."""
    out = []
    for i, r in enumerate(rows[:n]):
        keys = [k for k in preferred_keys if k in r]
        if not keys:
            keys = [k for k in r if not k.startswith("_")]
        parts = [f"{k}: {r.get(k, 'N/A')}" for k in keys[:10]]
        out.append(f"  Row{i+1}: " + " | ".join(parts))
    return "\n".join(out) if out else "  (none)"


def build_data_context(work_orders: list[dict], deals: list[dict], max_wo_rows: int = 80, max_deal_rows: int = 80) -> str:
    """
    Build a string of summary + sample rows for the LLM so it can answer from actual data.
    Limit rows to avoid token overflow and keep context grounded.
    """
    wo = normalize_work_orders(work_orders)[:max_wo_rows]
    dl = normalize_deals(deals)[:max_deal_rows]
    summary = build_summary_for_llm(work_orders, deals)
    wo_keys = ["Deal name masked", "Sector", "Execution Status", "Amount Receivable (Masked)", "Billing Status", "_item_name"]
    deal_keys = ["Deal Name", "Deal Status", "Deal Stage", "Sector/service", "Masked Deal value", "Tentative Close Date", "_item_name"]
    lines = [
        summary,
        "",
        "## Sample Work Order rows (key columns)",
        _sample_rows(wo, wo_keys, 25),
        "",
        "## Sample Deal rows (key columns)",
        _sample_rows(dl, deal_keys, 25),
    ]
    return "\n".join(lines)
