from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

import pandas as pd

from jobspy.config import default_config, Config

# Sales role categories (lowercase keys for matching)
SALES_HIGH = {
    "sdr",
    "bdR".lower(),
    "sales development representative",
    "business development representative",
    "account executive",
    "sales representative",
    "sales operations",
    "sales support",
    "sales coordinator",
    "revenue operations",
    "inside sales",
    "enterprise sales",
    "appointment setter",
}

SALES_MEDIUM = {
    "customer success",
    "customer success manager",
    "account manager",
    "partnership",
    "partner manager",
    "client success",
    "customer growth",
    "renewals",
    "commercial operations",
}

SALES_LOW = {
    "marketing",
    "engineering",
    "software",
    "developer",
    "hr",
    "finance",
    "accounting",
    "support",
    "it support",
    "data analyst",
    "project manager",
    "customer support",
}

TZ_PASS = {"cet", "cest", "utc", "gmt", "bst"}
TZ_REVIEW = {"est", "edt", "cst", "cdt", "pst", "pdt"}


def _text_contains_any(text: str, toks: List[str]) -> List[str]:
    found = []
    t = (text or "").lower()
    for tok in toks:
        if tok.lower() in t:
            found.append(tok)
    return found


def classify_sales_relevance(normalized_row: Dict[str, Any], cfg: Optional[Config] = None) -> Dict[str, Any]:
    cfg = cfg or default_config()
    title = (normalized_row.get("normalized_title") or "")
    job_function = (normalized_row.get("job_function") or "")
    desc = (normalized_row.get("description") or "")

    evidence: List[str] = []
    level = "NONE"

    # check title and job_function tokens for HIGH
    all_text = " ".join([title, str(job_function).lower(), str(desc).lower()])

    for tok in SALES_HIGH:
        if tok in all_text:
            evidence.append(f"high_title_or_fn:{tok}")
            level = "HIGH"
            break

    if level != "HIGH":
        for tok in SALES_MEDIUM:
            if tok in all_text:
                evidence.append(f"medium_title_or_fn:{tok}")
                level = "MEDIUM"
                break

    if level == "NONE":
        for tok in SALES_LOW:
            if tok in all_text:
                evidence.append(f"low_title_or_fn:{tok}")
                level = "LOW"
                break

    # detect explicit sales keywords in description to boost
    sales_indicators = [
        "quota",
        "quota-carrying",
        "cold call",
        "outbound",
        "prospect",
        "prospecting",
        "lead generation",
        "closing deals",
        "pipeline",
        "revenue",
        "upsell",
        "cross-sell",
        "renewal",
        "commission",
    ]
    for si in sales_indicators:
        if si in desc.lower():
            evidence.append(f"desc_indicator:{si}")
            if level == "NONE":
                level = "MEDIUM"

    return {
        "sales_relevance_level": level,
        "sales_relevance_evidence": evidence,
    }


def _find_explicit_geographic_exclusion(text: str) -> Optional[str]:
    if not text:
        return None
    t = text.lower()
    # direct patterns: 'us only', 'us candidates only', 'only us', 'only us candidates'
    m = re.search(r"\b([a-zA-Z ]+?) only\b", t)
    if m:
        # e.g., 'us only', 'europe only'
        region = m.group(1).strip()
        return region
    # patterns for excluding: 'excluding X', 'except X', 'exclude X', 'excluding: X', 'excluding (X)'
    m = re.search(r"\b(exclud(?:e|ing|ed)|except(?: for)?|excluding)\b\s*[:\-]?\s*([a-zA-Z ,]+)", t)
    if m:
        region = m.group(2).strip()
        return region
    # 'global, but US candidates only' -> handled by first pattern matching 'US only'
    return None


def classify_geographic_eligibility(normalized_row: Dict[str, Any], cfg: Optional[Config] = None) -> Dict[str, Any]:
    cfg = cfg or default_config()
    desc = (normalized_row.get("description") or "")
    loc_display = (normalized_row.get("normalized_location") or {}).get("display") or ""
    combined = " ".join([desc or "", str(loc_display) or ""]).lower()

    evidence: List[str] = []

    # 1) explicit exclusion check (highest precedence)
    excl = _find_explicit_geographic_exclusion(combined)
    if excl:
        evidence.append(f"explicit_exclusion:{excl}")
        return {"geographic_eligibility": "REJECT", "evidence": evidence, "source_field": "description|location"}

    # 2) positive signals (user-country inclusion / worldwide / EMEA / Africa)
    positives = ["worldwide", "world wide", "global", "emea", "africa", "algeria"]
    for p in positives:
        if p in combined:
            evidence.append(f"geo_positive:{p}")
            return {"geographic_eligibility": "PASS", "evidence": evidence, "source_field": "description|location"}

    # 3) europe-only -> REVIEW
    if "europe only" in combined or "remote in europe only" in combined or "europe-only" in combined:
        evidence.append("europe_only")
        return {"geographic_eligibility": "REVIEW", "evidence": evidence, "source_field": "description|location"}

    # 4) ambiguous -> REVIEW
    return {"geographic_eligibility": "REVIEW", "evidence": [], "source_field": "description|location"}


