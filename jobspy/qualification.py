from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from jobspy.config import default_config, Config
from jobspy.constants import (
    TIMEZONE_OFFSETS,
)

SALES_LEVELS = ("HIGH", "MEDIUM", "LOW", "NONE")
GEO_LEVELS = ("PASS", "REVIEW", "REJECT")
REMOTE_LEVELS = ("PASS", "REVIEW", "REJECT")
SALARY_STATUS = ("PASS", "REVIEW", "REJECT", "UNKNOWN")


def _score_title(title: Optional[str], cfg: Config) -> Tuple[float, List[str]]:
    score = 0.0
    evidence: List[str] = []
    if not title:
        return score, evidence
    t = title.lower()
    for phrase in cfg.SALES_WHITELIST:
        if phrase in t:
            score += cfg.SALES_WEIGHTS.get("title_exact", 5.0)
            evidence.append(f"title_exact:{phrase}")
    # partial matches
    for phrase in cfg.SALES_WHITELIST:
        words = phrase.split()
        if len(words) > 1 and any(w in t for w in words):
            score += cfg.SALES_WEIGHTS.get("title_partial", 2.0) * 0.5
            evidence.append(f"title_partial:{phrase}")
    # negative
    for n in cfg.SALES_BLACKLIST:
        if n in t:
            score += cfg.SALES_WEIGHTS.get("negative", -6.0)
            evidence.append(f"title_negative:{n}")
    return score, evidence


def _score_description(desc: Optional[str], cfg: Config) -> Tuple[float, List[str]]:
    score = 0.0
    evidence: List[str] = []
    if not desc:
        return score, evidence
    d = desc.lower()
    strong_phrases = [
        "quota",
        "quota-carrying",
        "cold call",
        "cold-calling",
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
        "quota",
    ]
    for p in strong_phrases:
        if p in d:
            score += cfg.SALES_WEIGHTS.get("description_strong", 3.0)
            evidence.append(f"desc:{p}")
    # CRM tools
    tools = ["salesforce", "hubspot", "outreach", "pipedrive"]
    for t in tools:
        if t in d:
            score += cfg.SALES_WEIGHTS.get("skills", 1.5)
            evidence.append(f"tool:{t}")
    # negative signals
    for n in cfg.SALES_BLACKLIST:
        if n in d:
            score += cfg.SALES_WEIGHTS.get("negative", -6.0)
            evidence.append(f"desc_negative:{n}")
    return score, evidence


def classify_sales_relevance(normalized_row: Dict[str, Any], cfg: Optional[Config] = None) -> Dict[str, Any]:
    cfg = cfg or default_config()
    title = normalized_row.get("normalized_title")
    desc = normalized_row.get("description_plain")
    job_function = (normalized_row.get("job_function") or "")
    skills = normalized_row.get("skills") or []

    score = 0.0
    evidence: List[str] = []

    s, ev = _score_title(title, cfg)
    score += s
    evidence.extend(ev)

    s, ev = _score_description(desc, cfg)
    score += s
    evidence.extend(ev)

    if job_function and "sales" in str(job_function).lower():
        score += cfg.SALES_WEIGHTS.get("job_function", 3.0)
        evidence.append("job_function:sales")

    if skills:
        skills_text = " ".join([str(x).lower() for x in (skills if isinstance(skills, list) else [skills])])
        for tool in ["salesforce", "hubspot"]:
            if tool in skills_text:
                score += cfg.SALES_WEIGHTS.get("skills", 1.5)
                evidence.append(f"skill:{tool}")

    # Experience hint
    exp = normalized_row.get("experience_range") or ""
    if isinstance(exp, str) and any(tok in exp.lower() for tok in ["sales", "business development"]):
        score += cfg.SALES_WEIGHTS.get("experience", 1.0)
        evidence.append("experience:sales")

    # Map score to level
    thresholds = cfg.SALES_THRESHOLDS
    level = "NONE"
    if score >= thresholds.get("HIGH", 6.0):
        level = "HIGH"
    elif score >= thresholds.get("MEDIUM", 3.0):
        level = "MEDIUM"
    elif score >= thresholds.get("LOW", 1.0):
        level = "LOW"
    else:
        level = "NONE"

    return {
        "sales_relevance": level,
        "sales_relevance_score": score,
        "sales_relevance_evidence": evidence,
    }


