# 🔮 RetailPulse — Agentic AI Retail Analytics Platform

An intelligent retail analytics system powered by **LangGraph Agentic AI** that converts natural language queries into actionable business insights, visualizations, forecasts, and PDF reports.

## 🏗️ Architecture

```
User Query (Natural Language)
    │
    ▼
┌─────────────────────────────────────────────────┐
│              LangGraph StateGraph                │
│                                                  │
│  🧠 Planner ─→ 🔍 Query Parser ─→ 🗄️ SQL Agent │
│       │                                │         │
│       ▼                                ▼         │
│  📊 Visualization ─→ 🔮 Forecast ─→ 💡 Insight  │
│       │                                │         │
│       ▼                                ▼         │
│  📄 PDF Report ──────────→ 📧 Email Agent        │
└─────────────────────────────────────────────────┘
    │
    ▼
Results: Data + Charts + Insights + PDF + Email
```

## 🛠️ Tech Stack

| Component | Technology |
|-----------|-----------|
| AI Orchestration | LangGraph + LangChain |
| LLM | Gemini / OpenAI / Ollama |
| Backend | FastAPI |
| Frontend | Streamlit |
| Database | PostgreSQL |
| Forecasting | Prophet + LSTM (TensorFlow) |
| Charts | Plotly + Matplotlib |
| PDF | FPDF2 |
| Containerization | Docker + Docker Compose |

## 📁 Folder Structure

```
RetailPulse/
├── agents/               # AI Agents
│   ├── planner_agent.py    # Decides which agents to invoke
│   ├── query_agent.py      # Parses natural language
│   ├── sql_agent.py        # Generates safe SQL (SELECT only)
│   ├── visualization_agent.py  # Creates Plotly charts
│   ├── forecast_agent.py   # Prophet + LSTM forecasting
│   ├── insight_agent.py    # Business insights generation
│   ├── pdf_agent.py        # PDF report generation
│   └── email_agent.py      # SMTP email with attachments
├── database/
│   ├── db.py               # SQLAlchemy connection + read-only queries
│   ├── models.py           # ORM models
│   └── schema.sql          # Database schema + sample data
├── forecasting/
│   ├── prophet_model.py    # Facebook Prophet
│   ├── lstm_model.py       # TensorFlow LSTM
│   └── ensemble.py         # Weighted ensemble
├── graphs/
│   └── workflow.py         # LangGraph StateGraph orchestrator
├── prompts/
│   ├── planner_prompt.py   # Planner prompt template
│   ├── sql_prompt.py       # SQL generation prompt
│   ├── visualization_prompt.py
│   └── insight_prompt.py   # Business insight prompt
├── tools/
│   └── llm_wrapper.py      # Unified LLM (OpenAI/Gemini/Ollama)
├── utils/
│   ├── config.py           # Pydantic settings
│   └── logger.py           # Structured logging
├── api.py                  # FastAPI REST API
├── streamlit_app.py        # Streamlit dashboard
├── main.py                 # Entry point
├── docker-compose.yml      # Docker orchestration
├── Dockerfile
└── requirements.txt
```

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.11+
- A Gemini API key (or OpenAI/Ollama)

### Option 1: Docker (Recommended)

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env → set GEMINI_API_KEY

# 2. Start everything
docker compose up

# 3. Open browser
# Streamlit: http://localhost:8501
# FastAPI:   http://localhost:8000/docs
```

### Option 2: Local Development

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start PostgreSQL (Docker or local)
docker compose up postgres -d

# 3. Import data
psql -U retailpulse -d retailpulse_db -f database/schema.sql

# 4. Configure
cp .env.example .env
# Edit .env → set GEMINI_API_KEY and DATABASE_URL

# 5. Start FastAPI
python main.py

# 6. Start Streamlit (new terminal)
streamlit run streamlit_app.py
```

## 📊 Features

### Natural Language Querying
Ask questions like:
- "Show sales of electronics during March"
- "Compare revenue of 2024 vs 2025"
- "Which products should be restocked?"
- "Forecast next month's sales"
- "Generate inventory report"

### Dashboards
- **Sales Dashboard**: Revenue KPIs, trends, category breakdown, regional performance
- **Inventory**: Stock levels, low stock alerts, refill recommendations
- **Customers**: Segments, top buyers, city distribution
- **Forecasting**: Prophet + LSTM with confidence intervals

### AI Agents
| Agent | Role |
|-------|------|
| 🧠 Planner | Analyzes query → decides which agents to invoke |
| 🔍 Query Parser | Extracts intent, entities, time period |
| 🗄️ SQL Agent | Generates safe SELECT queries (blocks mutations) |
| 📊 Visualization | Auto-selects chart type, creates Plotly charts |
| 🔮 Forecast | Prophet + LSTM ensemble forecasting |
| 💡 Insight | Business insights and recommendations |
| 📄 PDF | Professional report generation |
| 📧 Email | SMTP email with PDF attachment |

### REST API
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | System health check |
| `/query` | POST | Full agentic pipeline |
| `/report` | POST | Generate PDF report |
| `/email` | POST | Send email with attachment |
| `/forecast` | POST | Run sales forecast |
| `/schema` | GET | Database schema info |

## 🔒 Security
- SQL Agent only generates SELECT queries
- Dangerous keywords (INSERT, UPDATE, DELETE, DROP, etc.) are blocked
- Database connection is read-only
- All credentials in .env (never hardcoded)

## 📈 Future Improvements
- Real-time streaming with WebSockets
- Shopify/WooCommerce integration
- Multi-tenant support
- Advanced anomaly detection
- Voice query support
- Mobile-responsive dashboard

## 📄 License
MIT License — Built for educational and commercial use.
