# tests/test_qualification.py
import pandas as pd
from jobspy.config import default_config
from jobspy.pipeline import run_discovery_pipeline


def mk_df(rows):
    return pd.DataFrame(rows)


def test_qualifying_remote_sales_pass():
    cfg = default_config()
    rows = [
        {
            "site": "indeed",
            "title": "Sales Development Representative",
            "company_name": "Acme",
            "job_url": "https://jobs.acme.com/sdr1",
            "job_url_direct": "https://jobs.acme.com/sdr1",
            "location": "Remote - Worldwide",
            "description": "Quota carrying role. 9-5 CET acceptable. Base $1500/month + commission.",
            "date_posted": "2026-09-08",
            "is_remote": True,
            "compensation": {"interval": "monthly", "min_amount": 1500, "max_amount": 2500, "currency": "USD"},
            "job_function": "Sales",
        }
    ]
    df = mk_df(rows)
    out = run_discovery_pipeline(df, cfg, save_paths=None, save_raw=False)
    assert out.iloc[0]["qualification_status"] == "PASS"


def test_non_sales_reject():
    cfg = default_config()
    rows = [
        {
            "site": "indeed",
            "title": "Digital Marketing Specialist",
            "company_name": "MarketCo",
            "job_url": "https://jobs.marketco.com/mkt1",
            "job_url_direct": None,
            "location": "Remote - Worldwide",
            "description": "Manage digital campaigns. No sales responsibilities.",
            "date_posted": "2026-09-08",
            "is_remote": True,
            "compensation": None,
            "job_function": "Marketing",
        }
    ]
    out = run_discovery_pipeline(mk_df(rows), cfg, save_paths=None, save_raw=False)
    assert out.iloc[0]["qualification_status"] == "REJECT"


def test_us_only_reject():
    cfg = default_config()
    rows = [
        {
            "site": "indeed",
            "title": "Account Executive",
            "company_name": "Acme",
            "job_url": "https://jobs.acme.com/ae-us",
            "job_url_direct": None,
            "location": "Remote - US only",
            "description": "US candidates only. Sales role.",
            "date_posted": "2026-09-08",
            "is_remote": True,
            "compensation": {"interval": "monthly", "min_amount": 2000, "max_amount": 3000, "currency": "USD"},
            "job_function": "Sales",
        }
    ]
    out = run_discovery_pipeline(mk_df(rows), cfg, save_paths=None, save_raw=False)
    assert out.iloc[0]["qualification_status"] == "REJECT"


def test_emea_worldwide_pass_and_europe_only_review():
    cfg = default_config()
    rows = [
        {
            "site": "indeed",
            "title": "Business Development Representative",
            "company_name": "GlobalCo",
            "job_url": "https://jobs.globalco.com/bdr-emea",
            "job_url_direct": None,
            "location": "Remote - EMEA",
            "description": "We hire across EMEA. Sales development role.",
            "date_posted": "2026-09-08",
            "is_remote": True,
            "compensation": None,
            "job_function": "Sales",
        },
        {
            "site": "indeed",
            "title": "Business Development Representative",
            "company_name": "EuropeCo",
            "job_url": "https://jobs.eu/co/bdr-europe",
            "job_url_direct": None,
            "location": "Remote - Europe only",
            "description": "Remote in Europe only. Sales role.",
            "date_posted": "2026-09-08",
            "is_remote": True,
            "compensation": None,
            "job_function": "Sales",
        },
    ]
    out = run_discovery_pipeline(mk_df(rows), cfg, save_paths=None, save_raw=False)
    assert out.iloc[0]["qualification_status"] == "PASS"
    assert out.iloc[1]["qualification_status"] == "REVIEW"


def test_hybrid_and_onsite_reject():
    cfg = default_config()
    rows = [
        {
            "site": "indeed",
            "title": "Inside Sales",
            "company_name": "Acme",
            "job_url": "https://jobs.acme.com/ins",
            "location": "Hybrid - 3 days in office",
            "description": "Hybrid role, 3 days in office.",
            "date_posted": "2026-09-08",
            "is_remote": False,
            "compensation": None,
            "job_function": "Sales",
        },
        {
            "site": "indeed",
            "title": "Field Sales",
            "company_name": "Acme",
            "job_url": "https://jobs.acme.com/field",
            "location": "Onsite",
            "description": "Must be onsite in Algiers office.",
            "date_posted": "2026-09-08",
            "is_remote": False,
            "compensation": None,
            "job_function": "Sales",
        },
    ]
    out = run_discovery_pipeline(mk_df(rows), cfg, save_paths=None, save_raw=False)
    assert out.iloc[0]["qualification_status"] == "REJECT"
    assert out.iloc[1]["qualification_status"] == "REJECT"