def classify_remote_status(normalized_row: Dict[str, Any], cfg: Optional[Config] = None) -> Dict[str, Any]:
    cfg = cfg or default_config()
    desc = (normalized_row.get("description") or "").lower()
    is_remote_reported = normalized_row.get("is_remote_reported")
    wfht = (normalized_row.get("work_from_home_type") or "").lower()

    # immediate rejects for onsite/hybrid
    onsite_keywords = ["onsite", "on-site", "office-based", "must commute", "in-office", "hybrid", "partially remote"]
    for kw in onsite_keywords:
        if kw in desc or kw in wfht:
            return {"remote_status": "REJECT", "evidence": ["onsite_or_hybrid:" + kw]}

    # positive remote keywords
    remote_keywords = ["remote", "work from home", "wfh", "fully remote", "remote-first"]
    for kw in remote_keywords:
        if kw in desc or kw in wfht:
            return {"remote_status": "PASS", "evidence": ["remote_keyword:" + kw]}

    # If scraper reported remote and no onsite/hybrid evidence, accept
    if is_remote_reported:
        return {"remote_status": "PASS", "evidence": ["is_remote_reported"]}

    # otherwise REVIEW (ambiguous)
    return {"remote_status": "REVIEW", "evidence": []}


def classify_geographic_eligibility(normalized_row: Dict[str, Any], cfg: Optional[Config] = None) -> Dict[str, Any]:
    cfg = cfg or default_config()
    desc = (normalized_row.get("description") or "").lower()
    loc_display = (normalized_row.get("normalized_location") or {}).get("display") or ""
    combined = " ".join([desc, str(loc_display).lower()])

    # positive signals
    for p in cfg.GEOGRAPHIC_POSITIVE:
        if p in combined:
            return {"geographic_eligibility": "PASS", "evidence": ["geo_positive:" + p]}

    # EMEA is PASS for Algeria per requirement
    if "emea" in combined:
        return {"geographic_eligibility": "PASS", "evidence": ["geo_positive:emea"]}

    # explicit negative signals
    for n in cfg.GEOGRAPHIC_REJECT:
        if n in combined:
            return {"geographic_eligibility": "REJECT", "evidence": ["geo_reject:" + n]}

    # Europe-only fallback -> REVIEW
    if "europe" in combined and "europe only" in combined:
        return {"geographic_eligibility": "REVIEW", "evidence": ["geo_review:europe only"]}

    # If location explicitly includes Algeria
    if "algeria" in combined or "dz" in combined:
        return {"geographic_eligibility": "PASS", "evidence": ["geo_positive:algeria"]}

    # ambiguous -> REVIEW
    return {"geographic_eligibility": "REVIEW", "evidence": []}


def classify_posting_age(normalized_row: Dict[str, Any], cfg: Optional[Config] = None) -> Dict[str, Any]:
    cfg = cfg or default_config()
    days = normalized_row.get("days_since_posted")
    if days is None:
        return {"posting_age": "REVIEW", "evidence": ["missing_date"]}
    if days <= cfg.REVIEW_WINDOW_DAYS:
        return {"posting_age": "PASS", "evidence": [f"days:{days}"]}
    return {"posting_age": "REJECT", "evidence": [f"days:{days}"]}


def classify_salary(normalized_row: Dict[str, Any], cfg: Optional[Config] = None) -> Dict[str, Any]:
    cfg = cfg or default_config()
    # Respect rule: missing salary -> UNKNOWN and do NOT force review/reject
    commission_only = normalized_row.get("commission_only", False)
    if commission_only:
        return {"salary_status": "REJECT", "evidence": ["commission_only"]}

    usd_min = normalized_row.get("salary_monthly_min_usd")
    if usd_min is None:
        return {"salary_status": "UNKNOWN", "evidence": ["no_salary"]}

    if usd_min >= cfg.MIN_SALARY_USD_PER_MONTH:
        return {"salary_status": "PASS", "evidence": [f"usd_min:{usd_min}"]}
    # below minimum -> REVIEW (or REJECT depending on strictness). We'll flag REVIEW
    return {"salary_status": "REVIEW", "evidence": [f"usd_min:{usd_min}"]}


def classify_timezone_compatibility(normalized_row: Dict[str, Any], cfg: Optional[Config] = None) -> Dict[str, Any]:
    cfg = cfg or default_config()
    tzs = normalized_row.get("timezone_strings") or []
    if not tzs:
        return {"timezone_compatibility": "UNKNOWN", "evidence": []}
    # If any tz is in preferred set (UTC/BST/CET/CEST)
    preferred = {"UTC", "BST", "CET", "CEST"}
    for tz in tzs:
        if tz.upper() in preferred:
            return {"timezone_compatibility": "PASS", "evidence": ["tz:" + tz]}
        if tz.upper() in {"EST", "EDT", "CST", "CDT", "PST", "PDT"}:
            return {"timezone_compatibility": "REVIEW", "evidence": ["tz:" + tz]}
    return {"timezone_compatibility": "UNKNOWN", "evidence": tzs}


