import streamlit as st
import sys
import os
import time
import json
import pandas as pd

# Add parent directory to path to import RetailPulse modules WITHOUT modifying them
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import existing agents directly
from agents.sql_agent import generate_sql, validate_sql
from agents.planner_agent import plan_query
from agents.insight_agent import generate_insights
from agents.forecast_agent import run_forecast
from agents.pdf_agent import generate_report
from database.db import execute_read_query, check_connection
from utils.config import settings

st.set_page_config(page_title="RetailPulse Full Evaluation", layout="wide")
st.title("🧪 Full RetailPulse Agent Evaluation")
st.caption("Dynamic, non-hardcoded evaluation running against live database and actual LLM models.")

# Load Test Cases
@st.cache_data
def load_test_cases():
    test_cases_path = os.path.join(os.path.dirname(__file__), 'test_cases.json')
    if os.path.exists(test_cases_path):
        with open(test_cases_path, 'r') as f:
            return json.load(f)
    return []

test_cases = load_test_cases()

tabs = st.tabs([
    "Overview", 
    "SQL Agent", 
    "Planner Agent", 
    "Insight Agent", 
    "Forecast (ML) Agent", 
    "PDF/Report Agent", 
    "End-to-End Latency"
])

# 1. OVERVIEW
with tabs[0]:
    st.header("Overview")
    st.write(f"**Database Connection:** {'✅ Active' if check_connection() else '❌ Failed'}")
    st.write(f"**LLM Provider:** {settings.LLM_PROVIDER.upper()} | **Model:** {settings.GEMINI_MODEL if settings.LLM_PROVIDER == 'gemini' else settings.OPENAI_MODEL}")
    st.write(f"**Total Test Cases:** {len(test_cases)}")
    st.info("Every evaluation runs dynamically in real-time. No scores or outputs are hardcoded.")
    if test_cases:
        st.dataframe(pd.DataFrame(test_cases), use_container_width=True)

# 2. SQL AGENT EVALUATION
with tabs[1]:
    st.header("SQL Agent Evaluation")
    st.write("Tests LLM text-to-SQL generation against live PostgreSQL schema.")
    if st.button("Run SQL Evaluation"):
        sql_cases = [tc for tc in test_cases if tc['category'] in ['sales', 'products', 'customers', 'inventory']]
        results = []
        progress_bar = st.progress(0)
        
        for i, tc in enumerate(sql_cases):
            start_time = time.time()
            try:
                generated_sql = generate_sql(tc['query'])
                is_valid = validate_sql(generated_sql)
                
                exec_success = False
                error_msg = ""
                row_count = 0
                if is_valid:
                    try:
                        df = execute_read_query(generated_sql)
                        exec_success = True
                        row_count = len(df)
                    except Exception as e:
                        error_msg = str(e)
                
                results.append({
                    "Query": tc["query"],
                    "Generated SQL": generated_sql,
                    "Syntax Valid": is_valid,
                    "Execution Success": exec_success,
                    "Rows Returned": row_count,
                    "Latency (s)": round(time.time() - start_time, 2),
                    "Error": error_msg
                })
            except Exception as e:
                results.append({"Query": tc["query"], "Generated SQL": "ERROR", "Syntax Valid": False, "Execution Success": False, "Rows Returned": 0, "Latency (s)": round(time.time() - start_time, 2), "Error": str(e)})
            progress_bar.progress((i + 1) / len(sql_cases))
            
        res_df = pd.DataFrame(results)
        st.dataframe(res_df, use_container_width=True)
        c1, c2, c3 = st.columns(3)
        c1.metric("Execution Success Rate", f"{(res_df['Execution Success'].sum() / len(res_df)) * 100:.1f}%")
        c2.metric("Valid Syntax Rate", f"{(res_df['Syntax Valid'].sum() / len(res_df)) * 100:.1f}%")
        c3.metric("Avg Latency", f"{res_df['Latency (s)'].mean():.2f}s")

# 3. PLANNER AGENT EVALUATION
with tabs[2]:
    st.header("Planner Agent Evaluation")
    st.write("Tests intent routing and JSON structured output generation.")
    if st.button("Run Planner Evaluation"):
        results = []
        progress_bar = st.progress(0)
        
        for i, tc in enumerate(test_cases):
            start_time = time.time()
            try:
                plan = plan_query(tc['query'])
                expected = tc.get('expected_plan', {})
                matches = all(plan.get(k) == v for k, v in expected.items())
                
                results.append({
                    "Query": tc["query"],
                    "Generated Plan": str(plan),
                    "Expected": str(expected),
                    "Matches Expected": matches,
                    "Latency (s)": round(time.time() - start_time, 2)
                })
            except Exception as e:
                results.append({"Query": tc["query"], "Generated Plan": "ERROR", "Expected": str(expected), "Matches Expected": False, "Latency (s)": round(time.time() - start_time, 2)})
            progress_bar.progress((i + 1) / len(test_cases))
            
        res_df = pd.DataFrame(results)
        st.dataframe(res_df, use_container_width=True)
        st.metric("Planner Accuracy (Exact Match)", f"{(res_df['Matches Expected'].sum() / len(res_df)) * 100:.1f}%")

