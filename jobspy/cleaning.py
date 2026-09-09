from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from dateutil import parser as date_parser

from jobspy.config import default_config, Config
from jobspy.constants import CURRENCY_RATES_DEFAULT, COMMISSION_ONLY_KEYWORDS
from jobspy.util import extract_salary, plain_converter


def _normalize_text(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    s2 = re.sub(r"\s+", " ", s.strip())
    return s2


def _normalize_url(u: Optional[str]) -> Optional[str]:
    if not u:
        return None
    # Basic normalization: lowercase scheme/host, remove utm params, strip trailing slash
    try:
        from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

        parts = urlparse(u)
        scheme = parts.scheme.lower() if parts.scheme else "https"
        netloc = parts.netloc.lower()
        path = parts.path.rstrip("/")
        # filter query params
        q = dict(parse_qsl(parts.query, keep_blank_values=True))
        q = {k: v for k, v in q.items() if not k.startswith("utm_")}
        query = urlencode(sorted(q.items()))
        normalized = urlunparse((scheme, netloc, path, "", query, ""))
        return normalized
    except Exception:
        return u.strip()


def generate_job_id(
    canonical_job_url: Optional[str],
    job_url_direct: Optional[str],
    job_url: Optional[str],
    company: Optional[str],
    title: Optional[str],
    location_str: Optional[str],
    date_posted: Optional[date],
) -> str:
    """Generate SHA1 job id using canonical_job_url if present else fallback signature."""

    def sha1(s: str) -> str:
        return hashlib.sha1(s.encode("utf-8")).hexdigest()

    if canonical_job_url:
        return sha1(canonical_job_url)
    if job_url_direct:
        return sha1(job_url_direct)
    if job_url:
        return sha1(job_url)
    # fallback
    parts = [company or "", title or "", location_str or "", date_posted.isoformat() if date_posted else ""]
    sig = "|".join([_normalize_text(p).lower() if p else "" for p in parts])
    return sha1(sig)


def _parse_date(d: Any) -> Optional[date]:
    if d is None:
        return None
    if isinstance(d, date) and not isinstance(d, datetime):
        return d
    try:
        if isinstance(d, (int, float)):
            # assume timestamp seconds or milliseconds
            if d > 1e12:
                dt = datetime.fromtimestamp(d / 1000)
            else:
                dt = datetime.fromtimestamp(d)
        else:
            dt = date_parser.parse(str(d))
        return dt.date()
    except Exception:
        return None


def _convert_salary_to_monthly_min_max(
    interval: Optional[str], min_amount: Optional[float], max_amount: Optional[float]
) -> Tuple[Optional[float], Optional[float]]:
    if interval is None or (min_amount is None and max_amount is None):
        return None, None

    def conv_to_month(val: float) -> float:
        if interval == "yearly":
            return val / 12.0
        if interval == "monthly":
            return val
        if interval == "weekly":
            return val * 52.0 / 12.0
        if interval == "daily":
            return val * 260.0 / 12.0
        if interval == "hourly":
            return val * 2080.0 / 12.0
        return val

    return (
        conv_to_month(min_amount) if min_amount is not None else None,
        conv_to_month(max_amount) if max_amount is not None else None,
    )


def _extract_currency_rate(currency: Optional[str], cfg: Config) -> Optional[float]:
    if not currency:
        return None
    cur = currency.upper()
    rates = cfg.CURRENCY_RATES
    return rates.get(cur)


def _is_commission_only(description: str, cfg: Config) -> bool:
    if not description:
        return False
    d = description.lower()
    # If description contains explicit positive base salary indicators, don't treat as commission-only
    if "base" in d or "salary" in d or "$" in d or "£" in d or "€" in d:
        # but some phrases like "no base" indicate commission-only; handle negatives below
        # check for explicit commission-only strong phrases
        for kw in COMMISSION_ONLY_KEYWORDS:
            if kw in d:
                # if keyword present but there is also explicit base mentioned (e.g., "base $2000 + commission"), it's not commission-only
                # We already returned False if "base" or currency symbols present; but ensure phrases like "no base" are handled
                if "no base" in d or "no base salary" in d or "no base" in d:
                    return True
                # check for strong patterns like "100% commission"
                if kw in ("100% commission", "pure commission", "commission-only"):
                    return True
                # else, if keyword present but there is explicit base number, do not mark as commission-only
                # therefore continue scanning
        # if we found currency or base mention, assume not commission-only
        return False
    # if no base/currency mention, but commission keywords like "commission only" present -> commission-only
    for kw in COMMISSION_ONLY_KEYWORDS:
        if kw in d:
            return True
    return False


def normalize_row(raw_row: Dict[str, Any], cfg: Optional[Config] = None) -> Dict[str, Any]:
    """Normalize a single job row (dictionary) and return normalized dictionary with added fields."""
    cfg = cfg or default_config()
    row = dict(raw_row)  # shallow copy

    # Preserve raw
    row["raw_job_dict"] = json.loads(json.dumps(raw_row, default=str))

    # Normalize title/company/description
    title = _normalize_text(row.get("title"))
    company = _normalize_text(row.get("company_name") or row.get("company"))
    description = row.get("description")
    if description and not isinstance(description, str):
        try:
            description = str(description)
        except Exception:
            description = None
    description_plain = plain_converter(description) if description else None

    # Normalize urls
    # Prefer a canonical job URL field if present (canonical_job_url or canonical_url).
    canonical_job_url = _normalize_url(row.get("canonical_job_url") or row.get("canonical_url"))
    job_url_direct = _normalize_url(row.get("job_url_direct") or row.get("job_url"))
    # job_url field still preserved separately
    job_url = _normalize_url(row.get("job_url"))

    # Dates
    date_posted = _parse_date(row.get("date_posted"))
    days_since_posted = None
    if date_posted:
        days_since_posted = (datetime.utcnow().date() - date_posted).days

    # Location
    location_raw = row.get("location")
    if isinstance(location_raw, dict):
        # try to create a simple string
        loc_parts = []
        if location_raw.get("city"):
            loc_parts.append(location_raw.get("city"))
        if location_raw.get("state"):
            loc_parts.append(location_raw.get("state"))
        if location_raw.get("country"):
            loc_parts.append(str(location_raw.get("country")))
        location_str = ", ".join([p for p in loc_parts if p]) if loc_parts else None
    else:
        location_str = _normalize_text(location_raw) if location_raw else None

    # Compensation parse: if compensation object exists, use it; else try description extraction
    salary_interval = None
    salary_min = None
    salary_max = None
    salary_currency = None
    salary_source = None
    compensation_obj = row.get("compensation")
    if compensation_obj and isinstance(compensation_obj, dict):
        interval = compensation_obj.get("interval")
        if hasattr(interval, "value"):
            interval_val = interval.value
        else:
            interval_val = interval
        salary_interval = interval_val
        salary_min = compensation_obj.get("min_amount")
        salary_max = compensation_obj.get("max_amount")
        salary_currency = compensation_obj.get("currency") or compensation_obj.get("currency_code")
        salary_source = "DIRECT_DATA"
    else:
        # try description extraction
        if description:
            interval, smin, smax, currency = extract_salary(str(description))
            if interval or smin or smax:
                salary_interval = interval
                salary_min = smin
                salary_max = smax
                salary_currency = currency
                salary_source = "DESCRIPTION"

    # Convert to monthly amounts and USD if possible
    monthly_min, monthly_max = _convert_salary_to_monthly_min_max(salary_interval, salary_min, salary_max)
    usd_monthly_min = None
    usd_monthly_max = None
    if cfg.CONVERT_CURRENCY and salary_currency and (monthly_min or monthly_max):
        rate = _extract_currency_rate(salary_currency, cfg)
        if rate:
            usd_monthly_min = monthly_min * rate if monthly_min is not None else None
            usd_monthly_max = monthly_max * rate if monthly_max is not None else None

    # Commission detection (use configured keywords)
    desc_l = (description or "").lower()
    commission_only = _is_commission_only(desc_l, cfg)

    # Contractor signals
    contractor_signals: List[str] = []
    from jobspy.constants import CONTRACTOR_KEYWORDS

    for kw in CONTRACTOR_KEYWORDS:
        if kw in desc_l:
            contractor_signals.append(kw)

    # timezone strings naive extraction
    timezone_strings: List[str] = []
    for tz in ["CET", "CEST", "GMT", "BST", "EST", "EDT", "CST", "CDT", "PST", "PDT", "UTC"]:
        if tz.lower() in (desc_l or ""):
            timezone_strings.append(tz)

    # sales_fields
    sales_fields = {
        "title": title,
        "description_plain": description_plain,
        "job_function": row.get("job_function"),
        "skills": row.get("skills"),
        "experience_range": row.get("experience_range"),
    }

    normalized = {
        "raw_job_dict": row.get("raw_job_dict"),
        "site": row.get("site"),
        "job_id": None,  # fill after
        "source_sites": [row.get("site")] if row.get("site") else [],
        "canonical_job_url": canonical_job_url,
        "job_url": job_url,
        "job_url_direct": job_url_direct,
        "title": title,
        "normalized_title": title.lower() if title else None,
        "company_name": company,
        "normalized_company": company.lower() if company else None,
        "location_raw": location_raw,
        "normalized_location": {"display": location_str} if location_str else None,
        "date_posted": date_posted,
        "days_since_posted": days_since_posted,
        "description": description,
        "description_plain": description_plain,
        "has_description": bool(description_plain),
        "job_type": row.get("job_type"),
        "job_function": row.get("job_function"),
        "skills": row.get("skills"),
        "experience_range": row.get("experience_range"),
        "is_remote_reported": row.get("is_remote"),
        "work_from_home_type": row.get("work_from_home_type"),
        "compensation_raw": compensation_obj,
        "salary_interval": salary_interval,
        "salary_min": salary_min,
        "salary_max": salary_max,
        "salary_currency": salary_currency,
        "salary_source": salary_source,
        "salary_monthly_min": monthly_min,
        "salary_monthly_max": monthly_max,
        "salary_monthly_min_usd": usd_monthly_min,
        "salary_monthly_max_usd": usd_monthly_max,
        # availability vs qualification naming
        "salary_availability": "KNOWN" if (salary_min is not None or salary_max is not None) else "UNKNOWN",
        "salary_qualification": "UNKNOWN",
        "commission_only": commission_only,
        "contractor_signals": contractor_signals,
        "timezone_strings": timezone_strings,
        "sales_fields": sales_fields,
        "created_at": datetime.utcnow().isoformat(),
    }

    # job_id
    normalized_job_id = generate_job_id(
        canonical_job_url=canonical_job_url,
        job_url_direct=job_url_direct,
        job_url=job_url,
        company=company,
        title=title,
        location_str=location_str,
        date_posted=date_posted,
    )
    normalized["job_id"] = normalized_job_id

    return normalized


def clean_raw_df(raw_df: pd.DataFrame, cfg: Optional[Config] = None) -> pd.DataFrame:
    """Cleans a DataFrame produced by scrape_jobs and returns a normalized DataFrame."""
    cfg = cfg or default_config()
    normalized_rows: List[Dict[str, Any]] = []
    for _, r in raw_df.iterrows():
        try:
            raw_row = r.to_dict()
        except Exception:
            raw_row = dict(r)
        nr = normalize_row(raw_row, cfg)
        normalized_rows.append(nr)
    df = pd.DataFrame(normalized_rows)
    return df


def deduplicate(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, List[str]]]:
    """Exact deduplication by job_id (preserves source sites as list). Returns (deduped_df, duplicates_map)."""
    if df.empty:
        return df, {}
    df2 = df.copy()
    # group by job_id
    duplicates_map: Dict[str, List[str]] = {}
    grouped = df2.groupby("job_id")
    rows: List[Dict[str, Any]] = []
    for job_id, group in grouped:
        urls = list(group.apply(lambda r: r.get("job_url") or r.get("raw_job_dict", {}).get("job_url"), axis=1))
        duplicates_map[job_id] = urls
        if len(group) == 1:
            rows.append(group.iloc[0].to_dict())
        else:
            # merge source_sites and prefer canonical fields from the first non-null
            merged = group.iloc[0].to_dict()
            source_sites = []
            for _, gr in group.iterrows():
                ss = gr.get("source_sites") or []
                for s in ss:
                    if s not in source_sites:
                        source_sites.append(s)
            merged["source_sites"] = source_sites
            # choose canonical_job_url if any non-null exists
            for col in ["canonical_job_url", "job_url_direct", "job_url", "title", "company_name"]:
                vals = group[col].dropna().unique().tolist()
                merged[col] = vals[0] if vals else merged.get(col)
            rows.append(merged)
    deduped = pd.DataFrame(rows)
    return deduped.reset_index(drop=True), duplicates_map
