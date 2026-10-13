"""Provider-Independent Normalized Retail Analytics Engine for RetailPulse.

Operates on a standardized internal retail data model regardless of whether the source
is CSV, Excel, PostgreSQL, MySQL, SQLite, or Snowflake.
"""
import logging
from typing import Any, Optional
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Standard field mappings and aliases
FIELD_ALIASES = {
    "transaction_id": ["transaction_id", "transaction id", "order_id", "order id", "invoice_no", "invoice no", "id", "trans_id"],
    "date": ["date", "sale_date", "sale date", "order_date", "order date", "transaction_date", "timestamp", "datetime"],
    "customer_id": ["customer_id", "customer id", "customer", "customer_code", "client_id", "user_id"],
    "customer_name": ["customer_name", "customer name", "name", "client_name", "full_name", "buyer_name"],
    "category": ["category", "product_category", "product category", "category_name", "department"],
    "product_name": ["product_name", "product name", "product", "item_name", "item name", "item"],
    "product_id": ["product_id", "product id", "sku", "product_sku", "item_code"],
    "quantity": ["quantity", "qty", "units", "units_sold", "volume", "count"],
    "unit_price": ["price_per_unit", "price per unit", "unit_price", "unit price", "price", "rate"],
    "revenue": ["total_amount", "total amount", "total", "amount", "revenue", "sales", "net_amount", "total_sales"],
    "cost": ["cost", "cogs", "cost_of_goods", "product_cost", "total_cost"],
    "profit": ["profit", "gross_profit", "net_profit", "margin"],
    "payment_method": ["payment_method", "payment method", "payment", "payment_type", "payment_mode"],
    "region": ["region", "zone", "territory", "area"],
    "city": ["city", "town", "location"],
    "state": ["state", "province"]
}


def normalize_dataframe(df: pd.DataFrame, custom_mapping: dict = None) -> pd.DataFrame:
    """Normalize any arbitrary retail DataFrame into standard fields.
    
    Args:
        df: Input raw or cleaned DataFrame
        custom_mapping: Optional user-defined mapping {standard_field: df_column}
        
    Returns:
        Normalized DataFrame with standard columns
    """
    norm_df = pd.DataFrame()
    col_map = {}
    
    # 1. Apply custom mapping if provided
    if custom_mapping:
        for std_field, df_col in custom_mapping.items():
            if df_col in df.columns:
                col_map[std_field] = df_col
                
    # 2. Auto-detect remaining fields from aliases
    df_cols_lower = {c.lower().strip().replace("-", "_").replace(" ", "_"): c for c in df.columns}
    for std_field, aliases in FIELD_ALIASES.items():
        if std_field not in col_map:
            for alias in aliases:
                alias_norm = alias.lower().replace("-", "_").replace(" ", "_")
                if alias_norm in df_cols_lower:
                    col_map[std_field] = df_cols_lower[alias_norm]
                    break

    # 3. Extract and cast standard fields
    for std_field, src_col in col_map.items():
        norm_df[std_field] = df[src_col]
        
    # Copy unmapped columns as-is
    for col in df.columns:
        if col not in col_map.values():
            norm_df[col] = df[col]

    # Ensure numeric columns
    for num_col in ["quantity", "unit_price", "revenue", "cost", "profit"]:
        if num_col in norm_df.columns:
            norm_df[num_col] = pd.to_numeric(norm_df[num_col], errors="coerce").fillna(0.0)
            
    # Calculate derived financial fields if missing
    if "quantity" in norm_df.columns and "unit_price" in norm_df.columns:
        if "revenue" not in norm_df.columns or (norm_df["revenue"] == 0).all():
            norm_df["revenue"] = norm_df["quantity"] * norm_df["unit_price"]
            
    if "revenue" in norm_df.columns:
        if "cost" not in norm_df.columns:
            norm_df["cost"] = norm_df["revenue"] * 0.70  # Estimated 70% COGS benchmark
        if "profit" not in norm_df.columns:
            norm_df["profit"] = norm_df["revenue"] - norm_df["cost"]
        norm_df["margin_pct"] = np.where(norm_df["revenue"] > 0, (norm_df["profit"] / norm_df["revenue"]) * 100, 0.0)

    # Standardize dates
    if "date" in norm_df.columns:
        norm_df["date"] = pd.to_datetime(norm_df["date"], errors="coerce")
    else:
        norm_df["date"] = pd.date_range(end=pd.Timestamp.now(), periods=len(norm_df), freq="D")
        
    return norm_df


