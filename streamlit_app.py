"""RetailPulse — AI-Powered Multi-Database Retail Analytics Platform.

Supports:
- Data Sources: CSV, Excel (XLSX), JSON, TSV, Google Sheets, PostgreSQL, MySQL, SQLite, Snowflake
- Modes: Demo Mode (Instant, zero-config) & Company Mode (Upload file / Connect DB)
- Analytics: Normalized analytical model, sales/profit/customer/regional KPIs, period-over-period comparison
- AI: Google Gemini + Resilient Deterministic Fallback, Q&A Assistant, Business Problem Detection
- Reports: Professional PDF Generation, SMTP Email Delivery, Automated Scheduling, Anomaly Alerts
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import time
import io
import os
import traceback
import json
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Config & Setup
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="RetailPulse — Retail Intelligence",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------------------------------------------------------------------
# Styling (Dark Theme & Glassmorphism)
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    /* Gradient Text */
    .gradient-text {
        background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #a855f7 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
        font-size: 2.3rem;
        margin-bottom: 0.8rem;
    }
    
    /* Glass Cards */
    .glass-card {
        background: rgba(30, 41, 59, 0.6);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 1.25rem;
        margin-bottom: 1rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    .glass-card:hover {
        border-color: rgba(168, 85, 247, 0.3);
    }
    
    /* Metric Cards */
    .metric-title {
        color: #94a3b8;
        font-size: 0.8rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.3rem;
    }
    .metric-value {
        color: #f8fafc;
        font-size: 1.6rem;
        font-weight: 700;
    }
    
    /* Badges */
    .badge {
        padding: 0.25rem 0.6rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
        display: inline-block;
    }
    .badge-green { background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); }
    .badge-red { background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); }
    .badge-yellow { background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); }
    .badge-purple { background: rgba(139, 92, 246, 0.2); color: #a78bfa; border: 1px solid rgba(139, 92, 246, 0.3); }
    .badge-blue { background: rgba(59, 130, 246, 0.2); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.3); }
    /* Equal-height KPI columns */
    [data-testid="column"] {
        display: flex;
        flex-direction: column;
    }
    [data-testid="column"] > div:first-child {
        flex: 1;
        display: flex;
        flex-direction: column;
    }
    [data-testid="column"] .glass-card {
        flex: 1;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Lazy Imports & Backend Services
# ---------------------------------------------------------------------------
from utils.config import settings
from utils.logger import get_logger
from utils.file_parser import parse_file, parse_google_sheet, get_supported_formats
from agents.preprocessing_agent import clean_data, engineer_features, get_data_summary
from database.connection_manager import DatabaseConnectionManager, BaseDatabaseAdapter
from database.db import execute_read_query, check_connection, get_all_tables, get_table_columns, get_tables_with_metadata
from database.relational_importer import import_dataset_to_relational_db, auto_detect_mapping
from analytics.engine import run_full_retail_analytics, normalize_dataframe
from agents.ai_service import get_ai_service
from agents.pdf_agent import generate_retail_pdf_report, generate_report
from agents.email_agent import send_email, send_email_with_config, test_smtp_connection
from agents.forecast_agent import run_forecast
from automation.scheduler import list_schedules, create_schedule, delete_schedule, toggle_schedule
from automation.alerts import get_alert_rules, get_alerts_history, evaluate_and_record_alerts

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Session State Initialization
# ---------------------------------------------------------------------------
def init_session_state():
    defaults = {
        'page': '🏠 Executive Dashboard',
        'mode': None,  # 'demo' or 'company'
        'active_company_id': None,
        'active_company_name': 'RetailPulse Enterprise',
        'chat_history': [],
        'db_connected': False,
        'active_adapter': None,
        'active_df': None,
        'active_analytics': None,
        'uploaded_data': None,
        'uploaded_filename': '',
        'cleaned_data': None,
        'cleaning_report': None,
        'company_name': 'RetailPulse Enterprise',
        'company_email': '',
        'custom_column_mapping': {}
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

init_session_state()

# ---------------------------------------------------------------------------
# UI Helpers
# ---------------------------------------------------------------------------
def render_metric_card(title, value, suffix="", delta=None):
    # Build delta row
    if delta is not None:
        color = "#10b981" if delta >= 0 else "#ef4444"
        arrow = "&#9650;" if delta >= 0 else "&#9660;"
        delta_row = "<div style='margin-top:0.4rem;'><span style='color:" + color + "; font-size:0.8rem; font-weight:700;'>" + arrow + " " + f"{abs(delta):.1f}" + "%</span> <span style='color:#64748b; font-size:0.7rem;'>vs prev</span></div>"
    else:
        delta_row = "<div style='margin-top:0.4rem; height:1.1rem;'>&nbsp;</div>"
    # Build suffix row
    suffix_row = ""
    if suffix:
        suffix_row = "<div style='color:#94a3b8; font-size:0.82rem; margin-top:0.1rem;'>" + str(suffix) + "</div>"
    # Build full card HTML as single string
    card = (
        "<div class='glass-card' style='min-height:130px; display:flex; flex-direction:column;"
        " justify-content:space-between; padding:1rem 1.2rem 0.8rem 1.2rem;'>"
        "<div class='metric-title'>" + str(title) + "</div>"
        "<div>"
        "<div class='metric-value' style='font-size:1.55rem; line-height:1.2; margin-top:0.3rem;'>" + str(value) + "</div>"
        + suffix_row +
        "</div>"
        + delta_row +
        "</div>"
    )
    st.markdown(card, unsafe_allow_html=True)


def render_plotly_dark(fig):
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font_color='#94a3b8',
        margin=dict(l=20, r=20, t=35, b=20),
        xaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', zeroline=False),
        yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', zeroline=False)
    )
    st.plotly_chart(fig, use_container_width=True)

def ensure_active_data():
    """Ensure active analytics and dataset exist, loading demo/sample if needed."""
    if st.session_state.active_analytics is not None:
        return st.session_state.active_analytics

    # Try loading from sample data
    sample_path = os.path.join(os.getcwd(), "sample_data", "sample_retail_orders.csv")
    if os.path.exists(sample_path):
        df = pd.read_csv(sample_path)
    else:
        # Generate clean synthetic retail transactions
        df = pd.DataFrame({
            "Transaction ID": range(1001, 1501),
            "Date": pd.date_range(end=datetime.now(), periods=500, freq="h"),
            "Customer ID": [f"CUST-{i%100+1:03d}" for i in range(500)],
            "Product Category": np.random.choice(["Electronics", "Clothing", "Home & Kitchen", "Beauty", "Sports"], 500),
            "Product Name": np.random.choice(["Wireless Headphones", "Casual T-Shirt", "Coffee Maker", "Running Shoes", "Skincare Serum"], 500),
            "Quantity": np.random.randint(1, 5, 500),
            "Price per Unit": np.random.choice([499.0, 999.0, 2499.0, 4999.0, 899.0], 500),
            "Payment Method": np.random.choice(["Credit Card", "UPI", "Net Banking", "Cash"], 500),
            "Region": np.random.choice(["North", "South", "East", "West"], 500)
        })
        df["Total Amount"] = df["Quantity"] * df["Price per Unit"]

    st.session_state.active_df = df
    analytics = run_full_retail_analytics(df)
    st.session_state.active_analytics = analytics
    return analytics

# ---------------------------------------------------------------------------
# Mode Selection Page (Landing Gate)
# ---------------------------------------------------------------------------
def page_mode_select():
    st.markdown('<div class="gradient-text">Welcome to RetailPulse ⚡</div>', unsafe_allow_html=True)
    st.markdown("<p style='font-size: 1.15rem; color: #cbd5e1;'>AI-Powered Multi-Database Retail Analytics Platform</p>", unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        <div class="glass-card" style="padding: 1.8rem; border-top: 4px solid #a855f7;">
            <h3 style="color: #a855f7; margin-top:0;">🎓 Demo Mode</h3>
            <p style="color: #94a3b8; font-size: 0.95rem;">Instant presentation mode. Pre-loaded with retail transactions.</p>
            <ul style="color: #cbd5e1; font-size: 0.9rem; margin-bottom: 1.5rem;">
                <li>✨ Instant access — zero database credentials required</li>
                <li>📊 Pre-loaded sales, products, categories, regions</li>
                <li>💡 Real-time AI insights, forecasting & PDF reports</li>
                <li>🎯 Ideal for academic and faculty project showcase</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        if st.button("🚀 Launch Demo Mode", use_container_width=True, type="primary", key="btn_launch_demo"):
            st.session_state.mode = "demo"
            st.session_state.active_company_name = "RetailPulse Demo Store"
            ensure_active_data()
            st.session_state.page = "🏠 Executive Dashboard"
            st.rerun()

    with col2:
        st.markdown("""
        <div class="glass-card" style="padding: 1.8rem; border-top: 4px solid #3b82f6;">
            <h3 style="color: #60a5fa; margin-top:0;">🏢 Company Mode</h3>
            <p style="color: #94a3b8; font-size: 0.95rem;">Enterprise workspace for your own files and databases.</p>
            <ul style="color: #cbd5e1; font-size: 0.9rem; margin-bottom: 1.5rem;">
                <li>📁 <b>Upload Files:</b> Analyze CSV/Excel directly or import</li>
                <li>🔗 <b>Connect Databases:</b> PostgreSQL, MySQL, SQLite, Snowflake</li>
                <li>🛡️ <b>Safe Read-Only:</b> Analyze live DB without forced import</li>
                <li>📧 <b>Automation:</b> Email scheduling & anomaly alert rules</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        if st.button("🏢 Enter Company Mode", use_container_width=True, type="primary", key="btn_launch_company"):
            st.session_state.mode = "company"
            st.session_state.page = "📁 Upload Data"
            st.rerun()

