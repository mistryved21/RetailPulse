"""Data preprocessing agent for RetailPulse.

Handles: data cleaning, missing values, duplicates, type detection,
feature engineering, and data quality scoring.
"""
import logging
import re
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# DATA CLEANING
# ══════════════════════════════════════════════════════════════════════════════

def clean_data(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Full data cleaning pipeline.

    Steps:
        1. Remove completely empty rows/columns
        2. Standardize column names (snake_case)
        3. Remove duplicates
        4. Auto-detect and convert data types
        5. Handle missing values
        6. Flag outliers

    Args:
        df: Raw DataFrame

    Returns:
        tuple of (cleaned_df, cleaning_report)
    """
    report = {
        "original_rows": len(df),
        "original_columns": len(df.columns),
        "steps": [],
        "issues_found": 0,
        "issues_fixed": 0,
    }

    logger.info(f"Starting data cleaning: {len(df)} rows, {len(df.columns)} columns")

    # Step 1: Remove empty rows/columns
    empty_rows = df.isna().all(axis=1).sum()
    empty_cols = df.isna().all(axis=0).sum()
    df = df.dropna(how="all").dropna(axis=1, how="all")
    if empty_rows > 0 or empty_cols > 0:
        report["steps"].append(f"Removed {empty_rows} empty rows, {empty_cols} empty columns")
        report["issues_found"] += empty_rows + empty_cols
        report["issues_fixed"] += empty_rows + empty_cols

    # Step 2: Standardize column names
    original_cols = list(df.columns)
    df.columns = [_standardize_column_name(col) for col in df.columns]
    renamed = sum(1 for a, b in zip(original_cols, df.columns) if a != b)
    if renamed > 0:
        report["steps"].append(f"Standardized {renamed} column names to snake_case")

    # Step 3: Remove duplicates
    dup_count = df.duplicated().sum()
    if dup_count > 0:
        df = df.drop_duplicates().reset_index(drop=True)
        report["steps"].append(f"Removed {dup_count} duplicate rows")
        report["issues_found"] += dup_count
        report["issues_fixed"] += dup_count

    # Step 4: Auto-detect data types
    type_fixes = _auto_detect_types(df)
    if type_fixes:
        report["steps"].append(f"Auto-converted {len(type_fixes)} column types: {type_fixes}")

    # Step 5: Handle missing values
    missing_before = df.isna().sum().sum()
    if missing_before > 0:
        df = _handle_missing_values(df)
        missing_after = df.isna().sum().sum()
        fixed = missing_before - missing_after
        report["steps"].append(
            f"Handled {missing_before} missing values ({fixed} filled, {missing_after} remaining)"
        )
        report["issues_found"] += missing_before
        report["issues_fixed"] += fixed

    # Step 6: Flag outliers
    outlier_count = _count_outliers(df)
    if outlier_count > 0:
        report["steps"].append(f"Detected {outlier_count} potential outliers (> 3 std deviations)")
        report["issues_found"] += outlier_count

    # Final stats
    report["final_rows"] = len(df)
    report["final_columns"] = len(df.columns)
    report["data_quality_score"] = _calculate_quality_score(df)
    report["column_types"] = {col: str(dtype) for col, dtype in df.dtypes.items()}

    logger.info(
        f"Cleaning done: {report['issues_found']} issues found, "
        f"{report['issues_fixed']} fixed, quality={report['data_quality_score']}%"
    )
    return df, report


def _standardize_column_name(name: str) -> str:
    """Convert column name to clean snake_case."""
    name = str(name).strip()
    # Replace spaces and special chars with underscore
    name = re.sub(r"[^\w\s]", "", name)
    name = re.sub(r"\s+", "_", name)
    # Convert camelCase to snake_case
    name = re.sub(r"([a-z])([A-Z])", r"\1_\2", name)
    return name.lower().strip("_")


def _auto_detect_types(df: pd.DataFrame) -> dict:
    """Auto-detect and convert column data types."""
    fixes = {}
    for col in df.columns:
        if df[col].dtype == object:
            # Try numeric
            numeric = pd.to_numeric(df[col], errors="coerce")
            non_null = df[col].dropna()
            if non_null.empty:
                continue
            numeric_ratio = numeric.notna().sum() / len(non_null)
            if numeric_ratio > 0.8:
                df[col] = numeric
                fixes[col] = "numeric"
                continue

            # Try datetime
            try:
                dt = pd.to_datetime(df[col], errors="coerce", infer_datetime_format=True)
                dt_ratio = dt.notna().sum() / len(non_null)
                if dt_ratio > 0.8:
                    df[col] = dt
                    fixes[col] = "datetime"
                    continue
            except Exception:
                pass

            # Check if boolean
            unique = set(non_null.str.lower().unique())
            if unique.issubset({"true", "false", "yes", "no", "1", "0", "y", "n"}):
                mapping = {"true": True, "yes": True, "1": True, "y": True,
                           "false": False, "no": False, "0": False, "n": False}
                df[col] = non_null.str.lower().map(mapping)
                fixes[col] = "boolean"

    return fixes


def _handle_missing_values(df: pd.DataFrame) -> pd.DataFrame:
    """Handle missing values based on column type."""
    for col in df.columns:
        missing = df[col].isna().sum()
        if missing == 0:
            continue

        missing_pct = missing / len(df) * 100

        # If > 70% missing, leave as is (too much to fill)
        if missing_pct > 70:
            continue

        if pd.api.types.is_numeric_dtype(df[col]):
            # Fill numeric with median
            df[col] = df[col].fillna(df[col].median())
        elif pd.api.types.is_datetime64_any_dtype(df[col]):
            # Interpolate dates
            df[col] = df[col].interpolate(method="pad")
        else:
            # Fill text with mode
            mode = df[col].mode()
            if not mode.empty:
                df[col] = df[col].fillna(mode.iloc[0])

    return df


def _count_outliers(df: pd.DataFrame) -> int:
    """Count outliers using Z-score method (> 3 std deviations)."""
    count = 0
    for col in df.select_dtypes(include=[np.number]).columns:
        if df[col].std() == 0:
            continue
        z_scores = np.abs((df[col] - df[col].mean()) / df[col].std())
        count += (z_scores > 3).sum()
    return int(count)


def _calculate_quality_score(df: pd.DataFrame) -> int:
    """Calculate data quality score (0-100)."""
    if df.empty:
        return 0

    scores = []

    # Completeness (no missing values)
    completeness = 1 - (df.isna().sum().sum() / (len(df) * len(df.columns)))
    scores.append(completeness * 40)  # 40% weight

    # No duplicates
    dup_ratio = 1 - (df.duplicated().sum() / max(len(df), 1))
    scores.append(dup_ratio * 20)  # 20% weight

    # Consistent types (columns have uniform types)
    type_score = sum(1 for col in df.columns if df[col].dtype != object) / max(len(df.columns), 1)
    scores.append(type_score * 20)  # 20% weight

    # Row count (having enough data)
    row_score = min(len(df) / 100, 1.0)
    scores.append(row_score * 20)  # 20% weight

    return int(sum(scores))


# ══════════════════════════════════════════════════════════════════════════════
# FEATURE ENGINEERING
# ══════════════════════════════════════════════════════════════════════════════

def engineer_features(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Auto-generate useful features from the data.

    Detects column types and creates relevant features:
    - Date features: day_of_week, month, quarter, year, is_weekend
    - Revenue: quantity × price
    - Profit margin: (price - cost) / price × 100
    - Moving averages: 7-day, 30-day
    - Growth rate: period-over-period % change
    - Category encoding: label encode text columns

    Args:
        df: Cleaned DataFrame

    Returns:
        tuple of (enhanced_df, list of new feature names)
    """
    new_features = []
    df = df.copy()

    logger.info(f"Starting feature engineering on {len(df.columns)} columns")

    # ── Date Features ─────────────────────────────────────────────────────
    date_cols = df.select_dtypes(include=["datetime64"]).columns.tolist()
    for col in date_cols:
        # Day of week
        feat = f"{col}_day_of_week"
        df[feat] = df[col].dt.day_name()
        new_features.append(feat)

        # Month
        feat = f"{col}_month"
        df[feat] = df[col].dt.month_name()
        new_features.append(feat)

        # Quarter
        feat = f"{col}_quarter"
        df[feat] = df[col].dt.quarter
        new_features.append(feat)

        # Year
        feat = f"{col}_year"
        df[feat] = df[col].dt.year
        new_features.append(feat)

        # Is weekend
        feat = f"{col}_is_weekend"
        df[feat] = df[col].dt.dayofweek.isin([5, 6])
        new_features.append(feat)

    # ── Revenue Calculation ───────────────────────────────────────────────
    qty_cols = [c for c in df.columns if any(k in c.lower() for k in ["quantity", "qty", "units", "count"])]
    price_cols = [c for c in df.columns if any(k in c.lower() for k in ["price", "unit_price", "rate"])]

    if qty_cols and price_cols:
        qty_col = qty_cols[0]
        price_col = price_cols[0]
        if pd.api.types.is_numeric_dtype(df[qty_col]) and pd.api.types.is_numeric_dtype(df[price_col]):
            # Check if revenue column already exists
            if not any("revenue" in c.lower() or "total" in c.lower() for c in df.columns):
                df["calculated_revenue"] = df[qty_col] * df[price_col]
                new_features.append("calculated_revenue")

    # ── Profit Margin ─────────────────────────────────────────────────────
    cost_cols = [c for c in df.columns if any(k in c.lower() for k in ["cost", "cogs", "expense"])]
    if price_cols and cost_cols:
        price_col = price_cols[0]
        cost_col = cost_cols[0]
        if pd.api.types.is_numeric_dtype(df[price_col]) and pd.api.types.is_numeric_dtype(df[cost_col]):
            df["profit_margin_pct"] = ((df[price_col] - df[cost_col]) / df[price_col] * 100).round(2)
            new_features.append("profit_margin_pct")

    # ── Moving Averages ───────────────────────────────────────────────────
    value_cols = [c for c in df.columns if any(k in c.lower()
                  for k in ["revenue", "sales", "amount", "total", "value"])]
    if date_cols and value_cols:
        val_col = value_cols[0]
        if pd.api.types.is_numeric_dtype(df[val_col]):
            sorted_df = df.sort_values(date_cols[0])
            if len(sorted_df) >= 7:
                df["moving_avg_7d"] = sorted_df[val_col].rolling(window=7, min_periods=1).mean().round(2)
                new_features.append("moving_avg_7d")
            if len(sorted_df) >= 30:
                df["moving_avg_30d"] = sorted_df[val_col].rolling(window=30, min_periods=1).mean().round(2)
                new_features.append("moving_avg_30d")

    # ── Growth Rate ───────────────────────────────────────────────────────
    if value_cols:
        val_col = value_cols[0]
        if pd.api.types.is_numeric_dtype(df[val_col]):
            df["growth_rate_pct"] = df[val_col].pct_change().mul(100).round(2)
            new_features.append("growth_rate_pct")

    # ── Category Encoding ─────────────────────────────────────────────────
    cat_cols = df.select_dtypes(include=["object"]).columns.tolist()
    for col in cat_cols:
        n_unique = df[col].nunique()
        # Only encode if reasonable number of categories (2-20)
        if 2 <= n_unique <= 20:
            feat = f"{col}_encoded"
            df[feat] = df[col].astype("category").cat.codes
            new_features.append(feat)

    logger.info(f"Feature engineering complete: {len(new_features)} new features created")
    return df, new_features


# ══════════════════════════════════════════════════════════════════════════════
# DATA SUMMARY
# ══════════════════════════════════════════════════════════════════════════════

def get_data_summary(df: pd.DataFrame) -> dict:
    """Generate comprehensive data summary statistics.

    Args:
        df: DataFrame to summarize

    Returns:
        dict with summary statistics
    """
    summary = {
        "rows": len(df),
        "columns": len(df.columns),
        "memory_mb": round(df.memory_usage(deep=True).sum() / 1024 / 1024, 2),
        "missing_total": int(df.isna().sum().sum()),
        "missing_pct": round(df.isna().sum().sum() / (len(df) * len(df.columns)) * 100, 1)
        if len(df) > 0 else 0,
        "duplicates": int(df.duplicated().sum()),
        "numeric_columns": list(df.select_dtypes(include=[np.number]).columns),
        "text_columns": list(df.select_dtypes(include=["object"]).columns),
        "date_columns": list(df.select_dtypes(include=["datetime64"]).columns),
        "column_details": {},
    }

    for col in df.columns:
        detail = {
            "dtype": str(df[col].dtype),
            "missing": int(df[col].isna().sum()),
            "unique": int(df[col].nunique()),
        }
        if pd.api.types.is_numeric_dtype(df[col]):
            detail.update({
                "min": float(df[col].min()) if not df[col].isna().all() else None,
                "max": float(df[col].max()) if not df[col].isna().all() else None,
                "mean": round(float(df[col].mean()), 2) if not df[col].isna().all() else None,
                "median": round(float(df[col].median()), 2) if not df[col].isna().all() else None,
            })
        elif df[col].dtype == object:
            top = df[col].value_counts().head(5).to_dict()
            detail["top_values"] = top

        summary["column_details"][col] = detail

    return summary
