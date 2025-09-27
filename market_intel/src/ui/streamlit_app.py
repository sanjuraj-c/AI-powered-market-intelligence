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

# Load data
df = pd.read_csv(COMBINED_PATH)
with INSIGHTS_PATH.open("r", encoding="utf-8") as f:
    insights = json.load(f)

# --- Streamlit UI ---
st.set_page_config(page_title="App Insights Dashboard", layout="wide")
st.title("App Market Insights Dashboard")

# Sidebar filters
st.sidebar.header("Filters")
platform_filter = st.sidebar.multiselect(
    "Platform", options=df["platform"].unique(), default=df["platform"].unique()
)
category_filter = st.sidebar.multiselect(
    "Category", options=df["category"].dropna().unique(), default=df["category"].dropna().unique()
)
rating_filter = st.sidebar.slider("Minimum Rating", min_value=0.0, max_value=5.0, value=0.0)

# Apply filters
df_filtered = df[
    (df["platform"].isin(platform_filter)) &
    (df["category"].isin(category_filter)) &
    (df["rating"] >= rating_filter)
]

st.subheader(f"Filtered Apps ({len(df_filtered)} rows)")
st.dataframe(df_filtered)

# --- Metrics ---
st.subheader("Summary Metrics")
col1, col2, col3 = st.columns(3)
col1.metric("Total Apps", len(df_filtered))
col2.metric("Average Rating", round(df_filtered["rating"].mean(), 2))
col3.metric("Average Ratings Count", int(df_filtered["ratings_count"].mean()))

# --- Interactive Plots ---
st.subheader("Category Ratings")
cat_avg = df_filtered.groupby("category")["rating"].mean().sort_values(ascending=False)
fig, ax = plt.subplots(figsize=(10,5))
cat_avg.plot(kind="bar", ax=ax)
ax.set_ylabel("Average Rating")
ax.set_xlabel("Category")
st.pyplot(fig)

# --- Insights ---
st.subheader("LLM-Synthesized Insights")
for i, ins in enumerate(insights, 1):
    st.markdown(f"**Insight {i}:** {ins.get('insight_text', '')}")
    st.markdown(f"- **Evidence:** {ins.get('evidence', {})}")
    st.markdown(f"- **Confidence Score:** {ins.get('confidence_score', 0)}")
    st.markdown(f"- **Recommendation:** {ins.get('recommendation', '')}")
    st.markdown("---")

# --- Export Report ---
st.subheader("Export Executive Report")
if st.button("Generate Report"):
    report_md = f"# Executive Report\n\n## Metrics\n"
    report_md += f"- Total Apps: {len(df_filtered)}\n"
    report_md += f"- Average Rating: {round(df_filtered['rating'].mean(), 2)}\n"
    report_md += f"- Average Ratings Count: {int(df_filtered['ratings_count'].mean())}\n\n"
    
    report_md += "## LLM Insights\n"
    for i, ins in enumerate(insights, 1):
        report_md += f"### Insight {i}\n"
        report_md += f"- Insight: {ins.get('insight_text', '')}\n"
        report_md += f"- Evidence: {ins.get('evidence', {})}\n"
        report_md += f"- Confidence Score: {ins.get('confidence_score', 0)}\n"
        report_md += f"- Recommendation: {ins.get('recommendation', '')}\n\n"

    # Save markdown
    md_path = Path("report/executive_report.md")
    md_path.parent.mkdir(exist_ok=True)
    md_path.write_text(report_md, encoding="utf-8")

    # Convert to HTML/PDF
    html_path = md_path.with_suffix(".html")
    pdf_path = md_path.with_suffix(".pdf")
    pdfkit.from_file(str(md_path), str(pdf_path))
    st.success(f"Report generated:\n- Markdown: {md_path}\n- PDF: {pdf_path}")