# ---------------------------------------------------------------------------
# Page 1: Executive Dashboard
# ---------------------------------------------------------------------------
def page_executive_dashboard():
    st.markdown('<div class="gradient-text">🏠 Executive Overview</div>', unsafe_allow_html=True)
    
    analytics = ensure_active_data()
    exec_kpis = analytics.get("executive_kpis", {})
    comp = analytics.get("period_comparison", {})
    cat_info = analytics.get("category_analytics", {})
    reg_info = analytics.get("regional_analytics", {})
    norm_df = analytics.get("normalized_df", pd.DataFrame())

    # Top Row Metrics
    k1, k2, k3, k4 = st.columns(4)
    rev = exec_kpis.get("total_revenue", 0)
    rev_str = f"₹{rev:,.2f}" if rev < 1e6 else f"₹{rev/1e5:,.2f} Lakh"
    with k1: render_metric_card("Total Revenue", rev_str, delta=comp.get("revenue_growth") if comp.get("has_comparison") else None)
    with k2: render_metric_card("Total Orders", f"{exec_kpis.get('total_orders', 0):,}", delta=comp.get("orders_growth") if comp.get("has_comparison") else None)
    with k3: render_metric_card("Gross Profit", f"₹{exec_kpis.get('total_profit', 0):,.2f}", suffix=f" ({exec_kpis.get('gross_margin_pct', 0):.1f}%)", delta=comp.get("profit_growth") if comp.get("has_comparison") else None)
    with k4: render_metric_card("Active Customers", f"{exec_kpis.get('total_customers', 0):,}")

    # Executive AI Summary Card
    ai_service = get_ai_service()
    insights = ai_service.generate_insights(analytics)
    summary_text = insights.get("executive_summary", "Real-time AI diagnostic synthesis.")
    st.markdown(f"""
    <div class="glass-card" style="margin-bottom: 1.2rem; border-left: 4px solid #a855f7; padding: 1.2rem 1.5rem;">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <span style="font-weight: 700; color: #a855f7; font-size: 1.05rem;">🤖 Executive AI Diagnostic Summary</span>
            <span class="badge badge-purple">{comp.get('status', 'Stable')} Momentum</span>
        </div>
        <p style="margin: 0.5rem 0 0 0; color: #f1f5f9; font-size: 0.95rem; line-height: 1.5;">{summary_text}</p>
    </div>
    """, unsafe_allow_html=True)

    # Interactive Visualizations Controls
    st.markdown("### 📊 Interactive Visual Intelligence")
    col_sel1, col_sel2 = st.columns([1, 1])
    with col_sel1:
        trend_chart_type = st.selectbox("Timeline Chart Type", ["Area Chart", "Line Chart", "Bar Chart"], index=0)
    with col_sel2:
        cat_chart_type = st.selectbox("Category Breakdown Type", ["Donut / Pie Chart", "Bar Chart", "Treemap"], index=0)

    # Second Row: Trend & Category Breakdown
    c1, c2 = st.columns([2, 1])
    with c1:
        st.markdown(f"#### 📈 Revenue Over Time ({trend_chart_type})")
        if "date" in norm_df.columns and not norm_df["date"].isna().all():
            temp_df = norm_df.dropna(subset=["date"]).sort_values("date")
            temp_df["period"] = temp_df["date"].dt.to_period("M").astype(str)
            monthly = temp_df.groupby("period")["revenue"].sum().reset_index()
            
            if trend_chart_type == "Area Chart":
                fig = px.area(monthly, x="period", y="revenue", color_discrete_sequence=['#8b5cf6'], labels={"period": "Period", "revenue": "Revenue (₹)"})
                fig.update_traces(fillcolor='rgba(139, 92, 246, 0.25)', line=dict(color='#8b5cf6', width=3))
            elif trend_chart_type == "Line Chart":
                fig = px.line(monthly, x="period", y="revenue", markers=True, color_discrete_sequence=['#38bdf8'], labels={"period": "Period", "revenue": "Revenue (₹)"})
                fig.update_traces(line=dict(color='#38bdf8', width=3))
            else: # Bar Chart
                fig = px.bar(monthly, x="period", y="revenue", color_discrete_sequence=['#a855f7'], labels={"period": "Period", "revenue": "Revenue (₹)"})
            render_plotly_dark(fig)
        else:
            st.info("No time series data available for trend chart.")

    with c2:
        st.markdown(f"#### 🏷️ Category Revenue ({cat_chart_type})")
        cat_list = cat_info.get("category_performance", [])
        if cat_list:
            cat_df = pd.DataFrame(cat_list)
            cat_col_name = "category" if "category" in cat_df.columns else "product_category"
            
            if "Donut" in cat_chart_type:
                fig_cat = px.pie(cat_df, names=cat_col_name, values="revenue", hole=0.45, color_discrete_sequence=px.colors.qualitative.Bold)
            elif cat_chart_type == "Treemap":
                fig_cat = px.treemap(cat_df, path=[cat_col_name], values="revenue", color="revenue", color_continuous_scale="Purples")
            else: # Bar Chart
                fig_cat = px.bar(cat_df, x=cat_col_name, y="revenue", color=cat_col_name, color_discrete_sequence=px.colors.qualitative.Bold)
            render_plotly_dark(fig_cat)
        else:
            st.info("Category breakdown not available.")

    # Third Row: Geography & Top Products
    r1, r2 = st.columns(2)
    with r1:
        st.markdown("#### 🗺️ Regional Revenue Contribution")
        reg_list = reg_info.get("regional_performance", [])
        if reg_list:
            reg_df = pd.DataFrame(reg_list)
            reg_view = st.radio("Region Visual Format", ["Bar Graph", "Horizontal Bar", "Pie Slice"], horizontal=True, label_visibility="collapsed")
            if reg_view == "Bar Graph":
                fig_reg = px.bar(reg_df, x="region", y="revenue", color="region", color_discrete_sequence=px.colors.qualitative.Pastel, labels={"region": "Region", "revenue": "Revenue (₹)"})
            elif reg_view == "Horizontal Bar":
                fig_reg = px.bar(reg_df, y="region", x="revenue", orientation="h", color="region", color_discrete_sequence=px.colors.qualitative.Pastel, labels={"region": "Region", "revenue": "Revenue (₹)"})
            else:
                fig_reg = px.pie(reg_df, names="region", values="revenue", color_discrete_sequence=px.colors.qualitative.Pastel)
            render_plotly_dark(fig_reg)
        else:
            st.info("Regional breakdown not available.")

    with r2:
        st.markdown("#### 🏆 Top 5 Performing Products & Profit Matrix")
        top_prods = cat_info.get("top_products", [])
        if top_prods:
            p_df = pd.DataFrame(top_prods)
            # Display interactive scatter / bubble chart or dataframe
            show_scatter = st.toggle("Show Revenue vs Units Matrix", value=False)
            if show_scatter and "units" in p_df.columns and "revenue" in p_df.columns:
                p_name_col = "product_name" if "product_name" in p_df.columns else "product"
                fig_p = px.scatter(p_df, x="units", y="revenue", size="revenue", hover_name=p_name_col, color=p_name_col, color_discrete_sequence=px.colors.qualitative.Set2)
                render_plotly_dark(fig_p)
            else:
                st.dataframe(p_df, use_container_width=True)
        else:
            st.info("Product breakdown not available.")

