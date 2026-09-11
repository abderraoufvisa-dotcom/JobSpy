# Updated deterministic tests for cleaning
import pandas as pd
from jobspy.cleaning import normalize_row, clean_raw_df, deduplicate


def test_job_id_different_jobs_same_company():
    row1 = {
        "site": "acme_jobs",
        "title": "Engineer I",
        "company_name": "Acme Co",
        "job_url": "https://jobs.acme.com/eng-1",
        "job_url_direct": "https://jobs.acme.com/eng-1",
        "company_url_direct": "https://acme.com",
        "location": "Algiers",
    }
    row2 = {
        "site": "acme_jobs",
        "title": "Engineer II",
        "company_name": "Acme Co",
        "job_url": "https://jobs.acme.com/eng-2",
        "job_url_direct": "https://jobs.acme.com/eng-2",
        "company_url_direct": "https://acme.com",
        "location": "Algiers",
    }
    n1 = normalize_row(row1)
    n2 = normalize_row(row2)
    assert n1["job_id"] != n2["job_id"], "Different jobs at same company must have different job_ids"


def test_same_job_url_same_job_id_from_two_sources():
    row1 = {
        "site": "indeed",
        "title": "Account Executive",
        "company_name": "Beta",
        "job_url": "https://jobs.beta.com/ae-1",
        "job_url_direct": "https://jobs.beta.com/ae-1",
        "location": "Remote",
    }
    row2 = {
        "site": "linkedin",
        "title": "Account Executive",
        "company_name": "Beta Ltd",
        "job_url": "https://jobs.beta.com/ae-1",
        "job_url_direct": "https://jobs.beta.com/ae-1",
        "location": "Remote",
    }
    n1 = normalize_row(row1)
    n2 = normalize_row(row2)
    assert n1["job_id"] == n2["job_id"], "Same job URL across sources must produce identical job_id"


def test_company_url_direct_does_not_affect_job_id():
    row_base = {
        "site": "siteA",
        "title": "Data Analyst",
        "company_name": "Gamma",
        "job_url": "https://jobs.gamma.com/da-1",
        "job_url_direct": "https://jobs.gamma.com/da-1",
        "location": "Algiers",
    }
    row_a = dict(row_base)
    row_a["company_url_direct"] = "https://gamma.com/office-a"
    row_b = dict(row_base)
    row_b["company_url_direct"] = "https://gamma.com/office-b"
    n1 = normalize_row(row_a)
    n2 = normalize_row(row_b)
    assert n1["job_id"] == n2["job_id"], "company_url_direct must not affect job_id generation"


def test_deduplication_by_job_url():
    df = pd.DataFrame([
        {"site": "indeed", "title": "AE", "company_name": "Z", "job_url": "https://z.com/job/1", "job_url_direct": "https://z.com/job/1"},
        {"site": "linkedin", "title": "AE", "company_name": "Z", "job_url": "https://z.com/job/1", "job_url_direct": "https://z.com/job/1"},
        {"site": "indeed", "title": "AE2", "company_name": "Z", "job_url": "https://z.com/job/2", "job_url_direct": "https://z.com/job/2"},
    ])
    cleaned = clean_raw_df(df)
    deduped, duplicates_map = deduplicate(cleaned)
    # two distinct job URLs -> two records
    assert len(deduped) == 2
    # the job with job_url '/job/1' should have duplicate_count 2 after pipeline merges (duplicate_count added by pipeline)
    # but deduplicate returns merged rows; ensure duplicates_map contains both entries
    found = False
    for k, v in duplicates_map.items():
        if any("/job/1" in (u or "") for u in v):
            found = True
    assert found, "duplicates_map must include the URLs for the duplicated job"
