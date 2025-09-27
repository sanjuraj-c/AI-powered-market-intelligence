# src/cleaning/kaggle_clean.py
import os
import logging
import numpy as np
import pandas as pd
from datetime import datetime

from clean_utils import (
    parse_rating, parse_price, parse_installs_field,
    parse_size_to_bytes, parse_datetime, standardize_columns
)

logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(message)s')

def clean_kaggle_playstore(df, source_name='kaggle'):
    logging.info("Starting cleaning pipeline...")
    df = standardize_columns(df)

    # Ensure expected columns exist
    for col in ['app_name','category','size','installs','price','rating','ratings_count','last_updated','developer']:
        if col not in df.columns:
            df[col] = np.nan

    # Parse fields
    df['rating'] = df['rating'].apply(parse_rating)
    df['ratings_count'] = pd.to_numeric(df['ratings_count'], errors='coerce')

    installs_expanded = df['installs'].apply(
        lambda x: pd.Series(parse_installs_field(x), index=['installs_min','installs_max','installs_estimate'])
    )
    df = pd.concat([df, installs_expanded], axis=1)

    df['size_bytes'] = df['size'].apply(parse_size_to_bytes)
    df['price_usd'] = df['price'].apply(parse_price)
    df['is_free'] = df['price_usd'].fillna(0.0) == 0.0

    df['last_updated_dt'] = df['last_updated'].apply(parse_datetime)
    df['days_since_update'] = (pd.Timestamp.now(tz=None) - df['last_updated_dt']).dt.days
    df['platform'] = 'android'
    df['source'] = source_name

    # Normalize strings
    if 'category' in df.columns:
        df['category'] = df['category'].astype(str).str.strip().replace({'nan': None}).str.title()
    if 'developer' in df.columns:
        df['developer'] = df['developer'].astype(str).str.strip()

    # Deduplicate
    df = df.sort_values(by=['app_name','developer','last_updated_dt','rating'],
                        ascending=[True,True,False,False])
    df = df.drop_duplicates(subset=['app_name','developer'], keep='first').reset_index(drop=True)

    # Canonical schema
    canonical_cols = [
        'app_id','app_name','developer','platform','category','genres','rating','ratings_count',
        'installs_min','installs_max','installs_estimate','size_bytes','price_usd','is_free',
        'content_rating','last_updated_dt','days_since_update','android_version','description','source'
    ]
    for c in canonical_cols:
        if c not in df.columns:
            df[c] = np.nan

    result = df[canonical_cols].copy()
    logging.info("Cleaning complete. Rows: %d", len(result))
    return result

def save_clean(df, out_dir='data/cleaned', filename='google_play_cleaned.csv'):
    os.makedirs(out_dir, exist_ok=True)
    csv_path = os.path.join(out_dir, filename)
    json_path = csv_path.replace('.csv', '.json')
    df.to_csv(csv_path, index=False)
    df.to_json(json_path, orient='records')
    logging.info("Saved cleaned CSV -> %s and JSON -> %s", csv_path, json_path)
    return csv_path, json_path

if __name__ == '__main__':
    raw_path = 'data/raw/googleplaystore.csv'  # adjust if needed
    if not os.path.exists(raw_path):
        logging.error("Raw path not found: %s", raw_path)
        raise SystemExit(1)
    df_raw = pd.read_csv(raw_path)
    df_clean = clean_kaggle_playstore(df_raw)
    save_clean(df_clean)
