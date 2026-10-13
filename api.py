"""RetailPulse — FastAPI REST API with upload, company DB, and preprocessing."""
import logging
import os
import tempfile
from typing import Optional
from contextlib import asynccontextmanager

import pandas as pd
from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from utils.config import settings
from database.db import check_connection, get_table_schema
from graphs.workflow import run_pipeline

logger = logging.getLogger(__name__)


# ── Request/Response Models ───────────────────────────────────────────────────

class QueryRequest(BaseModel):
    query: str
    email_to: Optional[str] = None

class QueryResponse(BaseModel):
    status: str
    query: str
    sql_query: str = ""
    row_count: int = 0
    columns: list = []
    data_preview: list = []
    chart_path: str = ""
    insights: dict = {}
    forecast: dict = {}
    pdf_path: str = ""
    email_sent: bool = False
    error: str = ""

class ReportRequest(BaseModel):
    query: str
    email_to: Optional[str] = None

class EmailRequest(BaseModel):
    to_email: str
    subject: str
    body: str
    attachment_path: Optional[str] = None

class ForecastRequest(BaseModel):
    query: str = "Forecast next month's sales"
    periods: int = 30

class HealthResponse(BaseModel):
    status: str
    database: str
    llm_provider: str
    app_name: str

class DBConnectRequest(BaseModel):
    db_type: str
    host: str = ""
    port: int = 0
    database: str = ""
    username: str = ""
    password: str = ""
    sqlite_path: str = ""

class CompanyRequest(BaseModel):
    name: str
    email: str


# ── App Setup ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(settings.REPORTS_DIR, exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    logger.info("RetailPulse API started")
    yield
    logger.info("RetailPulse API shutting down")

app = FastAPI(
    title="RetailPulse API",
    description="Agentic AI Retail Analytics Platform",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Core Endpoints ────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check system health."""
    db_ok = check_connection()
    return HealthResponse(
        status="healthy" if db_ok else "degraded",
        database="connected" if db_ok else "disconnected",
        llm_provider=settings.LLM_PROVIDER,
        app_name=settings.APP_NAME,
    )


@app.post("/query", response_model=QueryResponse)
async def process_query(request: QueryRequest):
    """Process natural language query through agentic pipeline."""
    try:
        result = run_pipeline(user_query=request.query, email_to=request.email_to or "")
        df = result.get("data")
        data_preview, row_count, columns = [], 0, []
        if isinstance(df, pd.DataFrame) and not df.empty:
            row_count = len(df)
            columns = list(df.columns)
            preview_df = df.head(50).copy()
            for col in preview_df.columns:
                if pd.api.types.is_datetime64_any_dtype(preview_df[col]):
                    preview_df[col] = preview_df[col].astype(str)
            data_preview = preview_df.to_dict(orient="records")
        return QueryResponse(
            status=result.get("status", "completed"),
            query=request.query,
            sql_query=result.get("sql_query", ""),
            row_count=row_count, columns=columns, data_preview=data_preview,
            chart_path=result.get("chart_path", ""),
            insights=result.get("insights", {}),
            forecast=_serialize_forecast(result.get("forecast_result", {})),
            pdf_path=result.get("pdf_path", ""),
            email_sent=result.get("email_sent", False),
            error=result.get("error", ""),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── File Upload ───────────────────────────────────────────────────────────────

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload and parse a data file (CSV, Excel, PDF, DOCX, JSON)."""
    try:
        from utils.file_parser import parse_file
        from agents.preprocessing_agent import clean_data, get_data_summary

        contents = await file.read()
        df = parse_file(file_bytes=contents, filename=file.filename)
        cleaned_df, report = clean_data(df)
        summary = get_data_summary(cleaned_df)

        return {
            "status": "success",
            "filename": file.filename,
            "original_rows": report["original_rows"],
            "cleaned_rows": report["final_rows"],
            "cleaning_report": report,
            "data_summary": summary,
            "preview": cleaned_df.head(20).to_dict(orient="records"),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Database Connection ───────────────────────────────────────────────────────

@app.post("/connect-db")
async def connect_external_db(request: DBConnectRequest):
    """Test connection to an external company database."""
    try:
        from database.company_db import CompanyDatabase
        db = CompanyDatabase(
            db_type=request.db_type, host=request.host, port=request.port,
            database=request.database, username=request.username,
            password=request.password, sqlite_path=request.sqlite_path,
        )
        success, message = db.test_connection()
        tables = db.get_tables() if success else []
        return {"status": "connected" if success else "failed", "message": message, "tables": tables}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Reports & Email ───────────────────────────────────────────────────────────

@app.post("/report")
async def generate_report_endpoint(request: ReportRequest):
    """Generate PDF report."""
    try:
        result = run_pipeline(user_query=request.query, email_to=request.email_to or "")
        pdf_path = result.get("pdf_path", "")
        if pdf_path and os.path.exists(pdf_path):
            return {"status": "success", "pdf_path": pdf_path}
        return {"status": "error", "message": "Report generation failed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/email")
async def send_email_endpoint(request: EmailRequest):
    """Send email with optional attachment."""
    from agents.email_agent import send_email
    try:
        success = send_email(
            to_email=request.to_email, subject=request.subject,
            body=request.body, attachment_path=request.attachment_path,
        )
        return {"status": "sent" if success else "failed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/forecast")
async def forecast_endpoint(request: ForecastRequest):
    """Run sales forecasting."""
    try:
        result = run_pipeline(user_query=request.query)
        return {"status": "success", "forecast": _serialize_forecast(result.get("forecast_result", {}))}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/schema")
async def get_schema():
    """Get database schema."""
    try:
        return {"schema": get_table_schema()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _serialize_forecast(forecast: dict) -> dict:
    if not forecast:
        return {}
    result = {}
    for k, v in forecast.items():
        if isinstance(v, pd.DataFrame):
            result[k] = v.to_dict(orient="records")
        elif hasattr(v, "to_json"):
            result[k] = str(v)
        else:
            result[k] = v
    return result
