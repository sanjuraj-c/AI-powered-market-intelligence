# src/cleaning/clean_utils.py
import re
import numpy as np
import pandas as pd

# --- Parsing helpers ---

def parse_rating(x):
    try:
        return float(x)
    except Exception:
        return np.nan

def parse_price(x):
    if pd.isna(x): return 0.0
    s = str(x).strip()
    if s.lower() in ('free', '0', '0.0', ''):
        return 0.0
    s2 = re.sub(r'[^\d\.]', '', s)
    try:
        return float(s2) if s2 != '' else np.nan
    except:
        return np.nan

def parse_installs_field(s):
    """Parse installs field into (min, max, estimate)."""
    if pd.isna(s): return (np.nan, np.nan, np.nan)
    s = str(s).strip()
    if s == '':
        return (np.nan, np.nan, np.nan)
    s_clean = s.replace(',', '').replace(' ', '')
    if '-' in s_clean:
        parts = [p for p in re.split(r'[-–—]', s_clean) if p]
        try:
            lo = int(re.sub(r'\D','', parts[0]))
            hi = int(re.sub(r'\D','', parts[1])) if len(parts) > 1 else lo
            est = (lo + hi) // 2
            return (lo, hi, est)
        except:
            return (np.nan, np.nan, np.nan)
    val_digits = re.sub(r'\D', '', s_clean)
    if val_digits == '':
        return (np.nan, np.nan, np.nan)
    val = int(val_digits)
    return (val, val, val)

def parse_size_to_bytes(s):
    """Convert app size like '14M', '512k', '1.2G' → bytes."""
    if pd.isna(s): return np.nan
    ss = str(s).strip()
    if ss.lower().startswith('varies'):
        return np.nan
    m = re.match(r'([0-9]*\.?[0-9]+)\s*([kKmMgG])', ss)
    if m:
        num = float(m.group(1))
        unit = m.group(2).lower()
        if unit == 'k': return int(num * 1_000)
        if unit == 'm': return int(num * 1_000_000)
        if unit == 'g': return int(num * 1_000_000_000)
    digits = re.sub(r'\D', '', ss)
    try:
        return int(digits) if digits != '' else np.nan
    except:
        return np.nan

def parse_datetime(s):
    try:
        return pd.to_datetime(s, errors='coerce')
    except Exception:
        return pd.NaT

# --- Column renaming helper ---
def standardize_columns(df):
    rename_map = {}
    for c in df.columns:
        c_low = c.strip().lower()
        if c_low in ('app','app name','name'):
            rename_map[c] = 'app_name'
        elif c_low in ('category',):
            rename_map[c] = 'category'
        elif c_low in ('rating','ratings'):
            rename_map[c] = 'rating'
        elif c_low in ('reviews','review count','number of reviews'):
            rename_map[c] = 'ratings_count'
        elif c_low in ('size',):
            rename_map[c] = 'size'
        elif c_low in ('installs',):
            rename_map[c] = 'installs'
        elif c_low in ('type',):
            rename_map[c] = 'type'
        elif c_low in ('price',):
            rename_map[c] = 'price'
        elif c_low in ('content rating','content_rating'):
            rename_map[c] = 'content_rating'
        elif c_low in ('last updated','last_updated'):
            rename_map[c] = 'last_updated'
        elif c_low in ('android ver','android version','required android version'):
            rename_map[c] = 'android_version'
        elif c_low in ('genres',):
            rename_map[c] = 'genres'
        elif c_low in ('current ver','current_version'):
            rename_map[c] = 'current_version'
        elif c_low in ('app id','appid','app_id'):
            rename_map[c] = 'app_id'
        elif c_low in ('developer','author'):
            rename_map[c] = 'developer'
        elif c_low in ('description','short description'):
            rename_map[c] = 'description'
    return df.rename(columns=rename_map)
