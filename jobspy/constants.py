# jobspy/constants.py
"""
Constants and keyword lists used by cleaning and qualification.
"""
from __future__ import annotations

# Sales positive whitelist (phrases that strongly indicate sales)
SALES_WHITELIST = [
    "sales development",
    "sales development representative",
    "sdr",
    "business development",
    "bdm",
    "bdr",
    "account executive",
    "account manager",
    "inside sales",
    "enterprise sales",
    "saas sales",
    "technical sales",
    "sales operations",
    "sales support",
    "sales coordinator",
    "lead generation",
    "sales representative",
    "sales rep",
    "business development representative",
    "business development executive",
    "partnership",
    "commercial",
    "sales enablement",
    "revenue operations",
    "appointment setter",
]

# Negative blacklist - typical non-sales functions
NON_SALES_BLACKLIST = [
    "marketing",
    "digital marketing",
    "hr",
    "recruit",
    "finance",
    "accounting",
    "engineering",
    "software",
    "developer",
    "it support",
    "technical support",
    "customer support",
    "customer service",
    "data analyst",
    "business analyst",
    "operations manager",
    "project manager",
    "administrative assistant",
]

# Geographic keywords
GEOGRAPHIC_POSITIVE = [
    "worldwide",
    "global",
    "anywhere",
    "work from anywhere",
    "remote worldwide",
    "international",
    "africa",
    "remote africa",
    "emea",
    "remote emea",
]

GEOGRAPHIC_REVIEW = [
    "europe",
    "europe only",
]

GEOGRAPHIC_REJECT = [
    "us only",
    "usa only",
    "united states only",
    "canada only",
    "uk only",
    "united kingdom only",
    "australia only",
    "eu only",
    "european union only",
]

# Contractor keywords
CONTRACTOR_KEYWORDS = [
    "contractor",
    "independent contractor",
    "freelance",
    "eor",
    "employer of record",
    "hire globally",
    "hire anywhere",
    "global contractor",
    "international contractor",
    "contract",
]

# Remote keywords
REMOTE_POSITIVE = ["remote", "work from home", "wfh", "fully remote", "remote-first"]
REMOTE_NEGATIVE = ["onsite", "on-site", "office-based", "must commute", "in-office", "hybrid", "partially remote"]

# Commission indicators
COMMISSION_ONLY_KEYWORDS = ["commission only", "100% commission", "no base", "pure commission", "commission-only"]

# Timezone groups mapping name->UTC offset (hours) approx for Phase 1
TIMEZONE_OFFSETS = {
    "UTC": 0,
    "GMT": 0,
    "BST": 1,
    "CET": 1,
    "CEST": 2,
    "WEST": 1,
    "EET": 2,
    "EST": -5,
    "EDT": -4,
    "CST": -6,
    "CDT": -5,
    "PST": -8,
    "PDT": -7,
}

# Default static currency rates to USD for Phase 1 (USD per 1 unit of currency)
# e.g. 1 EUR = 1.05 USD (example rate)
CURRENCY_RATES_DEFAULT = {
    "USD": 1.0,
    "EUR": 1.05,
    "GBP": 1.25,
    "DZD": 0.0073,  # Algerian Dinar -> USD approx placeholder
}