def compute_executive_metrics(df: pd.DataFrame) -> dict:
    """Calculate core executive retail KPIs."""
    if df.empty:
        return {
            "total_revenue": 0.0, "total_orders": 0, "total_units": 0, "aov": 0.0,
            "total_profit": 0.0, "gross_margin_pct": 0.0, "total_customers": 0,
            "new_customers": 0, "repeat_customers": 0, "revenue_per_customer": 0.0
        }

    total_revenue = float(df["revenue"].sum()) if "revenue" in df.columns else 0.0
    total_orders = len(df)
    total_units = int(df["quantity"].sum()) if "quantity" in df.columns else total_orders
    aov = total_revenue / total_orders if total_orders > 0 else 0.0
    
    total_profit = float(df["profit"].sum()) if "profit" in df.columns else (total_revenue * 0.3)
    gross_margin_pct = (total_profit / total_revenue * 100) if total_revenue > 0 else 0.0
    
    # Customers
    if "customer_id" in df.columns:
        total_cust = df["customer_id"].nunique()
        order_counts = df["customer_id"].value_counts()
        repeat_cust = int((order_counts > 1).sum())
        new_cust = total_cust - repeat_cust
    else:
        total_cust = int(total_orders * 0.7)
        repeat_cust = int(total_cust * 0.3)
        new_cust = total_cust - repeat_cust
        
    rev_per_cust = total_revenue / total_cust if total_cust > 0 else 0.0

    return {
        "total_revenue": round(total_revenue, 2),
        "total_orders": total_orders,
        "total_units": total_units,
        "aov": round(aov, 2),
        "total_profit": round(total_profit, 2),
        "gross_margin_pct": round(gross_margin_pct, 2),
        "total_customers": total_cust,
        "new_customers": new_cust,
        "repeat_customers": repeat_cust,
        "revenue_per_customer": round(rev_per_cust, 2)
    }


def compute_period_comparison(df: pd.DataFrame) -> dict:
    """Compare recent period vs previous period performance."""
    if df.empty or "date" not in df.columns or df["date"].isna().all():
        return {
            "has_comparison": False,
            "revenue_growth": 0.0,
            "profit_growth": 0.0,
            "orders_growth": 0.0,
            "status": "Stable"
        }

    valid_dates = df.dropna(subset=["date"]).sort_values("date")
    if len(valid_dates) < 4:
        return {
            "has_comparison": False, "revenue_growth": 0.0,
            "profit_growth": 0.0, "orders_growth": 0.0, "status": "Stable"
        }

    # Split into two equal halves (Recent Period vs Prior Period)
    mid_idx = len(valid_dates) // 2
    prior_df = valid_dates.iloc[:mid_idx]
    recent_df = valid_dates.iloc[mid_idx:]

    recent_rev = recent_df["revenue"].sum() if "revenue" in recent_df.columns else 0.0
    prior_rev = prior_df["revenue"].sum() if "revenue" in prior_df.columns else 0.0
    rev_growth = ((recent_rev - prior_rev) / prior_rev * 100) if prior_rev > 0 else 0.0

    recent_prof = recent_df["profit"].sum() if "profit" in recent_df.columns else 0.0
    prior_prof = prior_df["profit"].sum() if "profit" in prior_df.columns else 0.0
    prof_growth = ((recent_prof - prior_prof) / prior_prof * 100) if prior_prof > 0 else 0.0

    recent_orders = len(recent_df)
    prior_orders = len(prior_df)
    orders_growth = ((recent_orders - prior_orders) / prior_orders * 100) if prior_orders > 0 else 0.0

    # Determine business status
    if rev_growth >= 10.0 and prof_growth >= 5.0:
        status = "Excellent"
    elif rev_growth >= 0.0:
        status = "Good"
    elif rev_growth >= -10.0:
        status = "Warning"
    else:
        status = "Critical"

    return {
        "has_comparison": True,
        "recent_revenue": round(recent_rev, 2),
        "prior_revenue": round(prior_rev, 2),
        "revenue_growth": round(rev_growth, 2),
        "recent_profit": round(recent_prof, 2),
        "prior_profit": round(prior_prof, 2),
        "profit_growth": round(prof_growth, 2),
        "orders_growth": round(orders_growth, 2),
        "status": status
    }


