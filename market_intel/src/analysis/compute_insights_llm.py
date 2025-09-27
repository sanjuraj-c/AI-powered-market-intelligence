# src/analysis/compute_insights_hf.py
import os
import json
import logging
from pathlib import Path

import pandas as pd
import numpy as np
from transformers import pipeline

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")

# Paths
COMBINED_PATH = Path("data/combined/combined_apps.csv")
OUT_DIR = Path("insights")
OUT_DIR.mkdir(parents=True, exist_ok=True)
RAW_FILE = OUT_DIR / "insights_raw.json"
HF_FILE = OUT_DIR / "insights_hf.json"

# --- Utility: safe stats ---
def safe_mean(series):
    return float(series.mean()) if len(series) > 0 else None

def safe_median(series):
    return float(series.median()) if len(series) > 0 else None

# --- Insight generation ---
def compute_category_metrics(df):
    grouped = df.groupby("category").agg(
        avg_rating=("rating", "mean"),
        median_rating=("rating", "median"),
        app_count=("app_name", "count"),
        avg_ratings_count=("ratings_count", "mean")
    ).reset_index()
    return grouped

def compute_platform_comparison(df):
    results = {}
    for platform in ["android", "ios"]:
        sub = df[df["platform"] == platform]
        results[platform] = {
            "n_apps": len(sub),
            "avg_rating": safe_mean(sub["rating"]),
            "median_rating": safe_median(sub["rating"]),
        }
    return results

def generate_raw_insights(df):
    insights = []

    cat_metrics = compute_category_metrics(df)
    if not cat_metrics.empty:
        top_cat = cat_metrics.sort_values("avg_rating", ascending=False).iloc[0]
        insights.append({
            "insight_text": f"Apps in the '{top_cat['category']}' category have the highest average rating.",
            "evidence": {
                "category": top_cat["category"],
                "avg_rating": round(top_cat["avg_rating"], 2),
                "app_count": int(top_cat["app_count"])
            },
            "confidence_score": 0.9,
            "recommendation": f"Prioritize apps in '{top_cat['category']}' for higher user satisfaction."
        })

    platform_cmp = compute_platform_comparison(df)
    if all(v["avg_rating"] is not None for v in platform_cmp.values()):
        better = max(platform_cmp, key=lambda x: platform_cmp[x]["avg_rating"])
        insights.append({
            "insight_text": f"{better.capitalize()} apps have higher average ratings compared to the other platform.",
            "evidence": platform_cmp,
            "confidence_score": 0.8,
            "recommendation": f"Focus marketing and development efforts on {better} apps."
        })

    if "installs_estimate" in df.columns:
        popular_low = df[(df["rating"] < 3.0) & (df["installs_estimate"].notna())]
        if not popular_low.empty:
            worst = popular_low.sort_values("installs_estimate", ascending=False).iloc[0]
            insights.append({
                "insight_text": f"App '{worst['app_name']}' has high installs but low ratings (<3).",
                "evidence": {
                    "app_name": worst["app_name"],
                    "rating": worst["rating"],
                    "installs_estimate": int(worst["installs_estimate"])
                },
                "confidence_score": 0.85,
                "recommendation": "Investigate poor reviews for this high-install app to identify quick wins."
            })

    return insights

# --- Hugging Face LLM synthesis with structured few-shot ---
def synthesize_with_hf(raw_insights):
    examples = [
        {
            "insight_text": "Apps in the 'Productivity' category have the highest average rating.",
            "evidence": {"category": "Productivity", "avg_rating": 4.7, "app_count": 120},
            "confidence_score": 0.9,
            "recommendation": "Prioritize apps in 'Productivity' for higher user satisfaction."
        },
        {
            "insight_text": "iOS apps have slightly higher ratings than Android apps.",
            "evidence": {"ios_avg": 4.3, "android_avg": 4.1},
            "confidence_score": 0.8,
            "recommendation": "Consider focusing marketing campaigns on iOS users."
        }
    ]

    prompt = (
        "You are an analytics assistant. Rewrite the following raw insights into concise, "
        "human-friendly summaries in JSON format with keys: summary_text, evidence, confidence_score, recommendation.\n\n"
        f"Examples:\n{json.dumps(examples, indent=2)}\n\n"
        f"Raw Insights:\n{json.dumps(raw_insights, indent=2)}\n\n"
        "Return a JSON array where each element follows the example structure."
    )

    try:
        synth_pipeline = pipeline(
            "text2text-generation",
            model="google/flan-t5-small",
            device=0 if os.environ.get("USE_GPU", "0") == "1" else -1
        )
        result = synth_pipeline(prompt, max_new_tokens=512)
        generated_text = result[0]["generated_text"]

        # Try to parse JSON
        return json.loads(generated_text)
    except Exception as e:
        logging.warning("HF synthesis failed: %s", e)
        return raw_insights  # fallback to raw

# --- Main ---
if __name__ == "__main__":
    if not COMBINED_PATH.exists():
        raise FileNotFoundError(f"Missing input file: {COMBINED_PATH}")

    df = pd.read_csv(COMBINED_PATH)
    logging.info("Loaded combined dataset with %d rows", len(df))

    raw_insights = generate_raw_insights(df)
    with open(RAW_FILE, "w", encoding="utf-8") as f:
        json.dump(raw_insights, f, ensure_ascii=False, indent=2)
    logging.info("Saved raw insights: %s", RAW_FILE)

    hf_insights = synthesize_with_hf(raw_insights)
    with open(HF_FILE, "w", encoding="utf-8") as f:
        json.dump(hf_insights, f, ensure_ascii=False, indent=2)
    logging.info("Saved Hugging Face-synthesized insights: %s", HF_FILE)