# 4. INSIGHT AGENT EVALUATION
with tabs[3]:
    st.header("Insight Agent Evaluation")
    st.write("Tests the LLM's ability to analyze dataframes and output structured JSON insights.")
    if st.button("Run Insight Evaluation"):
        with st.spinner("Fetching live data and generating insights..."):
            try:
                start_time = time.time()
                # Dynamically fetch real data for evaluation
                df = execute_read_query("SELECT category_id, sum(total_amount) as revenue, sum(quantity) as units FROM sales GROUP BY category_id")
                insights = generate_insights(df, "Analyze sales performance by category.")
                
                has_summary = bool(insights.get('summary'))
                has_findings = len(insights.get('key_findings', [])) > 0
                has_recs = len(insights.get('recommendations', [])) > 0
                
                st.write("### Live Output Generated:")
                st.json(insights)
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Generated Successfully", "Yes")
                c2.metric("Contains Summary", "Yes" if has_summary else "No")
                c3.metric("Contains Recommendations", "Yes" if has_recs else "No")
                c4.metric("Latency", f"{round(time.time() - start_time, 2)}s")
            except Exception as e:
                st.error(f"Insight Evaluation Failed: {e}")

# 5. FORECAST (ML) AGENT EVALUATION
with tabs[4]:
    st.header("Forecast (ML) Agent Evaluation")
    st.write("Tests Prophet/LSTM models against real database time-series data.")
    if st.button("Run ML Forecast Evaluation"):
        with st.spinner("Training models on live data..."):
            try:
                start_time = time.time()
                # Dynamically fetch real time-series data
                df = execute_read_query("SELECT sale_date as date, sum(total_amount) as revenue FROM sales GROUP BY sale_date ORDER BY sale_date")
                df['date'] = pd.to_datetime(df['date'])
                
                result = run_forecast(df, date_col='date', value_col='revenue', periods=30)
                
                model_used = result.get('model_used', 'None')
                metrics = result.get('metrics', {})
                
                st.write(f"### ML Results (Model: {model_used})")
                if result.get('figure'):
                    st.plotly_chart(result['figure'], use_container_width=True)
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Model Selected", model_used)
                c2.metric("Actual MAE", round(metrics.get('MAE', 0), 2) if metrics else "N/A")
                c3.metric("Actual RMSE", round(metrics.get('RMSE', 0), 2) if metrics else "N/A")
                c4.metric("Latency", f"{round(time.time() - start_time, 2)}s")
            except Exception as e:
                st.error(f"Forecast Evaluation Failed: {e}")

# 6. PDF / REPORT AGENT EVALUATION
with tabs[5]:
    st.header("PDF/Report Agent Evaluation")
    st.write("Tests document generation system.")
    if st.button("Run PDF Evaluation"):
        with st.spinner("Generating test report..."):
            try:
                start_time = time.time()
                df = pd.DataFrame({"Metric": ["Revenue", "Orders"], "Value": [1000, 50]})
                pdf_path = generate_report("Evaluation Test Report", "This is a live generated evaluation report.", df, [], {})
                
                file_exists = os.path.exists(pdf_path)
                file_size = os.path.getsize(pdf_path) if file_exists else 0
                
                c1, c2, c3 = st.columns(3)
                c1.metric("File Created successfully", "Yes" if file_exists else "No")
                c2.metric("File Size (bytes)", file_size)
                c3.metric("Latency", f"{round(time.time() - start_time, 2)}s")
                
                if file_exists:
                    with open(pdf_path, "rb") as f:
                        st.download_button("Download Generated PDF", f, file_name="eval_report.pdf")
            except Exception as e:
                st.error(f"PDF Evaluation Failed: {e}")

# 7. END-TO-END LATENCY
with tabs[6]:
    st.header("End-to-End Pipeline Evaluation")
    runs = st.selectbox("Number of consecutive runs:", [1, 3, 5])
    if st.button("Run E2E Pipeline"):
        with st.spinner(f"Running full LangGraph pipeline {runs} times..."):
            from graphs.workflow import run_pipeline
            test_query = "Show total revenue by category"
            latencies = []
            
            for r in range(runs):
                start = time.time()
                try:
                    res = run_pipeline(test_query)
                    success = res.get('status') != 'error'
                except Exception as e:
                    success = False
                
                latencies.append({
                    "Run #": r + 1,
                    "Success": success,
                    "Latency (s)": round(time.time() - start, 2)
                })
            
            lat_df = pd.DataFrame(latencies)
            st.dataframe(lat_df, use_container_width=True)
            st.metric("Average E2E Latency", f"{lat_df['Latency (s)'].mean():.2f}s")
