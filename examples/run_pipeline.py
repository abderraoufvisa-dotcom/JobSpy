"""Example: run the JobSpy discovery pipeline.

This script demonstrates how to call scrape_jobs() (if you want to run live scraping)
or how to run the pipeline on a synthetic DataFrame for testing.
"""
from __future__ import annotations

from pprint import pprint

# If you have a local clone and want to run the scrapers, uncomment the following:
# from jobspy import scrape_jobs

from jobspy.config import default_config
from jobspy.pipeline import run_discovery_pipeline
import pandas as pd


def synthetic_job_dataframe() -> pd.DataFrame:
    """Return a small synthetic DataFrame that mimics the shape returned by scrape_jobs().
    This is used for offline testing without hitting live job boards.
    """
    data = [
        {
            "site": "indeed",
            "title": "Sales Development Representative (SDR) - Remote",
            "company_name": "Acme SaaS",
            "job_url": "https://indeed.com/viewjob?jk=abc123",
            "job_url_direct": "https://jobs.acme.com/sdr-remote",
            "location": "Worldwide",
            "description": "We are hiring an SDR to prospect and qualify leads. Base salary $1800/month + commission. We hire globally. EOR available.",
            "date_posted": "2026-09-07",
            "is_remote": True,
            "compensation": {"interval": "monthly", "min_amount": 1800, "max_amount": 3000, "currency": "USD"},
            "job_function": "Sales",
            "skills": ["Salesforce", "Cold Calling"],
        },
        {
            "site": "indeed",
            "title": "Customer Support Representative",
            "company_name": "SupportCo",
            "job_url": "https://indeed.com/viewjob?jk=sup1",
            "job_url_direct": None,
            "location": "Remote - US only",
            "description": "Provide customer support. No sales. US-based candidates only.",
            "date_posted": "2026-09-05",
            "is_remote": True,
            "compensation": None,
            "job_function": "Customer Service",
            "skills": ["Zendesk"],
        },
    ]
    return pd.DataFrame(data)


def main():
    cfg = default_config()

    # For live scraping (not used in tests), you'd run:
    # jobs_df = scrape_jobs(site_name=["indeed"], search_term="sales", results_wanted=10)

    # For example/testing, use synthetic data
    jobs_df = synthetic_job_dataframe()

    result_df = run_discovery_pipeline(jobs_df, cfg=cfg, save_paths=None, save_raw=False)

    print("Pipeline output rows:")
    for _, row in result_df.iterrows():
        print("---")
        pprint({
            "job_id": row.get("job_id"),
            "title": row.get("title"),
            "company": row.get("company_name"),
            "qualification_status": row.get("qualification_status"),
            "qualification_reasons": row.get("qualification_reasons"),
            "rule_results": row.get("qualification_rule_results"),
        })


if __name__ == "__main__":
    main()