def test_posted_too_old_reject():
    cfg = default_config()
    # older than 7 days
    rows = [
        {
            "site": "indeed",
            "title": "Sales Rep",
            "company_name": "OldCo",
            "job_url": "https://jobs.oldco.com/sales",
            "location": "Remote - Worldwide",
            "description": "Sales role",
            "date_posted": "2026-08-20",
            "is_remote": True,
            "compensation": None,
            "job_function": "Sales",
        }
    ]
    out = run_discovery_pipeline(mk_df(rows), cfg, save_paths=None, save_raw=False)
    assert out.iloc[0]["qualification_status"] == "REJECT"


def test_missing_salary_but_qualifies_pass():
    cfg = default_config()
    rows = [
        {
            "site": "indeed",
            "title": "Account Manager",
            "company_name": "Acme",
            "job_url": "https://jobs.acme.com/am",
            "location": "Remote - Worldwide",
            "description": "Account manager with upsell responsibility. Salary undisclosed.",
            "date_posted": "2026-09-08",
            "is_remote": True,
            "compensation": None,
            "job_function": "Sales",
        }
    ]
    out = run_discovery_pipeline(mk_df(rows), cfg, save_paths=None, save_raw=False)
    assert out.iloc[0]["qualification_status"] == "PASS"


def test_commission_only_reject():
    cfg = default_config()
    rows = [
        {
            "site": "indeed",
            "title": "Sales Agent",
            "company_name": "CommissionCo",
            "job_url": "https://jobs.com/comm",
            "location": "Remote - Worldwide",
            "description": "100% commission only, no base salary",
            "date_posted": "2026-09-08",
            "is_remote": True,
            "compensation": None,
            "job_function": "Sales",
        }
    ]
    out = run_discovery_pipeline(mk_df(rows), cfg, save_paths=None, save_raw=False)
    assert out.iloc[0]["qualification_status"] == "REJECT"


def test_ambiguous_customer_success_review():
    cfg = default_config()
    rows = [
        {
            "site": "indeed",
            "title": "Customer Success Manager",
            "company_name": "Acme",
            "job_url": "https://jobs.acme.com/csm",
            "location": "Remote - Worldwide",
            "description": "Manage accounts and help customers. Some collaboration with sales but no explicit upsell targets.",
            "date_posted": "2026-09-08",
            "is_remote": True,
            "compensation": None,
            "job_function": "Customer Success",
        }
    ]
    out = run_discovery_pipeline(mk_df(rows), cfg, save_paths=None, save_raw=False)
    assert out.iloc[0]["qualification_status"] == "REVIEW"


def test_timezone_compatibility_and_ambiguous_us_timezone():
    cfg = default_config()
    rows = [
        {
            "site": "indeed",
            "title": "Sales Operations",
            "company_name": "Acme",
            "job_url": "https://jobs.acme.com/so",
            "location": "Remote - Worldwide",
            "description": "9am-5pm CET working hours",
            "date_posted": "2026-09-08",
            "is_remote": True,
            "compensation": None,
            "job_function": "Sales",
        },
        {
            "site": "indeed",
            "title": "Sales Ops",
            "company_name": "Acme",
            "job_url": "https://jobs.acme.com/so2",
            "location": "Remote - Worldwide",
            "description": "9am-5pm EST working hours",
            "date_posted": "2026-09-08",
            "is_remote": True,
            "compensation": None,
            "job_function": "Sales",
        },
    ]
    out = run_discovery_pipeline(mk_df(rows), cfg, save_paths=None, save_raw=False)
    assert out.iloc[0]["qualification_status"] == "PASS"
    assert out.iloc[1]["qualification_status"] in ("REVIEW", "PASS")
