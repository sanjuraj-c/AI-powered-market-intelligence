# src/confidence.py
import numpy as np
from scipy import stats

def pvalue_category_vs_rest(df, category_col, metric_col, category):
    a = df[df[category_col]==category][metric_col].dropna()
    b = df[df[category_col]!=category][metric_col].dropna()
    if len(a) < 5 or len(b) < 5:
        return 1.0
    t, p = stats.ttest_ind(a, b, equal_var=False, nan_policy='omit')
    return p
