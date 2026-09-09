from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from jobspy.constants import CURRENCY_RATES_DEFAULT

@dataclass
class Config:
    # User location and timezone
    USER_COUNTRY: str = "Algeria"
    USER_COUNTRY_CODE: str = "DZ"  # ISO-2, optional
    USER_TIMEZONE: str = "Africa/Algiers"  # tz database name or description

    # Salary and recency
    MIN_SALARY_USD_PER_MONTH: float = 1200.0
    REVIEW_WINDOW_DAYS: int = 7

    # Currency rates for conversion to USD (unit -> USD)
    # Phase 1 uses a static table; replace or extend later with a provider
    CURRENCY_RATES: Dict[str, float] = field(default_factory=lambda: dict(CURRENCY_RATES_DEFAULT))

    # Sales classifier weights and thresholds (tunable)
    SALES_WEIGHTS: Dict[str, float] = field(default_factory=lambda: {
        "title_exact": 5.0,
        "title_partial": 2.0,
        "description_strong": 3.0,
        "job_function": 3.0,
        "skills": 1.5,
        "experience": 1.0,
        "negative": -6.0,
    })
    SALES_THRESHOLDS: Dict[str, float] = field(default_factory=lambda: {
        "HIGH": 6.0,
        "MEDIUM": 3.0,
        "LOW": 1.0,
    })

    # Dedupe behavior
    DEDUPE_EXACT_NORMALIZED: bool = True

    # Other toggles
    CONVERT_CURRENCY: bool = True

    # Lists that can be overridden
    SALES_WHITELIST: List[str] = field(default_factory=list)
    SALES_BLACKLIST: List[str] = field(default_factory=list)
    GEOGRAPHIC_POSITIVE: List[str] = field(default_factory=list)
    GEOGRAPHIC_REVIEW: List[str] = field(default_factory=list)
    GEOGRAPHIC_REJECT: List[str] = field(default_factory=list)


def default_config() -> Config:
    cfg = Config()
    # Import defaults from constants lazily to avoid import cycles
    from jobspy.constants import SALES_WHITELIST, NON_SALES_BLACKLIST, GEOGRAPHIC_POSITIVE, GEOGRAPHIC_REVIEW, GEOGRAPHIC_REJECT

    cfg.SALES_WHITELIST = SALES_WHITELIST
    cfg.SALES_BLACKLIST = NON_SALES_BLACKLIST
    cfg.GEOGRAPHIC_POSITIVE = GEOGRAPHIC_POSITIVE
    cfg.GEOGRAPHIC_REVIEW = GEOGRAPHIC_REVIEW
    cfg.GEOGRAPHIC_REJECT = GEOGRAPHIC_REJECT
    return cfg