def compute_category_and_product_analytics(df: pd.DataFrame) -> dict:
    """Analyze breakdown by Category and Products."""
    res = {
        "category_performance": [],
        "top_products": [],
        "bottom_products": [],
        "best_category": "N/A",
        "worst_category": "N/A"
    }
    
    if df.empty:
        return res

    # Category breakdown
    cat_col = "category" if "category" in df.columns else ("product_category" if "product_category" in df.columns else None)
    if cat_col and "revenue" in df.columns:
        cat_grp = df.groupby(cat_col).agg(
            revenue=("revenue", "sum"),
            profit=("profit", "sum") if "profit" in df.columns else ("revenue", lambda s: s.sum() * 0.3),
            orders=("revenue", "count"),
            units=("quantity", "sum") if "quantity" in df.columns else ("revenue", "count")
        ).reset_index().sort_values("revenue", ascending=False)
        
        cat_grp["margin_pct"] = np.where(cat_grp["revenue"] > 0, (cat_grp["profit"] / cat_grp["revenue"]) * 100, 0.0)
        res["category_performance"] = cat_grp.to_dict(orient="records")
        if not cat_grp.empty:
            res["best_category"] = cat_grp.iloc[0][cat_col]
            res["worst_category"] = cat_grp.iloc[-1][cat_col]

    # Product breakdown
    prod_col = "product_name" if "product_name" in df.columns else ("product" if "product" in df.columns else None)
    if prod_col and "revenue" in df.columns:
        prod_grp = df.groupby(prod_col).agg(
            revenue=("revenue", "sum"),
            profit=("profit", "sum") if "profit" in df.columns else ("revenue", lambda s: s.sum() * 0.3),
            units=("quantity", "sum") if "quantity" in df.columns else ("revenue", "count")
        ).reset_index().sort_values("revenue", ascending=False)
        
        res["top_products"] = prod_grp.head(5).to_dict(orient="records")
        res["bottom_products"] = prod_grp.tail(5).to_dict(orient="records")

    return res


def compute_regional_analytics(df: pd.DataFrame) -> dict:
    """Analyze breakdown by Region / Geography."""
    res = {
        "regional_performance": [],
        "best_region": "N/A",
        "worst_region": "N/A"
    }
    if df.empty or "region" not in df.columns or "revenue" not in df.columns:
        return res

    reg_grp = df.groupby("region").agg(
        revenue=("revenue", "sum"),
        profit=("profit", "sum") if "profit" in df.columns else ("revenue", lambda s: s.sum() * 0.3),
        orders=("revenue", "count")
    ).reset_index().sort_values("revenue", ascending=False)

    res["regional_performance"] = reg_grp.to_dict(orient="records")
    if not reg_grp.empty:
        res["best_region"] = reg_grp.iloc[0]["region"]
        res["worst_region"] = reg_grp.iloc[-1]["region"]

    return res


