from __future__ import annotations

import json
import os
from typing import Dict, Optional

import pandas as pd

from jobspy.cleaning import clean_raw_df, deduplicate
from jobspy.config import default_config, Config
from jobspy.qualification import qualify_df


def run_discovery_pipeline(
    jobs_df: pd.DataFrame,
    cfg: Optional[Config] = None,
    save_paths: Optional[Dict[str, str]] = None,
    save_raw: bool = True,
) -> pd.DataFrame:
    """Run cleaning -> dedupe -> qualification and optionally save artifacts.

    Parameters
    - jobs_df: DataFrame returned by scrape_jobs()
    - cfg: Config object (default_config() if None)
    - save_paths: dict with keys: raw, clean, qualified, rejected pointing to directories
    - save_raw: whether to save the original raw DataFrame as JSONL

    Returns: annotated DataFrame with qualification columns
    """
    cfg = cfg or default_config()

    # Step 0: save raw if requested
    if save_paths and save_raw:
        raw_dir = save_paths.get("raw")
        if raw_dir:
            os.makedirs(raw_dir, exist_ok=True)
            raw_file = os.path.join(raw_dir, "jobs_raw.jsonl")
            with open(raw_file, "w", encoding="utf-8") as fh:
                for _, row in jobs_df.iterrows():
                    json.dump(row.to_dict(), fh, default=str)
                    fh.write("\n")

    # Step 1: cleaning
    clean_df = clean_raw_df(jobs_df, cfg)

    # optional: save clean
    if save_paths and save_paths.get("clean"):
        os.makedirs(save_paths.get("clean"), exist_ok=True)
        clean_df.to_parquet(os.path.join(save_paths.get("clean"), "jobs_clean.parquet"))

    # Step 2: dedupe
    deduped_df, duplicates_map = deduplicate(clean_df)
    # attach duplicate counts into a column
    if not deduped_df.empty:
        deduped_df["duplicate_count"] = deduped_df["job_id"].map(lambda j: len(duplicates_map.get(j, [])))

    # Step 3: qualification
    qualified_df = qualify_df(deduped_df, cfg)

    # split and optionally save qualified/rejected
    if save_paths and save_paths.get("qualified"):
        os.makedirs(save_paths.get("qualified"), exist_ok=True)
        qualified_df.to_parquet(os.path.join(save_paths.get("qualified"), "jobs_qualified.parquet"))

    if save_paths and save_paths.get("rejected"):
        os.makedirs(save_paths.get("rejected"), exist_ok=True)
        rejected = qualified_df[qualified_df["qualification_status"] == "REJECT"]
        rejected.to_parquet(os.path.join(save_paths.get("rejected"), "jobs_rejected.parquet"))

    return qualified_df