def classify_posting_age(normalized_row: Dict[str, Any], cfg: Optional[Config] = None) -> Dict[str, Any]:
    cfg = cfg or default_config()
    days = normalized_row.get("days_since_posted")
    if days is None:
        return {"posting_age": "REVIEW", "evidence": ["missing_date"]}
    try:
        days_i = int(days)
    except Exception:
        return {"posting_age": "REVIEW", "evidence": ["invalid_date"]}
    if days_i <= cfg.REVIEW_WINDOW_DAYS:
        return {"posting_age": "PASS", "evidence": [f"days:{days_i}"]}
    return {"posting_age": "REJECT", "evidence": [f"days:{days_i}"]}


def classify_salary(normalized_row: Dict[str, Any], cfg: Optional[Config] = None) -> Dict[str, Any]:
    cfg = cfg or default_config()
    # salary_availability from cleaning
    availability = normalized_row.get("salary_availability")
    commission_only = normalized_row.get("commission_only", False)
    usd_min = normalized_row.get("salary_monthly_min_usd")

    evidence: List[str] = []

    if commission_only:
        evidence.append("commission_only_detected")
        return {"salary_qualification": "REJECT", "evidence": evidence}

    if availability == "UNKNOWN":
        evidence.append("no_salary_provided")
        return {"salary_qualification": "UNKNOWN", "evidence": evidence}

    if usd_min is None:
        evidence.append("no_usd_value")
        return {"salary_qualification": "UNKNOWN", "evidence": evidence}

    if usd_min >= cfg.MIN_SALARY_USD_PER_MONTH:
        evidence.append(f"usd_min:{usd_min}")
        return {"salary_qualification": "PASS", "evidence": evidence}

    evidence.append(f"usd_min_below:{usd_min}")
    return {"salary_qualification": "REVIEW", "evidence": evidence}


def classify_timezone_compatibility(normalized_row: Dict[str, Any], cfg: Optional[Config] = None) -> Dict[str, Any]:
    tzs = normalized_row.get("timezone_strings") or []
    if not tzs:
        return {"timezone_compatibility": "UNKNOWN", "evidence": []}
    for tz in tzs:
        key = tz.lower()
        if key in TZ_PASS:
            return {"timezone_compatibility": "PASS", "evidence": [tz]}
        if key in TZ_REVIEW:
            return {"timezone_compatibility": "REVIEW", "evidence": [tz]}
    return {"timezone_compatibility": "UNKNOWN", "evidence": tzs}


def classify_contractor_eligibility(normalized_row: Dict[str, Any], cfg: Optional[Config] = None) -> Dict[str, Any]:
    desc = (normalized_row.get("description") or "").lower()
    evidence: List[str] = []
    if "eor" in desc or "employer of record" in desc or "we support eor" in desc or "eor available" in desc:
        evidence.append("eor_supported")
        return {"contractor_eligibility": {"status": "PASS", "evidence": evidence, "source_field": "description"}}
    if "contractor only" in desc or "contractor-only" in desc:
        evidence.append("contractor_only")
        return {"contractor_eligibility": {"status": "REVIEW", "evidence": evidence, "source_field": "description"}}
    if "no contractors" in desc or "employee only" in desc or "employees only" in desc or "no contractor" in desc:
        evidence.append("employee_only")
        return {"contractor_eligibility": {"status": "REJECT", "evidence": evidence, "source_field": "description"}}
    return {"contractor_eligibility": {"status": "UNKNOWN", "evidence": [], "source_field": "description"}}


def gather_ghost_scam_signals(normalized_row: Dict[str, Any]) -> Dict[str, Any]:
    signals = {}
    desc = (normalized_row.get("description") or "").lower()
    signals["missing_company"] = not bool(normalized_row.get("company_name"))
    signals["short_description"] = len((normalized_row.get("description_plain") or "")) < 50
    signals["duplicate_count"] = normalized_row.get("duplicate_count") or 1
    scam_kw = ["pyramid", "multi-level", "mlm", "buy in", "pay to play"]
    signals["scam_indicators"] = [k for k in scam_kw if k in desc]
    return signals