def detect_business_problems(df: pd.DataFrame, exec_metrics: dict, comparison: dict, cat_prod: dict, reg_info: dict) -> list[dict]:
    """Automated Business Problem and Risk Detection Engine."""
    problems = []

    # 1. Revenue Decline
    if comparison.get("revenue_growth", 0.0) < -8.0:
        problems.append({
            "title": "Revenue Contraction Alert",
            "severity": "Critical" if comparison.get("revenue_growth", 0.0) < -15.0 else "Warning",
            "metric": f"Revenue Growth: {comparison.get('revenue_growth')}%",
            "evidence": f"Total revenue declined from ₹{comparison.get('prior_revenue', 0):,.2f} to ₹{comparison.get('recent_revenue', 0):,.2f}.",
            "impact": "Topline shrinkage impacting overall business cash flow.",
            "recommendation": "Launch targeted promotional campaigns and review pricing strategies for top categories."
        })

    # 2. Profit Decline & Margin Compression
    if comparison.get("profit_growth", 0.0) < -10.0:
        problems.append({
            "title": "Profit Margin Compression",
            "severity": "Critical",
            "metric": f"Profit Growth: {comparison.get('profit_growth')}%",
            "evidence": f"Gross profit dropped by {abs(comparison.get('profit_growth', 0)):.1f}% over the comparable period.",
            "impact": "Erosion of operational net margins and profitability.",
            "recommendation": "Audit vendor procurement costs, negotiate bulk supplier discounts, and eliminate zero-margin discounts."
        })

    # 3. Category Underperformance
    if cat_prod.get("category_performance") and len(cat_prod["category_performance"]) > 1:
        worst_cat = cat_prod["category_performance"][-1]
        best_cat = cat_prod["category_performance"][0]
        if worst_cat.get("revenue", 0) < (best_cat.get("revenue", 0) * 0.15):
            problems.append({
                "title": f"Underperforming Category: {worst_cat.get('category') or worst_cat.get('product_category', 'Bottom Category')}",
                "severity": "Warning",
                "metric": f"Revenue Share: {worst_cat.get('revenue', 0) / (exec_metrics.get('total_revenue') or 1) * 100:.1f}%",
                "evidence": f"Category '{worst_cat.get('category') or worst_cat.get('product_category')}' generated only ₹{worst_cat.get('revenue', 0):,.2f} compared to leader ₹{best_cat.get('revenue', 0):,.2f}.",
                "impact": "Dead stock accumulation and poor retail shelf turnover.",
                "recommendation": f"Rationalize product catalog for {worst_cat.get('category') or worst_cat.get('product_category')} and bundle with high-velocity items."
            })

    # 4. Regional Imbalance
    if reg_info.get("regional_performance") and len(reg_info["regional_performance"]) > 1:
        worst_reg = reg_info["regional_performance"][-1]
        problems.append({
            "title": f"Regional Sales Laggard: {worst_reg.get('region')}",
            "severity": "Info",
            "metric": f"Regional Revenue: ₹{worst_reg.get('revenue', 0):,.2f}",
            "evidence": f"Region {worst_reg.get('region')} accounts for the lowest revenue contribution ({worst_reg.get('orders')} orders).",
            "impact": "Uneven geographic penetration.",
            "recommendation": f"Evaluate local marketing channels and distribution partnerships in {worst_reg.get('region')}."
        })

    return problems


def run_full_retail_analytics(df: pd.DataFrame, custom_mapping: dict = None) -> dict:
    """Consolidated master pipeline for retail business analysis."""
    norm_df = normalize_dataframe(df, custom_mapping=custom_mapping)
    
    exec_kpis = compute_executive_metrics(norm_df)
    comparison = compute_period_comparison(norm_df)
    cat_prod = compute_category_and_product_analytics(norm_df)
    regional = compute_regional_analytics(norm_df)
    problems = detect_business_problems(norm_df, exec_kpis, comparison, cat_prod, regional)
    
    return {
        "normalized_df": norm_df,
        "executive_kpis": exec_kpis,
        "period_comparison": comparison,
        "category_analytics": cat_prod,
        "regional_analytics": regional,
        "detected_problems": problems,
        "record_count": len(norm_df)
    }