# ---------------------------------------------------------------------------
# Page 2: Upload Data (Direct Analysis or Database Import)
# ---------------------------------------------------------------------------
def page_upload_data():
    st.markdown('<div class="gradient-text">📁 Upload Data</div>', unsafe_allow_html=True)
    st.caption("Upload retail data (CSV, XLSX, JSON, TSV, Google Sheets) to clean, analyze directly, or import into a selected database.")

    t1, t2 = st.tabs(["📄 File Upload", "🌐 Google Sheets URL"])
    with t1:
        uploaded_file = st.file_uploader("Upload your data file", type=['csv', 'xlsx', 'json', 'tsv'], key="file_upload_input")
        if uploaded_file is not None:
            try:
                file_bytes = uploaded_file.read()
                df = parse_file(file_bytes=file_bytes, filename=uploaded_file.name)
                if not df.empty:
                    st.session_state.uploaded_data = df
                    st.session_state.uploaded_filename = uploaded_file.name
                    st.success(f"✅ Loaded '{uploaded_file.name}' ({len(df):,} rows, {len(df.columns)} columns)!")
            except Exception as e:
                st.error(f"Error parsing file: {e}")

    with t2:
        gs_url = st.text_input("Google Sheets Public URL", placeholder="https://docs.google.com/spreadsheets/d/...")
        if st.button("Load Google Sheet") and gs_url:
            try:
                df = parse_google_sheet(gs_url)
                if not df.empty:
                    st.session_state.uploaded_data = df
                    st.session_state.uploaded_filename = "Google_Sheet_Data"
                    st.success(f"✅ Loaded Google Sheet ({len(df):,} rows)!")
            except Exception as e:
                st.error(f"Error loading sheet: {e}")

    if st.session_state.uploaded_data is not None:
        df = st.session_state.uploaded_data
        st.markdown("### 1. 🔍 Raw Data Preview")
        st.dataframe(df.head(10), use_container_width=True)

        st.markdown("---")
        st.markdown("### 2. 🧹 Data Cleaning & Quality Analysis")
        c1, c2 = st.columns([1, 2])
        with c1:
            if st.button("Clean & Standardize Data", use_container_width=True, type="primary"):
                with st.spinner("Cleaning dataset..."):
                    c_df, report = clean_data(df)
                    st.session_state.cleaned_data = c_df
                    st.session_state.cleaning_report = report
                    st.success("✅ Dataset cleaned & validated!")

        target_df = st.session_state.cleaned_data if st.session_state.cleaned_data is not None else df
        if st.session_state.cleaning_report:
            rep = st.session_state.cleaning_report
            rc1, rc2, rc3 = st.columns(3)
            rc1.metric("Validated Rows", f"{len(target_df):,}")
            rc2.metric("Missing Fixed", rep.get("issues_fixed", 0))
            rc3.metric("Quality Score", f"{rep.get('quality_score', rep.get('data_quality_score', 95))}%")

        st.markdown("---")
        st.markdown("### 3. 📋 Retail Column Mapping")
        detected_mapping = auto_detect_mapping(list(target_df.columns))
        col_options = ["-- Not Mapped --"] + list(target_df.columns)
        confirmed_mapping = {}

        field_labels = [
            ("transaction_id", "Transaction / Order ID"),
            ("sale_date", "Date / Timestamp"),
            ("customer_id", "Customer ID / Code"),
            ("category_name", "Product Category"),
            ("product_name", "Product Name"),
            ("quantity", "Quantity Sold"),
            ("unit_price", "Price per Unit"),
            ("total_amount", "Total Revenue / Amount"),
            ("payment_method", "Payment Method"),
            ("region", "Region / Territory")
        ]

        m_cols = st.columns(2)
        for idx, (f_key, f_title) in enumerate(field_labels):
            grid = m_cols[idx % 2]
            with grid:
                def_col = detected_mapping.get(f_key)
                def_idx = list(target_df.columns).index(def_col) + 1 if def_col and def_col in target_df.columns else 0
                sel = st.selectbox(f_title, col_options, index=def_idx, key=f"up_map_{f_key}")
                if sel != "-- Not Mapped --":
                    confirmed_mapping[f_key] = sel

        st.markdown("---")
        st.markdown("### 4. ⚡ Choose Analysis or Database Import")

        ch1, ch2 = st.columns(2)
        with ch1:
            st.markdown("""
            <div class="glass-card" style="padding: 1rem; border-left: 4px solid #10b981;">
                <h4 style="margin:0 0 0.5rem 0; color: #34d399;">Option A: Analyze File Directly</h4>
                <p style="font-size: 0.85rem; color: #94a3b8; margin:0;">Immediate analysis without setting up or modifying any database.</p>
            </div>
            """, unsafe_allow_html=True)
            if st.button("📊 Analyze File Directly", use_container_width=True, type="primary", key="btn_direct_analysis"):
                with st.spinner("Computing normalized analytics..."):
                    analytics = run_full_retail_analytics(target_df, custom_mapping=confirmed_mapping)
                    st.session_state.active_df = target_df
                    st.session_state.active_analytics = analytics
                    st.session_state.page = "🏠 Executive Dashboard"
                    st.success("✅ Analytics ready!")
                    st.rerun()

        with ch2:
            st.markdown("""
            <div class="glass-card" style="padding: 1rem; border-left: 4px solid #8b5cf6;">
                <h4 style="margin:0 0 0.5rem 0; color: #a78bfa;">Option B: Import to Database</h4>
                <p style="font-size: 0.85rem; color: #94a3b8; margin:0;">Save records into your connected database with transaction rollback.</p>
            </div>
            """, unsafe_allow_html=True)
            import_mode_sel = st.selectbox("Import Mode", ["Add New Records", "Replace Dataset", "Upsert Records"], key="sel_import_mode")
            mode_key = "add" if "Add" in import_mode_sel else ("replace" if "Replace" in import_mode_sel else "upsert")
            
            if st.button("💾 Save & Import to Database", use_container_width=True, key="btn_save_db"):
                with st.spinner("Executing relational database transaction..."):
                    res = import_dataset_to_relational_db(target_df, confirmed_mapping, import_mode=mode_key)
                    if res["success"]:
                        st.success(f"✅ {res['message']}")
                        st.session_state.db_connected = True
                        analytics = run_full_retail_analytics(target_df, custom_mapping=confirmed_mapping)
                        st.session_state.active_df = target_df
                        st.session_state.active_analytics = analytics
                    else:
                        st.error(f"❌ {res['message']}")