def gather_ghost_scam_signals(normalized_row: Dict[str, Any]) -> Dict[str, Any]:
    signals = {}
    desc = (normalized_row.get("description") or "").lower()
    # simple heuristics
    signals["missing_company"] = not bool(normalized_row.get("company_name"))
    signals["short_description"] = len((normalized_row.get("description_plain") or "")) < 50
    signals["duplicate_count"] = 1  # filled by dedupe pipeline if available
    # MLM/scam keywords
    scam_kw = ["pyramid", "multi-level", "mlm", "buy in", "pay to play"]
    signals["scam_indicators"] = [k for k in scam_kw if k in desc]
    return signals


def qualify_row(normalized_row: Dict[str, Any], cfg: Optional[Config] = None) -> Dict[str, Any]:
    cfg = cfg or default_config()
    # run classifiers
    sales = classify_sales_relevance(normalized_row, cfg)
    remote = classify_remote_status(normalized_row, cfg)
    geo = classify_geographic_eligibility(normalized_row, cfg)
    posting = classify_posting_age(normalized_row, cfg)
    salary = classify_salary(normalized_row, cfg)
    tz = classify_timezone_compatibility(normalized_row, cfg)
    ghost = gather_ghost_scam_signals(normalized_row)

    rule_results = {
        "sales_relevance": sales,
        "remote": remote,
        "geographic": geo,
        "posting_age": posting,
        "salary": salary,
        "timezone": tz,
        "ghost_scam_signals": ghost,
    }

    # Decision flow - hard rejections first
    reasons: List[str] = []

    # Posting age hard REJECT
    if posting["posting_age"] == "REJECT":
        return {
            "qualification_status": "REJECT",
            "qualification_reasons": ["posted_too_old"],
            "rule_results": rule_results,
        }

    # Sales relevance hard REJECT if NONE or LOW
    if sales["sales_relevance"] in ("NONE", "LOW"):
        return {
            "qualification_status": "REJECT",
            "qualification_reasons": ["not_sales_role"],
            "rule_results": rule_results,
        }

    # Remote status hard REJECT (onsite/hybrid)
    if remote["remote_status"] == "REJECT":
        return {
            "qualification_status": "REJECT",
            "qualification_reasons": ["not_fully_remote"],
            "rule_results": rule_results,
        }

    # Geographic explicit REJECT
    if geo["geographic_eligibility"] == "REJECT":
        return {
            "qualification_status": "REJECT",
            "qualification_reasons": ["geographic_restriction_excludes_user_country"],
            "rule_results": rule_results,
        }

    # Commission-only -> REJECT
    if salary["salary_status"] == "REJECT":
        return {
            "qualification_status": "REJECT",
            "qualification_reasons": ["commission_only_or_no_base_salary"],
            "rule_results": rule_results,
        }

    # At this point, no hard rejections. Gather any REVIEW flags
    review_reasons: List[str] = []
    if sales["sales_relevance"] == "MEDIUM":
        review_reasons.append("ambiguous_sales_relevance")
    if remote["remote_status"] == "REVIEW":
        review_reasons.append("ambiguous_remote_status")
    if geo["geographic_eligibility"] == "REVIEW":
        review_reasons.append("ambiguous_geographic_eligibility")
    if salary["salary_status"] == "REVIEW":
        review_reasons.append("salary_below_min_or_unclear")
    if tz["timezone_compatibility"] == "REVIEW":
        review_reasons.append("ambiguous_timezone_compatibility")
    # ghost/scam signals non-decisive -> REVIEW
    if ghost.get("short_description") or ghost.get("scam_indicators"):
        review_reasons.append("suspicious_listing_signals")

    if review_reasons:
        return {
            "qualification_status": "REVIEW",
            "qualification_reasons": review_reasons,
            "rule_results": rule_results,
        }

    # Otherwise PASS
    pass_reasons = [
        f"sales_{sales['sales_relevance']}",
        f"remote_{remote['remote_status']}",
        f"geo_{geo['geographic_eligibility']}",
        f"posted_days:{normalized_row.get('days_since_posted')}",
    ]
    if salary["salary_status"] == "PASS":
        pass_reasons.append("salary_ok")
    else:
        pass_reasons.append("salary_unknown_or_missing")

    return {
        "qualification_status": "PASS",
        "qualification_reasons": pass_reasons,
        "rule_results": rule_results,
    }


def qualify_df(df: pd.DataFrame, cfg: Optional[Config] = None) -> pd.DataFrame:
    cfg = cfg or default_config()
    if df.empty:
        return df
    rows = []
    for _, r in df.iterrows():
        row = r.to_dict()
        q = qualify_row(row, cfg)
        # merge results into row
        row.update({
            "qualification_status": q["qualification_status"],
            "qualification_reasons": q["qualification_reasons"],
            "qualification_rule_results": q["rule_results"],
        })
        rows.append(row)
    return pd.DataFrame(rows)
