# src/ingestion/merge_datasets.py
import os
import json
import logging
from pathlib import Path
import pandas as pd
from rapidfuzz import process, fuzz

logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(message)s')

# Paths
KAGGLE_PATH = Path("data/cleaned/google_play_cleaned.csv")
APPS_JSON = Path("data/raw/app_store_apps.json")
OUT_DIR = Path("data/combined")
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_CSV = OUT_DIR / "combined_apps.csv"
OUT_JSON = OUT_DIR / "combined_apps.json"

# Load Kaggle Google Play dataset
df_kaggle = pd.read_csv(KAGGLE_PATH)

# Load App Store apps metadata
apps = []
if APPS_JSON.exists():
    with APPS_JSON.open("r", encoding="utf-8") as f:
        apps = json.load(f)

df_appstore = pd.DataFrame(apps)

logging.info("Kaggle rows: %d | App Store metadata rows: %d", len(df_kaggle), len(df_appstore))


# --- Utility: Ensure canonical schema ---
def ensure_cols(df, cols_defaults):
    for c, d in cols_defaults.items():
        if c not in df.columns:
            df[c] = d
    return df


canonical_defaults = {
    'app_id': None, 'app_name': None, 'developer': None, 'platform': 'ios',
    'category': None, 'genres': None, 'rating': None, 'ratings_count': None,
    'installs_min': None, 'installs_max': None, 'installs_estimate': None,
    'size_bytes': None, 'price_usd': None, 'is_free': None, 'content_rating': None,
    'last_updated_dt': None, 'days_since_update': None, 'android_version': None,
    'description': None, 'source': 'app_store'
}

df_appstore = ensure_cols(df_appstore, canonical_defaults)

# Normalize datatypes (fix Timestamp issue for JSON export)
for col in ["last_updated_dt"]:
    if col in df_appstore.columns:
        df_appstore[col] = pd.to_datetime(df_appstore[col], errors="coerce").dt.strftime("%Y-%m-%d")

# Add join keys
df_kaggle['join_name'] = df_kaggle['app_name'].astype(str).str.lower().str.strip()
df_kaggle['join_dev'] = df_kaggle['developer'].astype(str).str.lower().str.strip()

df_appstore['join_name'] = df_appstore['app_name'].astype(str).str.lower().str.strip()
df_appstore['join_dev'] = df_appstore['developer'].astype(str).str.lower().str.strip()

# --- Combine datasets ---
combined_rows = []

# 1) All Kaggle rows (Android apps)
for _, kr in df_kaggle.iterrows():
    row = kr.to_dict()
    row['platform'] = 'android'
    row['source'] = row.get('source', 'kaggle')
    combined_rows.append(row)

# 2) App Store rows
for _, ar in df_appstore.iterrows():
    mask = (df_kaggle['join_name'] == ar['join_name']) & (df_kaggle['join_dev'] == ar['join_dev'])
    if mask.any():
        # Same app exists on both platforms → keep both entries
        logging.info("Exact match found: %s (keeping both platforms)", ar['app_name'])
        combined_rows.append(ar.to_dict())
    else:
        # Try fuzzy match
        choices = df_kaggle['join_name'].tolist()
        if ar['join_name'] and len(choices) > 0:
            match = process.extractOne(
                ar['join_name'], 
                choices, 
                scorer=fuzz.token_sort_ratio, 
                score_cutoff=90
            )
            if match:
                logging.info("Fuzzy match (score %d): AppStore '%s' ≈ Kaggle '%s'", match[1], ar['app_name'], match[0])
                combined_rows.append(ar.to_dict())
            else:
                combined_rows.append(ar.to_dict())
        else:
            combined_rows.append(ar.to_dict())

# Build final DataFrame
df_combined = pd.DataFrame(combined_rows)

# Ensure canonical columns
canonical_cols = [
    'app_id','app_name','developer','platform','category','genres','rating','ratings_count',
    'installs_min','installs_max','installs_estimate','size_bytes','price_usd','is_free',
    'content_rating','last_updated_dt','days_since_update','android_version','description','source'
]
for c in canonical_cols:
    if c not in df_combined.columns:
        df_combined[c] = None

# Drop duplicates (same app, same dev, same platform)
df_combined = df_combined.drop_duplicates(
    subset=['app_name', 'developer', 'platform'], keep='first'
).reset_index(drop=True)

# Save
df_combined.to_csv(OUT_CSV, index=False)
df_combined.to_json(OUT_JSON, orient="records", force_ascii=False)
logging.info("Saved combined dataset: %s (rows=%d)", OUT_CSV, len(df_combined))
