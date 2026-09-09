# tests/test_cleaning.py
import pandas as pd
from jobspy.cleaning import clean_raw_df, deduplicate
from jobspy.config import default_config


def test_job_id_generation_and_dedupe():
    cfg = default_config()
    # Create two rows that represent the same job from two sites
    row1 = {
        "site": "indeed",
        "title": "Account Executive",
        "company_name": "Acme Co",
        "job_url": "https://indeed.com/viewjob?jk=abc",
        "job_url_direct": "https://acme.com/jobs/ae",
        "location": "Worldwide",
        "description": "Account Executive with quota",
        "date_posted": "2026-09-07",
        "is_remote": True,
    }
    row2 = {
        "site": "linkedin",
        "title": "Account Executive",
        "company_name": "Acme Co",
        "job_url": "https://linkedin.com/jobs/view/123",
        "job_url_direct": "https://acme.com/jobs/ae",
        "location": "Worldwide",
        "description": "Account Executive with quota",
        "date_posted": "2026-09-07",
        "is_remote": True,
    }
    df = pd.DataFrame([row1, row2])
    cleaned = clean_raw_df(df, cfg)
    deduped, duplicates_map = deduplicate(cleaned)
    assert len(deduped) == 1
    job_id = deduped.iloc[0]["job_id"]
    assert job_id in duplicates_map


def test_salary_parsing_to_monthly_and_usd():
    cfg = default_config()
    row = {
        "site": "indeed",
        "title": "Sales Rep",
        "company_name": "X",
        "job_url": "https://indeed.com/viewjob?jk=sal",
        "job_url_direct": None,
        "location": "Remote",
        "description": "Base salary $2,400/month + commission",
        "date_posted": "2026-09-07",
        "is_remote": True,
    }
    df = pd.DataFrame([row])
    cleaned = clean_raw_df(df, cfg)
    r = cleaned.iloc[0]
    assert r["salary_monthly_min"] == 2400 or r["salary_monthly_min"] == 2400.0
    # USD conversion uses default rate 1.0
    assert r["salary_monthly_min_usd"] == 2400 or r["salary_monthly_min_usd"] == 2400.0
