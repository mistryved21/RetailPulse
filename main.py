"""RetailPulse — Main entry point."""
import os
import sys
import uvicorn

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.config import settings
from utils.logger import get_logger

logger = get_logger(__name__)


def setup_directories() -> None:
    """Create required directories."""
    for d in [settings.REPORTS_DIR, "logs", "static"]:
        os.makedirs(d, exist_ok=True)


def check_database() -> bool:
    """Verify database connection."""
    try:
        from database.db import check_connection
        if check_connection():
            logger.info("✅ Database connected")
            return True
        logger.error("❌ Database connection failed")
        return False
    except Exception as e:
        logger.error(f"❌ Database error: {e}")
        return False


def main() -> None:
    """Start RetailPulse FastAPI server."""
    logger.info("=" * 60)
    logger.info("  🔮 RetailPulse — Agentic AI Retail Analytics")
    logger.info("=" * 60)

    setup_directories()
    db_ok = check_database()

    if not db_ok:
        logger.warning("Starting without database")

    logger.info(f"LLM: {settings.LLM_PROVIDER} | Env: {settings.ENVIRONMENT}")
    logger.info("API: http://0.0.0.0:8000 | Docs: http://0.0.0.0:8000/docs")
    logger.info("Start Streamlit: streamlit run streamlit_app.py")
    logger.info("=" * 60)

    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.ENVIRONMENT == "development",
        workers=1,
        log_level=settings.LOG_LEVEL.lower(),
    )


if __name__ == "__main__":
    main()