# ---------------------------------------------------------------------------
# Page 3: Connect Database (Universal Multi-Database Adapter)
# ---------------------------------------------------------------------------
def page_connect_database():
    st.markdown('<div class="gradient-text">🔗 Connect Database</div>', unsafe_allow_html=True)
    st.caption("Universal multi-database connector supporting PostgreSQL, MySQL, SQLite, and Snowflake in safe Read-Only mode.")

    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    db_type = st.selectbox("Database Provider", ["PostgreSQL", "MySQL", "SQLite", "Snowflake"], index=0, key="sel_db_provider")

    config = {}
    if db_type == "SQLite":
        config["sqlite_path"] = st.text_input("Database File Path", value="data/retail.db", help="Path to your .db or .sqlite file")
    elif db_type == "Snowflake":
        sc1, sc2 = st.columns(2)
        with sc1:
            config["account"] = st.text_input("Account Identifier", placeholder="xy12345.us-east-1")
            config["username"] = st.text_input("Username")
            config["password"] = st.text_input("Password", type="password")
        with sc2:
            config["warehouse"] = st.text_input("Warehouse", placeholder="COMPUTE_WH")
            config["database"] = st.text_input("Database Name")
            config["schema"] = st.text_input("Schema", value="PUBLIC")
            config["role"] = st.text_input("Role (Optional)", placeholder="ACCOUNTADMIN")
    else:  # PostgreSQL / MySQL
        default_host = DatabaseConnectionManager.resolve_default_host()
        default_port = "5432" if db_type == "PostgreSQL" else "3306"
        default_db = "retailpulse_db" if db_type == "PostgreSQL" else "retail_db"
        default_user = "retailpulse" if db_type == "PostgreSQL" else "root"
        default_pass = "retailpulse123" if db_type == "PostgreSQL" else ""

        c1, c2 = st.columns(2)
        with c1:
            config["host"] = st.text_input("Host", value=default_host)
            config["port"] = st.text_input("Port", value=default_port)
            config["database"] = st.text_input("Database Name", value=default_db)
        with c2:
            config["username"] = st.text_input("Username", value=default_user)
            config["password"] = st.text_input("Password", value=default_pass, type="password")
            config["ssl"] = st.checkbox("Require SSL", value=False)

    st.caption("🛡️ *External databases are accessed in strictly safe Read-Only mode.*")

    if st.button("🔌 Test & Connect Database", use_container_width=True, type="primary", key="btn_test_connect"):
        with st.spinner(f"Connecting to {db_type}..."):
            try:
                adapter = DatabaseConnectionManager.get_adapter(db_type, config)
                ok, msg, info = adapter.test_connection()
                if ok:
                    st.session_state.active_adapter = adapter
                    st.session_state.db_connected = True
                    st.success(msg)
                else:
                    st.error(msg)
            except Exception as e:
                st.error(f"❌ Connection error: {str(e)}")

    st.markdown('</div>', unsafe_allow_html=True)

    # Discovered Schema Section
    if st.session_state.db_connected and st.session_state.active_adapter:
        adapter = st.session_state.active_adapter
        st.markdown("### 🗄️ Database Schema & Table Discovery")
        
        tables_meta = adapter.get_tables_metadata()
        if tables_meta:
            st.markdown(f"#### **Found {len(tables_meta)} Tables in `{adapter.config.get('database', 'database')}`**")
            g_cols = st.columns(min(len(tables_meta), 3))
            for idx, meta in enumerate(tables_meta):
                with g_cols[idx % 3]:
                    st.markdown(f"""
                    <div class="glass-card" style="padding: 0.8rem; margin-bottom: 0.5rem;">
                        <h4 style="margin:0; color: #a855f7;">📋 <code>{meta['table_name']}</code></h4>
                        <p style="margin: 0.2rem 0 0 0; color: #94a3b8; font-size: 0.85rem;">
                            <b>{meta['row_count']:,}</b> rows | <b>{meta['column_count']}</b> columns
                        </p>
                    </div>
                    """, unsafe_allow_html=True)

            # Analyze live database button
            st.markdown("---")
            if st.button("📊 Analyze Connected Database Directly (Read-Only)", use_container_width=True, type="primary", key="btn_analyze_db"):
                with st.spinner("Extracting and normalizing retail records..."):
                    # Find sales or largest table
                    t_names = [m["table_name"] for m in tables_meta]
                    target_table = "sales" if "sales" in t_names else t_names[0]
                    df = adapter.preview_table(target_table, limit=5000)
                    if not df.empty:
                        analytics = run_full_retail_analytics(df)
                        st.session_state.active_df = df
                        st.session_state.active_analytics = analytics
                        st.session_state.page = "🏠 Executive Dashboard"
                        st.success(f"✅ Loaded and analyzed table '{target_table}'!")
                        st.rerun()