def qualify_row(normalized_row: Dict[str, Any], cfg: Optional[Config] = None) -> Dict[str, Any]:
    cfg = cfg or default_config()

    sales = classify_sales_relevance(normalized_row, cfg)
    geo = classify_geographic_eligibility(normalized_row, cfg)
    posting = classify_posting_age(normalized_row, cfg)
    salary = classify_salary(normalized_row, cfg)
    remote = None
    # remote classification: check work_from_home_type and description
    desc = (normalized_row.get("description") or "").lower()
    wfht = (normalized_row.get("work_from_home_type") or "").lower()
    if any(k in desc for k in ["onsite", "on-site", "office-based", "must commute", "in-office"] ) or any(k in wfht for k in ["onsite", "on-site", "office", "hybrid"]):
        remote = {"remote_status": "REJECT", "evidence": ["onsite_or_hybrid"]}
    elif any(k in desc for k in ["remote", "work from home", "wfh", "fully remote", "remote-first"]) or normalized_row.get("is_remote_reported"):
        remote = {"remote_status": "PASS", "evidence": ["remote_keyword_or_flagged"]}
    else:
        remote = {"remote_status": "REVIEW", "evidence": []}

    tz = classify_timezone_compatibility(normalized_row, cfg)
    contractor = classify_contractor_eligibility(normalized_row, cfg)
    ghost = gather_ghost_scam_signals(normalized_row)

    rule_results = {
        "sales": sales,
        "geographic": geo,
        "posting_age": posting,
        "salary": salary,
        "remote": remote,
        "timezone": tz,
        "contractor": contractor.get("contractor_eligibility"),
        "ghost": ghost,
    }

    # Decision precedence and outcomes
    # 1. Posting age hard reject
    if posting["posting_age"] == "REJECT":
        return {"qualification_status": "REJECT", "qualification_reasons": ["posted_too_old"], "rule_results": rule_results}

    # 2. Geographic explicit REJECT
    if geo["geographic_eligibility"] == "REJECT":
        return {"qualification_status": "REJECT", "qualification_reasons": ["geographic_restriction_excludes_user_country"], "rule_results": rule_results}

    # 3. Contractor explicit REJECT
    if contractor.get("contractor_eligibility", {}).get("status") == "REJECT":
        return {"qualification_status": "REJECT", "qualification_reasons": ["employee_only_listing"], "rule_results": rule_results}

    # 4. Commission-only -> REJECT
    if salary.get("salary_qualification") == "REJECT":
        return {"qualification_status": "REJECT", "qualification_reasons": ["commission_only_or_no_base_salary"], "rule_results": rule_results}

    # 5. Remote hard reject
    if remote and remote.get("remote_status") == "REJECT":
        return {"qualification_status": "REJECT", "qualification_reasons": ["not_fully_remote"], "rule_results": rule_results}

    # 6. Sales relevance: LOW/NONE -> REJECT; MEDIUM -> REVIEW; HIGH -> continue
    sales_level = sales.get("sales_relevance_level")
    if sales_level in ("NONE", "LOW"):
        return {"qualification_status": "REJECT", "qualification_reasons": ["not_sales_role"], "rule_results": rule_results}

    review_reasons: List[str] = []
    if sales_level == "MEDIUM":
        review_reasons.append("ambiguous_sales_relevance")

    if geo["geographic_eligibility"] == "REVIEW":
        review_reasons.append("ambiguous_geographic_eligibility")

    if remote and remote.get("remote_status") == "REVIEW":
        review_reasons.append("ambiguous_remote_status")

    if salary.get("salary_qualification") == "REVIEW":
        review_reasons.append("salary_below_minimum")

    if tz.get("timezone_compatibility") == "REVIEW":
        review_reasons.append("ambiguous_timezone_compatibility")

    # contractor status REVIEW -> add reason but do not force reject
    if contractor.get("contractor_eligibility", {}).get("status") == "REVIEW":
        review_reasons.append("contractor_only_listing")

    # ghost / suspicious signals
    if ghost.get("short_description") or ghost.get("scam_indicators"):
        review_reasons.append("suspicious_listing_signals")

    if review_reasons:
        return {"qualification_status": "REVIEW", "qualification_reasons": review_reasons, "rule_results": rule_results}

    # Otherwise PASS
    pass_reasons = [f"sales_{sales_level}", f"remote_{remote.get('remote_status')}", f"geo_{geo.get('geographic_eligibility')}", f"posted_days:{normalized_row.get('days_since_posted')}"]
    if salary.get("salary_qualification") == "PASS":
        pass_reasons.append("salary_ok")
    else:
        pass_reasons.append("salary_unknown_or_missing")

    return {"qualification_status": "PASS", "qualification_reasons": pass_reasons, "rule_results": rule_results}


def qualify_df(df: pd.DataFrame, cfg: Optional[Config] = None) -> pd.DataFrame:
    cfg = cfg or default_config()
    if df.empty:
        return df
    rows = []
    for _, r in df.iterrows():
        row = r.to_dict()
        q = qualify_row(row, cfg)
        # ensure salary_qualification is present in row for consistency
        row["salary_qualification"] = q.get("rule_results", {}).get("salary", {}).get("salary_qualification")
        row.update({
            "qualification_status": q["qualification_status"],
            "qualification_reasons": q["qualification_reasons"],
            "qualification_rule_results": q["rule_results"],
        })
        rows.append(row)
    return pd.DataFrame(rows)
