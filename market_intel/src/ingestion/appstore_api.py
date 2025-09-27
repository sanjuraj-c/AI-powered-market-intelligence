# src/ingestion/appstore_api.py
import os
import sys
import time
import json
import logging
from pathlib import Path

import requests
import pandas as pd
from dotenv import load_dotenv

# make clean_utils importable
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../cleaning')))
from clean_utils import parse_rating, parse_price, parse_datetime

# Load env (optional)
load_dotenv()

# --- Config ---
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "df93acc88bmsh7c20f21bceebddap1c07bdjsn01d7a03a2e61")
RAPIDAPI_HOST = os.getenv("RAPIDAPI_HOST", "appstore-scrapper-api.p.rapidapi.com")

HEADERS = {
    "X-RapidAPI-Key": RAPIDAPI_KEY,
    "X-RapidAPI-Host": RAPIDAPI_HOST
}
REVIEWS_BASE = f"https://{RAPIDAPI_HOST}/v1/app-store-api/reviews"
ITUNES_LOOKUP = "https://itunes.apple.com/lookup"

RAW_DIR = Path("data/raw")
RAW_DIR.mkdir(parents=True, exist_ok=True)
APPS_JSON = RAW_DIR / "app_store_apps.json"
REVIEWS_CACHE_DIR = Path("cache/reviews")
REVIEWS_CACHE_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(message)s')

# --- helpers ---
def safe_get(url, headers=None, params=None, max_retries=3, backoff=1):
    for attempt in range(max_retries):
        try:
            r = requests.get(url, headers=headers, params=params, timeout=15)
            if r.status_code == 200:
                return r
            elif r.status_code == 429:
                logging.warning("Rate limit (429). Backing off %ds", backoff * (attempt + 1))
                time.sleep(backoff * (attempt + 1))
            else:
                logging.warning("Unexpected status %d for %s", r.status_code, url)
                return r
        except requests.exceptions.RequestException as e:
            logging.warning("Request exception: %s — retrying", e)
            time.sleep(backoff * (attempt + 1))
    logging.error("Max retries exceeded for %s", url)
    return None

def json_serial(obj):
    """JSON serializer for datetime/Timestamp objects."""
    if isinstance(obj, (pd.Timestamp,)):
        return obj.isoformat()
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    raise TypeError(f"Type {obj.__class__.__name__} not serializable")

# --- Metadata ---
def fetch_app_metadata_from_itunes(app_id, country="us"):
    params = {"id": app_id, "country": country}
    resp = safe_get(ITUNES_LOOKUP, params=params)
    if resp is None or resp.status_code != 200:
        return None
    data = resp.json()
    if data.get("resultCount", 0) > 0:
        return data["results"][0]
    return None

def normalize_itunes_metadata(meta):
    if not meta:
        return None
    return {
        "app_id": meta.get("trackId"),
        "app_name": meta.get("trackName"),
        "developer": meta.get("sellerName") or meta.get("artistName"),
        "platform": "ios",
        "category": meta.get("primaryGenreName"),
        "genres": ", ".join(meta.get("genres", [])) if meta.get("genres") else None,
        "rating": parse_rating(meta.get("averageUserRating")),
        "ratings_count": meta.get("userRatingCount"),
        "price_usd": parse_price(meta.get("price")) if meta.get("price") is not None else 0.0,
        "is_free": (parse_price(meta.get("price")) == 0.0) if meta.get("price") is not None else True,
        "content_rating": meta.get("contentAdvisoryRating"),
        "last_updated_dt": parse_datetime(meta.get("currentVersionReleaseDate") or meta.get("releaseDate")),
        "description": meta.get("description"),
        "source": "app_store_itunes"
    }

# --- Reviews ---
def fetch_reviews_page(app_id, page=1, country="us", lang="en"):
    params = {"id": app_id, "sort": "mostRecent", "page": page, "contry": country, "lang": lang}
    resp = safe_get(REVIEWS_BASE, headers=HEADERS, params=params)
    if resp is None:
        return None
    try:
        return resp.json()
    except Exception:
        logging.exception("Failed to parse JSON for reviews")
        return None

def fetch_all_reviews(app_id, max_pages=3):
    all_reviews = []
    for p in range(1, max_pages + 1):
        data = fetch_reviews_page(app_id, page=p)
        if not data or (isinstance(data, list) and len(data) == 0):
            break
        if isinstance(data, list):
            all_reviews.extend(data)
        elif isinstance(data, dict) and data.get("data"):
            all_reviews.extend(data["data"])
        else:
            break
        time.sleep(0.5)
    if not all_reviews:
        return pd.DataFrame()
    df = pd.DataFrame(all_reviews).drop_duplicates(subset=["id"], keep="first")
    out_path = REVIEWS_CACHE_DIR / f"app_{app_id}_reviews.csv"
    df.to_csv(out_path, index=False)
    logging.info("Saved %d reviews to %s", len(df), out_path)
    return df

# --- Batch runner ---
def fetch_and_cache_apps(app_ids):
    apps = {}
    if APPS_JSON.exists():
        try:
            with APPS_JSON.open("r", encoding="utf-8") as f:
                loaded = json.load(f)
                for a in loaded:
                    apps[str(a.get("app_id"))] = a
        except Exception:
            logging.warning("Failed to load existing cache")

    for aid in app_ids:
        strid = str(aid)
        if strid not in apps:
            meta = fetch_app_metadata_from_itunes(aid)
            norm = normalize_itunes_metadata(meta)
            if norm:
                apps[strid] = norm
                logging.info("Fetched metadata for %s: %s", aid, norm["app_name"])
        # Always fetch reviews
        fetch_all_reviews(aid)
        # Save after each app
        with APPS_JSON.open("w", encoding="utf-8") as f:
            json.dump(list(apps.values()), f, ensure_ascii=False, indent=2, default=json_serial)
    return list(apps.values())

# --- CLI ---
if __name__ == "__main__":
    sample_app_ids = [364709193]
    fetch_and_cache_apps(sample_app_ids)