# ---------------------------------------------------------------------------
# Page 4: AI Business Insights Studio & Q&A
# ---------------------------------------------------------------------------
def page_ai_insights():
    st.markdown('<div class="gradient-text">💡 AI Business Insights</div>', unsafe_allow_html=True)
    st.caption("AI-powered diagnostic executive synthesis, problem detection, and natural language decision assistant.")

    analytics = ensure_active_data()
    ai_service = get_ai_service()

    with st.spinner("Synthesizing retail intelligence..."):
        insights = ai_service.generate_insights(analytics)

    # Status Banner
    risk = insights.get("risk_level", "Low")
    risk_color = "badge-green" if risk == "Low" else ("badge-yellow" if risk == "Moderate" else "badge-red")
    
    st.markdown(f"""
    <div class="glass-card" style="border-left: 4px solid #a855f7;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <h3 style="margin: 0; color: #f8fafc;">Executive Synthesis</h3>
            <span class="badge {risk_color}">Risk Level: {risk}</span>
        </div>
        <p style="margin: 0.8rem 0 0 0; color: #cbd5e1; font-size: 1rem; line-height: 1.6;">
            {insights.get('executive_summary', 'No summary available.')}
        </p>
        <p style="margin: 0.5rem 0 0 0; font-size: 0.75rem; color: #94a3b8;">
            Engine: <i>{insights.get('provider_used', 'AI Intelligence')}</i>
        </p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 🟢 What Went Well")
        for item in insights.get("positive_insights", []):
            st.markdown(f"- <span style='color: #34d399;'>✓</span> {item}", unsafe_allow_html=True)

    with col2:
        st.markdown("### 🔴 What Needs Attention")
        for item in insights.get("negative_insights", []):
            st.markdown(f"- <span style='color: #f87171;'>!</span> {item}", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 🎯 Strategic Recommendations & Priority Actions")
    r1, r2 = st.columns(2)
    with r1:
        st.markdown("#### Strategic Directions")
        for rec in insights.get("recommendations", []):
            st.markdown(f"1. **{rec}**")
    with r2:
        st.markdown("#### Priority Action Items")
        for act in insights.get("priority_actions", []):
            st.markdown(f"- `{act}`")

    # Interactive Natural Language Assistant
    st.markdown("---")
    st.markdown("### 💬 Ask RetailPulse Assistant")

    # Suggested question chips
    st.caption("💡 Try one of these questions or type your own:")
    suggested = [
        "What should I do next month to increase profit?",
        "Which category performs best and why?",
        "Show top 10 products by revenue",
        "Previous month sales breakdown",
        "Which region is underperforming and how to fix it?",
        "How can I reduce slow-moving inventory?"
    ]
    chip_cols = st.columns(3)
    for i, suggestion in enumerate(suggested):
        if chip_cols[i % 3].button(f"💬 {suggestion}", key=f"chip_{i}", use_container_width=True):
            st.session_state["ai_prefill_q"] = suggestion

    # Chat history
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # Pre-fill question from chip click
    prefill = st.session_state.pop("ai_prefill_q", "")
    user_q = st.text_input("Your business question:", value=prefill, key="ai_q_input", placeholder="e.g. What should I do next month to increase profit?")

    if st.button("🔍 Analyze", use_container_width=True, type="primary") and user_q:
        with st.spinner("Analyzing your data and generating strategic recommendations..."):
            df = st.session_state.get('active_df')
            data_context = dict(analytics)

            if df is not None and not df.empty:
                data_summary = f"Dataset: {len(df)} rows × {len(df.columns)} columns: {', '.join(df.columns.tolist())}.\n"

                # Date range info
                for col in df.columns:
                    try:
                        dt_col = pd.to_datetime(df[col], errors='coerce')
                        if dt_col.notna().sum() > len(df) * 0.5:
                            data_summary += f"Date range ({col}): {dt_col.min().strftime('%Y-%m-%d')} to {dt_col.max().strftime('%Y-%m-%d')}.\n"
                    except Exception:
                        pass

                num_cols = df.select_dtypes(include='number').columns.tolist()
                if num_cols:
                    stats = df[num_cols].describe().round(2).to_string()
                    data_summary += f"\nNumeric Stats:\n{stats}\n"

                q_lower = user_q.lower()

                # Monthly breakdown
                if any(kw in q_lower for kw in ['previous month', 'last month', 'this month', 'monthly', 'month wise', 'month']):
                    for col in df.columns:
                        try:
                            dt_col = pd.to_datetime(df[col], errors='coerce')
                            if dt_col.notna().sum() > len(df) * 0.5:
                                df_copy = df.copy()
                                df_copy['_month'] = dt_col.dt.to_period('M')
                                monthly = df_copy.groupby('_month').agg({c: 'sum' for c in num_cols}).tail(6)
                                data_summary += f"\nMonthly Breakdown (last 6 months):\n{monthly.to_string()}\n"
                                break
                        except Exception:
                            pass

                # Top products
                if any(kw in q_lower for kw in ['top product', 'best product', 'top 10', 'top selling', 'product']):
                    prod_cols = [c for c in df.columns if any(k in c.lower() for k in ['product', 'item', 'name'])]
                    rev_cols = [c for c in df.columns if any(k in c.lower() for k in ['revenue', 'amount', 'total', 'sales', 'price'])]
                    if prod_cols and rev_cols:
                        top_p = df.groupby(prod_cols[0])[rev_cols[0]].sum().nlargest(10)
                        data_summary += f"\nTop 10 Products by {rev_cols[0]}:\n{top_p.to_string()}\n"
                        # Also bottom products for bundling strategy
                        bottom_p = df.groupby(prod_cols[0])[rev_cols[0]].sum().nsmallest(5)
                        data_summary += f"\nBottom 5 Products (slow-moving):\n{bottom_p.to_string()}\n"

                # Category analysis
                if any(kw in q_lower for kw in ['category', 'categories', 'profit', 'next month', 'increase', 'improve', 'strategy', 'discount']):
                    cat_cols = [c for c in df.columns if any(k in c.lower() for k in ['category', 'cat', 'type', 'group'])]
                    rev_cols = [c for c in df.columns if any(k in c.lower() for k in ['revenue', 'amount', 'total', 'sales', 'price'])]
                    profit_cols = [c for c in df.columns if any(k in c.lower() for k in ['profit', 'margin', 'cost'])]
                    if cat_cols and rev_cols:
                        agg_dict = {rev_cols[0]: 'sum'}
                        if profit_cols:
                            agg_dict[profit_cols[0]] = 'sum'
                        cat_perf = df.groupby(cat_cols[0]).agg(agg_dict).sort_values(rev_cols[0], ascending=False)
                        data_summary += f"\nCategory Performance (sorted by revenue):\n{cat_perf.to_string()}\n"

                # Region analysis
                if any(kw in q_lower for kw in ['region', 'geography', 'where', 'location', 'area', 'territory']):
                    reg_cols = [c for c in df.columns if any(k in c.lower() for k in ['region', 'area', 'city', 'state', 'location', 'territory'])]
                    rev_cols = [c for c in df.columns if any(k in c.lower() for k in ['revenue', 'amount', 'total', 'sales'])]
                    if reg_cols and rev_cols:
                        reg_perf = df.groupby(reg_cols[0])[rev_cols[0]].sum().sort_values(ascending=False)
                        data_summary += f"\nRegional Performance:\n{reg_perf.to_string()}\n"

                data_context["data_summary"] = data_summary

            ans = ai_service.answer_question(user_q, data_context)
            st.session_state.chat_history.append({"q": user_q, "a": ans})
            st.rerun()

    # Display chat history (most recent first) — rendered as proper markdown
    for chat in reversed(st.session_state.chat_history):
        st.markdown(f"<div class='glass-card' style='margin-bottom:0.8rem; border-left: 3px solid #a855f7;'>"
                    f"<p style='color:#94a3b8; font-size:0.85rem; margin:0 0 0.5rem 0;'>🧑 <b>You asked:</b> {chat['q']}</p>"
                    f"</div>", unsafe_allow_html=True)
        # Render AI answer as proper markdown (not inside raw HTML)
        with st.container():
            st.markdown(f"🤖 **RetailPulse AI:**")
            st.markdown(chat['a'])
            st.markdown("---")

# ---------------------------------------------------------------------------
# Page 5: Forecast Studio
# ---------------------------------------------------------------------------
def page_forecast_studio():
    st.markdown('<div class="gradient-text">🔮 Forecast Studio</div>', unsafe_allow_html=True)
    st.caption("Machine learning sales and demand forecasting with confidence interval bounds.")

    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    df = st.session_state.get('active_df')
    if df is None or df.empty:
        st.warning("Please upload data or connect a database first.")
        return
        
    date_cols = [c for c in df.columns if pd.api.types.is_datetime64_any_dtype(df[c]) or df[c].dtype == 'object']
    num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    
    if not date_cols or not num_cols:
        st.error("Data must contain at least one date column and one numeric column.")
        return
        
    c1, c2 = st.columns(2)
    with c1:
        date_col = st.selectbox("Date Column", date_cols)
    with c2:
        value_col = st.selectbox("Metric Column (to forecast)", num_cols)

    days = st.slider("Forecast Horizon (Days)", min_value=7, max_value=90, value=30)
    
    if st.button("Generate ML Forecast", use_container_width=True, type="primary"):
        with st.spinner("Fitting time-series forecasting model..."):
            try:
                # Attempt to convert date column to datetime if not already
                df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
                df_clean = df.dropna(subset=[date_col, value_col]).sort_values(date_col)
                
                # run_forecast expects (df, date_col, value_col, periods) and returns a dict
                result = run_forecast(df_clean, date_col, value_col, days)
                if 'error' in result:
                    st.error(result['error'])
                else:
                    forecast_df = result['forecast_df']
                    metrics = result['metrics']
                    model_used = result['model_used']
                    
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Selected Algorithm", model_used)
                    m2.metric("Mean Absolute Error (MAE)", f"{metrics.get('MAE', 0):.2f}")
                    m3.metric("Root Mean Squared Error (RMSE)", f"{metrics.get('RMSE', 0):.2f}")
    
                    fig = result['figure']
                    render_plotly_dark(fig)
    
                    st.markdown("### 📋 Forecast Data Table")
                    st.dataframe(forecast_df[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].head(15), use_container_width=True)
            except Exception as e:
                st.error(f"Forecasting error: {e}")
    st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Page 6: Table Explorer
# ---------------------------------------------------------------------------
def page_table_explorer():
    st.markdown('<div class="gradient-text">📦 Table Explorer</div>', unsafe_allow_html=True)
    st.caption("Inspect schemas, data types, statistical distributions, and record previews.")

    try:
        adapter = st.session_state.get('active_adapter')
        if adapter:
            tables_meta = adapter.get_tables_metadata()
        else:
            tables_meta = get_tables_with_metadata()
            
        if not tables_meta:
            st.warning("No database tables found. Upload a file or connect to a Database.")
            return

        t_names = [m["table_name"] for m in tables_meta]
        sel_table = st.selectbox("Select Table to Explore", t_names, key="tbl_exp_sel")

        if adapter:
            df = adapter.preview_table(sel_table, limit=5000)
        else:
            df = execute_read_query(f'SELECT * FROM "{sel_table}" LIMIT 5000')
        if df.empty:
            st.info(f"Table '{sel_table}' is empty.")
            return

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Rows", f"{len(df):,}")
        c2.metric("Total Columns", str(len(df.columns)))
        c3.metric("Numeric Fields", str(len([c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])])))
        c4.metric("Text Fields", str(len([c for c in df.columns if df[c].dtype == 'object'])))

        st.markdown("### 📊 Statistical Summary")
        st.dataframe(df.describe(include="all").fillna("").T, use_container_width=True)

        st.markdown("### 📋 Record Preview (First 100 Rows)")
        st.dataframe(df.head(100), use_container_width=True)
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(f"📥 Download {sel_table}.csv", csv, f"{sel_table}.csv", "text/csv")
    except Exception as e:
        st.error(f"Error loading table explorer: {e}")

# ---------------------------------------------------------------------------
# Page 7: PDF Reports Studio
# ---------------------------------------------------------------------------
def page_reports_studio():
    st.markdown('<div class="gradient-text">📄 Executive PDF Reports</div>', unsafe_allow_html=True)
    st.caption("Generate professional board-ready PDF retail performance reports.")

    analytics = ensure_active_data()
    ai_service = get_ai_service()

    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    company_title = st.text_input("Enterprise Name", value=st.session_state.active_company_name)
    
    if st.button("📄 Generate Comprehensive PDF Report", use_container_width=True, type="primary"):
        with st.spinner("Generating executive PDF document..."):
            try:
                insights = ai_service.generate_insights(analytics)
                pdf_bytes = generate_retail_pdf_report(analytics, ai_insights=insights, company_name=company_title)
                st.session_state.last_pdf = pdf_bytes
                st.success("✅ Executive PDF Report Generated Successfully!")
                
                st.download_button(
                    label="📥 Download PDF Report",
                    data=pdf_bytes,
                    file_name=f"RetailPulse_Report_{datetime.now().strftime('%Y%m%d')}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"Report generation error: {e}")
    st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Page 8: Email Reports & Schedules
# ---------------------------------------------------------------------------
def page_email_and_schedules():
    st.markdown('<div class="gradient-text">📧 Email Reports & Schedules</div>', unsafe_allow_html=True)
    st.caption("Deliver automated reports via SMTP (Gmail, Outlook, Custom) and manage APScheduler recurring jobs.")

    t1, t2 = st.tabs(["✉️ Dispatch Report Now", "⏰ Automated Report Schedules"])
    
    with t1:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        to_email = st.text_input("Recipient Email", value=st.session_state.company_email, placeholder="executive@company.com")
        subject = st.text_input("Subject Line", value="RetailPulse AI — Weekly Retail Performance Report")
        body_text = st.text_area("Message Summary", value="Attached is your automated RetailPulse AI performance report.")
        
        with st.expander("⚙️ Configure Sender Email (SMTP / Live Delivery Setup)", expanded=True):
            import dotenv
            env_path = ".env"
            current_user = dotenv.get_key(env_path, "SMTP_USER") or ""
            current_pass = dotenv.get_key(env_path, "SMTP_PASSWORD") or ""
            
            st.markdown("""
            **Enter your Gmail sender credentials below to deliver real emails to any phone or inbox:**
            1. Use your Gmail address as **Sender Email**.
            2. For **App Password**, generate a 16-letter password at: [Google App Passwords](https://myaccount.google.com/apppasswords) *(Do not use your regular password)*.
            """)
            smtp_user = st.text_input("Sender Gmail Address", value=current_user, placeholder="yourname@gmail.com")
            smtp_pass = st.text_input("Google 16-Character App Password", value=current_pass, type="password", placeholder="xxxx xxxx xxxx xxxx")
            
            c_save, c_test = st.columns(2)
            with c_save:
                if st.button("💾 Save Sender Settings", use_container_width=True):
                    dotenv.set_key(env_path, "SMTP_USER", smtp_user.strip())
                    dotenv.set_key(env_path, "SMTP_PASSWORD", smtp_pass.strip().replace(" ", ""))
                    st.success("✅ SMTP credentials saved successfully!")
            with c_test:
                if st.button("🔍 Test Live SMTP Connection", use_container_width=True):
                    if smtp_user and smtp_pass:
                        test_conf = {
                            "host": "smtp.gmail.com",
                            "port": 587,
                            "username": smtp_user.strip(),
                            "password": smtp_pass.strip().replace(" ", "")
                        }
                        ok, msg = test_smtp_connection(test_conf)
                        if ok:
                            st.success(msg)
                        else:
                            st.error(msg)
                    else:
                        st.warning("Please enter both Sender Email and App Password to test.")

        # Platform dispatch button
        if st.button("🚀 Send Email Report with PDF Attachment", use_container_width=True, type="primary"):
            if not to_email:
                st.warning("Please enter a valid recipient email.")
            else:
                with st.spinner(f"Sending real email report to {to_email}..."):
                    try:
                        analytics = ensure_active_data()
                        ai_service = get_ai_service()
                        insights = ai_service.generate_insights(analytics)
                        pdf_bytes = generate_retail_pdf_report(analytics, ai_insights=insights, company_name=st.session_state.active_company_name)
                        
                        import dotenv
                        env_path = ".env"
                        s_user = dotenv.get_key(env_path, "SMTP_USER") or ""
                        s_pass = (dotenv.get_key(env_path, "SMTP_PASSWORD") or "").replace(" ", "")
                        
                        config = {
                            "host": "smtp.gmail.com",
                            "port": 587,
                            "username": s_user,
                            "password": s_pass,
                            "sender_email": s_user or "RetailPulse AI Platform <reports@retailpulse.ai>"
                        }
                        ok, msg = send_email_with_config(config, to_email, subject, body_text, attachment=pdf_bytes)
                        if ok:
                            st.success(f"✅ Report successfully generated and dispatched for **{to_email}**!")
                            st.markdown(f"""
                            <div style="background: rgba(16, 185, 129, 0.15); border: 1px solid #10b981; border-radius: 8px; padding: 12px; margin: 10px 0;">
                                <p style="margin: 0; color: #34d399; font-weight: 600;">📄 Executive Report Ready for {to_email}</p>
                                <p style="margin: 4px 0 0 0; color: #cbd5e1; font-size: 0.9rem;">
                                    The PDF report with all analytics and AI insights has been compiled. You can download and send it directly below:
                                </p>
                            </div>
                            """, unsafe_allow_html=True)
                            st.download_button(
                                label=f"📥 Download Report for {to_email}",
                                data=pdf_bytes,
                                file_name=f"RetailPulse_Report_{to_email.split('@')[0]}_{datetime.now().strftime('%Y%m%d')}.pdf",
                                mime="application/pdf",
                                use_container_width=True
                            )
                        else:
                            st.error(msg)
                    except Exception as e:
                        st.error(f"Email delivery error: {e}")
        st.markdown('</div>', unsafe_allow_html=True)

    with t2:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown("### Add New Report Schedule")
        sc1, sc2, sc3 = st.columns(3)
        freq = sc1.selectbox("Frequency", ["Daily", "Weekly", "Monthly"])
        time_sel = sc2.text_input("Time (HH:MM)", value="09:00")
        sched_recipients = sc3.text_input("Recipients", placeholder="exec@company.com")

        if st.button("➕ Create Schedule", use_container_width=True):
            if not sched_recipients:
                st.warning("Please specify at least one recipient.")
            else:
                create_schedule(
                    company_id=st.session_state.active_company_id or "demo",
                    company_name=st.session_state.active_company_name,
                    report_title="Automated Retail Report",
                    frequency=freq,
                    time_of_day=time_sel,
                    recipients=[r.strip() for r in sched_recipients.split(",")]
                )
                st.success(f"✅ Recurring schedule created for {sched_recipients} at {time_sel}!")
                st.rerun()

        st.markdown("---")
        st.markdown("### Active Schedules")
        schedules = list_schedules()
        if schedules:
            for s in schedules:
                st.markdown(f"⏰ **{s['report_title']}** ({s['frequency'].capitalize()} at {s['time_of_day']}) — Status: `{s['status']}`")
        else:
            st.info("No active recurring schedules configured.")
        st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Page 9: Alerts Studio
# ---------------------------------------------------------------------------
def page_alerts_studio():
    st.markdown('<div class="gradient-text">🚨 Automated Anomaly Alerts</div>', unsafe_allow_html=True)
    st.caption("Active monitoring rules and audit history of detected business problems.")

    analytics = ensure_active_data()
    triggered = evaluate_and_record_alerts(analytics, company_id=st.session_state.active_company_id or "demo", company_name=st.session_state.active_company_name)

    st.markdown("### Active Monitoring Rules")
    rules = get_alert_rules()
    for r in rules:
        st.markdown(f"- 🔔 **{r['name']}** (Threshold: `{r['metric']} <= {r['threshold']}%`) — <span class='badge badge-purple'>{r['severity']}</span>", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### Recent Triggered Alerts")
    history = get_alerts_history()
    if history:
        for a in history[:10]:
            sev_class = "badge-red" if a.get("severity") == "Critical" else "badge-yellow"
            st.markdown(f"""
            <div class="glass-card" style="padding: 0.8rem; margin-bottom: 0.5rem;">
                <div style="display:flex; justify-content:space-between;">
                    <b>{a.get('title')}</b>
                    <span class="badge {sev_class}">{a.get('severity')}</span>
                </div>
                <p style="margin: 0.3rem 0 0 0; color: #cbd5e1; font-size: 0.85rem;">{a.get('message')}</p>
                <small style="color: #64748b;">Triggered at: {a.get('timestamp')}</small>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.success("✅ All systems operating within normal parameters. No active alerts.")

# ---------------------------------------------------------------------------
# Page 10: Custom SQL Studio
# ---------------------------------------------------------------------------
def page_custom_sql():
    st.markdown('<div class="gradient-text">🔍 Custom SQL Studio</div>', unsafe_allow_html=True)
    st.caption("Run safe read-only SELECT queries directly against your connected database.")

    sql = st.text_area("SQL Query (SELECT only):", value="SELECT * FROM sales LIMIT 25", height=120)
    if st.button("▶ Run Query", use_container_width=True, type="primary"):
        with st.spinner("Executing query..."):
            try:
                adapter = st.session_state.get('active_adapter')
                if adapter:
                    df = adapter.execute_query(sql)
                else:
                    df = execute_read_query(sql)
                if not df.empty:
                    st.success(f"✅ {len(df)} rows returned!")
                    st.dataframe(df, use_container_width=True)
                else:
                    st.info("Query returned 0 rows.")
            except Exception as e:
                st.error(f"SQL Execution Error: {e}")

# ---------------------------------------------------------------------------
# Page 11: Settings Page
# ---------------------------------------------------------------------------
def page_settings():
    st.markdown('<div class="gradient-text">⚙️ Settings</div>', unsafe_allow_html=True)
    
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### Environment & DB Status")
        db_stat = "Connected" if st.session_state.db_connected else "Disconnected"
        st.markdown(f"**Database Status:** <span class='badge {'badge-green' if st.session_state.db_connected else 'badge-red'}'>{db_stat}</span>", unsafe_allow_html=True)
        st.markdown(f"**Operating Mode:** `{st.session_state.mode or 'Not Selected'}`")
        st.markdown(f"**Active Workspace:** `{st.session_state.active_company_name}`")
    with c2:
        st.markdown("### Session Management")
        if st.button("Reset Application Cache & State", type="primary", use_container_width=True):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()

# ---------------------------------------------------------------------------
# Sidebar Navigation
# ---------------------------------------------------------------------------
def sidebar():
    with st.sidebar:
        st.markdown("<h2 style='text-align: center; color: #a855f7; margin-bottom:0;'>⚡ RetailPulse</h2>", unsafe_allow_html=True)
        st.caption("<div style='text-align:center; color:#94a3b8;'>Retail Intelligence Platform</div>", unsafe_allow_html=True)
        
        mode = st.session_state.mode
        if mode == 'demo':
            st.markdown("<div style='text-align:center; margin: 0.5rem 0;'><span class='badge badge-purple'>🎓 DEMO MODE</span></div>", unsafe_allow_html=True)
        elif mode == 'company':
            cname = st.session_state.active_company_name or 'Company'
            st.markdown(f"<div style='text-align:center; margin: 0.5rem 0;'><span class='badge badge-green'>🏢 {cname}</span></div>", unsafe_allow_html=True)
            
        if mode and st.button('↩ Switch Mode', use_container_width=True, key='nav_switch_mode'):
            st.session_state.mode = None
            st.session_state.page = 'mode_select'
            st.rerun()

        st.markdown("---")

        core_pages = ['🏠 Executive Dashboard', '📁 Upload Data', '🔗 Connect Database']
        pages = {
            'Core': core_pages,
            'Intelligence': ['💡 AI Business Insights', '🔮 Forecast Studio', '📦 Table Explorer', '🔍 Custom SQL Studio'],
            'Reports & Alerts': ['📄 PDF Reports', '📧 Email & Schedules', '🚨 Anomaly Alerts'],
            'System': ['⚙️ Settings']
        }

        for section, items in pages.items():
            st.markdown(f"<div style='color: #64748b; font-size: 0.75rem; font-weight: bold; margin-top: 0.8rem; margin-bottom: 0.3rem; text-transform: uppercase;'>{section}</div>", unsafe_allow_html=True)
            for item in items:
                if st.button(item, use_container_width=True, key=f"nav_{item}", type="primary" if st.session_state.page == item else "secondary"):
                    st.session_state.page = item
                    st.rerun()

# ---------------------------------------------------------------------------
# Main Router
# ---------------------------------------------------------------------------
def main():
    if st.session_state.mode is None:
        page_mode_select()
        return

    sidebar()
    page = st.session_state.page

    if page == '🏠 Executive Dashboard': page_executive_dashboard()
    elif page == '📁 Upload Data': page_upload_data()
    elif page == '🔗 Connect Database': page_connect_database()
    elif page == '💡 AI Business Insights': page_ai_insights()
    elif page == '🔮 Forecast Studio': page_forecast_studio()
    elif page == '📦 Table Explorer': page_table_explorer()
    elif page == '🔍 Custom SQL Studio': page_custom_sql()
    elif page == '📄 PDF Reports': page_reports_studio()
    elif page == '📧 Email & Schedules': page_email_and_schedules()
    elif page == '🚨 Anomaly Alerts': page_alerts_studio()
    elif page == '⚙️ Settings': page_settings()

main()
