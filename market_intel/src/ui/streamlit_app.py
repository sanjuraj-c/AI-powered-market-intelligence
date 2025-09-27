# ui/app.py
import streamlit as st
import pandas as pd
import json
import matplotlib.pyplot as plt
from pathlib import Path
from io import BytesIO
import pdfkit

# Paths
COMBINED_PATH = Path("data/combined/combined_apps.csv")
INSIGHTS_PATH = Path("insights/insights_hf.json")

# --- Load data with error handling ---
try:
    df = pd.read_csv(COMBINED_PATH)
except Exception as e:
    st.error(f"Failed to load combined dataset: {e}")
    st.stop()

try:
    with INSIGHTS_PATH.open("r", encoding="utf-8") as f:
        insights = json.load(f)
except Exception as e:
    st.warning(f"Failed to load insights file: {e}")
    insights = []

# --- Streamlit UI ---
st.set_page_config(page_title="App Insights Dashboard", layout="wide")
st.title("App Market Insights Dashboard")

# Sidebar filters
st.sidebar.header("Filters")
platform_options = df["platform"].dropna().unique() if "platform" in df.columns else []
category_options = df["category"].dropna().unique() if "category" in df.columns else []

platform_filter = st.sidebar.multiselect("Platform", options=platform_options, default=platform_options)
category_filter = st.sidebar.multiselect("Category", options=category_options, default=category_options)
rating_filter = st.sidebar.slider("Minimum Rating", min_value=0.0, max_value=5.0, value=0.0)

# Apply filters safely
try:
    df_filtered = df[
        (df["platform"].isin(platform_filter)) &
        (df["category"].isin(category_filter)) &
        (df["rating"] >= rating_filter)
    ]
except Exception as e:
    st.warning(f"Filtering failed: {e}")
    df_filtered = pd.DataFrame()

st.subheader(f"Filtered Apps ({len(df_filtered)} rows)")
try:
    st.dataframe(df_filtered)
except Exception as e:
    st.warning(f"Failed to display dataframe: {e}")

# --- Metrics ---
st.subheader("Summary Metrics")
try:
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Apps", len(df_filtered))
    col2.metric("Average Rating", round(df_filtered.get("rating", pd.Series()).mean(), 2) if not df_filtered.empty else "N/A")
    col3.metric("Average Ratings Count", int(df_filtered.get("ratings_count", pd.Series()).mean()) if not df_filtered.empty else "N/A")
except Exception as e:
    st.warning(f"Failed to compute metrics: {e}")

# --- Interactive Plots ---
st.subheader("Category Ratings")
try:
    if not df_filtered.empty and "category" in df_filtered.columns and "rating" in df_filtered.columns:
        cat_avg = df_filtered.groupby("category")["rating"].mean().sort_values(ascending=False)
        fig, ax = plt.subplots(figsize=(10,5))
        cat_avg.plot(kind="bar", ax=ax)
        ax.set_ylabel("Average Rating")
        ax.set_xlabel("Category")
        st.pyplot(fig)
    else:
        st.info("No data available for plotting.")
except Exception as e:
    st.warning(f"Failed to generate plot: {e}")

# --- Insights ---
st.subheader("LLM-Synthesized Insights")
if insights:
    st.info(f"Total Insights: {len(insights)}")
    for i, ins in enumerate(insights, 1):
        text = ins.get("insight_text") or ins.get("summary_text") or ""
        evidence = ins.get("evidence", {})
        confidence = ins.get("confidence_score", 0)
        recommendation = ins.get("recommendation", "")
        
        st.markdown(f"**Insight {i}:** {text}")
        st.markdown(f"- **Evidence:** {evidence}")
        st.markdown(f"- **Confidence Score:** {confidence}")
        st.markdown(f"- **Recommendation:** {recommendation}")
        st.markdown("---")
else:
    st.info("No insights available.")

# --- Export Report ---
st.subheader("Export Executive Report")
try:
    if st.button("Generate Report"):
        report_md = f"# Executive Report\n\n## Metrics\n"
        report_md += f"- Total Apps: {len(df_filtered)}\n"
        report_md += f"- Average Rating: {round(df_filtered.get('rating', pd.Series()).mean(), 2) if not df_filtered.empty else 'N/A'}\n"
        report_md += f"- Average Ratings Count: {int(df_filtered.get('ratings_count', pd.Series()).mean()) if not df_filtered.empty else 'N/A'}\n\n"

        report_md += "## LLM Insights\n"
        if insights:
            for i, ins in enumerate(insights, 1):
                text = ins.get("insight_text") or ins.get("summary_text") or ""
                evidence = ins.get("evidence", {})
                confidence = ins.get("confidence_score", 0)
                recommendation = ins.get("recommendation", "")
                
                report_md += f"### Insight {i}\n"
                report_md += f"- Insight: {text}\n"
                report_md += f"- Evidence: {evidence}\n"
                report_md += f"- Confidence Score: {confidence}\n"
                report_md += f"- Recommendation: {recommendation}\n\n"
        else:
            report_md += "No insights available.\n"

        # Save markdown + HTML/PDF safely
        md_path = Path("report/executive_report.md")
        md_path.parent.mkdir(exist_ok=True)
        md_path.write_text(report_md, encoding="utf-8")

        html_path = md_path.with_suffix(".html")
        pdf_path = md_path.with_suffix(".pdf")
        try:
            pdfkit.from_file(str(md_path), str(pdf_path))
            st.success(f"Report generated:\n- Markdown: {md_path}\n- PDF: {pdf_path}")
        except Exception as e:
            st.warning(f"PDF generation failed, but markdown saved: {e}\n- Markdown path: {md_path}")
except Exception as e:
    st.warning(f"Report generation failed: {e}")
