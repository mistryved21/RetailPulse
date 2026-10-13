"""Multi-format file parser for RetailPulse.

Supports: CSV, Excel, Google Sheets, PDF, Word (.docx), JSON, TSV
"""
import os
import io
import logging
import tempfile
from typing import Optional

import pandas as pd
import requests

logger = logging.getLogger(__name__)


def parse_file(file_path: str = "", file_bytes: bytes = b"", filename: str = "") -> pd.DataFrame:
    """Parse any supported file format into a pandas DataFrame.

    Args:
        file_path: Path to file on disk
        file_bytes: Raw file bytes (from Streamlit upload)
        filename: Original filename (used to detect format)

    Returns:
        pd.DataFrame with parsed data

    Raises:
        ValueError: If format is unsupported or file is empty
    """
    if file_path:
        filename = filename or os.path.basename(file_path)
        with open(file_path, "rb") as f:
            file_bytes = f.read()

    if not file_bytes:
        raise ValueError("No file data provided")

    ext = os.path.splitext(filename)[1].lower() if filename else ""
    logger.info(f"Parsing file: {filename} (ext={ext}, size={len(file_bytes)} bytes)")

    try:
        if ext in (".csv", ".tsv"):
            return _parse_csv(file_bytes, ext)
        elif ext in (".xlsx", ".xls"):
            return _parse_excel(file_bytes)
        elif ext == ".json":
            return _parse_json(file_bytes)
        elif ext == ".pdf":
            return _parse_pdf(file_bytes)
        elif ext == ".docx":
            return _parse_docx(file_bytes)
        else:
            # Try CSV as default
            logger.warning(f"Unknown extension '{ext}', trying CSV parser")
            return _parse_csv(file_bytes, ".csv")
    except Exception as e:
        logger.error(f"Failed to parse {filename}: {e}")
        raise ValueError(f"Could not parse file '{filename}': {e}")


def parse_google_sheet(url: str) -> pd.DataFrame:
    """Parse a Google Sheets URL into a DataFrame.

    Converts the URL to CSV export format and downloads it.

    Args:
        url: Google Sheets URL (sharing link)

    Returns:
        pd.DataFrame with sheet data
    """
    try:
        # Convert Google Sheets URL to CSV export URL
        if "/edit" in url:
            url = url.split("/edit")[0]
        if "/pub" in url:
            csv_url = url.replace("/pub", "/export?format=csv")
        elif "spreadsheets/d/" in url:
            sheet_id = url.split("spreadsheets/d/")[1].split("/")[0]
            csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
        else:
            raise ValueError("Invalid Google Sheets URL")

        logger.info(f"Downloading Google Sheet: {csv_url}")
        response = requests.get(csv_url, timeout=30)
        response.raise_for_status()

        df = pd.read_csv(io.BytesIO(response.content))
        logger.info(f"Google Sheet parsed: {len(df)} rows, {len(df.columns)} columns")
        return df
    except Exception as e:
        logger.error(f"Google Sheets parsing failed: {e}")
        raise ValueError(f"Could not parse Google Sheet: {e}")


def _parse_csv(data: bytes, ext: str) -> pd.DataFrame:
    """Parse CSV or TSV file."""
    sep = "\t" if ext == ".tsv" else ","
    # Try different encodings
    for encoding in ["utf-8", "latin-1", "cp1252"]:
        try:
            df = pd.read_csv(io.BytesIO(data), sep=sep, encoding=encoding)
            logger.info(f"CSV parsed ({encoding}): {len(df)} rows, {len(df.columns)} columns")
            return df
        except UnicodeDecodeError:
            continue
    raise ValueError("Could not decode CSV with any supported encoding")


def _parse_excel(data: bytes) -> pd.DataFrame:
    """Parse Excel file (.xlsx or .xls)."""
    try:
        xls = pd.ExcelFile(io.BytesIO(data))
        # If multiple sheets, read all and concatenate
        if len(xls.sheet_names) == 1:
            df = pd.read_excel(io.BytesIO(data), sheet_name=0)
        else:
            logger.info(f"Excel has {len(xls.sheet_names)} sheets: {xls.sheet_names}")
            # Read first non-empty sheet
            for sheet in xls.sheet_names:
                df = pd.read_excel(io.BytesIO(data), sheet_name=sheet)
                if not df.empty:
                    logger.info(f"Using sheet: {sheet}")
                    break
        logger.info(f"Excel parsed: {len(df)} rows, {len(df.columns)} columns")
        return df
    except Exception as e:
        raise ValueError(f"Excel parsing failed: {e}")


def _parse_json(data: bytes) -> pd.DataFrame:
    """Parse JSON file."""
    import json
    text = data.decode("utf-8")
    parsed = json.loads(text)

    if isinstance(parsed, list):
        df = pd.DataFrame(parsed)
    elif isinstance(parsed, dict):
        # Try common JSON structures
        if "data" in parsed:
            df = pd.DataFrame(parsed["data"])
        elif "records" in parsed:
            df = pd.DataFrame(parsed["records"])
        elif "results" in parsed:
            df = pd.DataFrame(parsed["results"])
        else:
            df = pd.json_normalize(parsed)
    else:
        raise ValueError("JSON structure not recognized")

    logger.info(f"JSON parsed: {len(df)} rows, {len(df.columns)} columns")
    return df


def _parse_pdf(data: bytes) -> pd.DataFrame:
    """Parse tables from PDF file using pdfplumber."""
    try:
        import pdfplumber
    except ImportError:
        raise ValueError("PDF parsing requires 'pdfplumber'. Install: pip install pdfplumber")

    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name

        all_tables = []
        with pdfplumber.open(tmp_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                tables = page.extract_tables()
                for table in tables:
                    if table and len(table) > 1:
                        # First row as header
                        headers = [str(h).strip() if h else f"col_{i}" for i, h in enumerate(table[0])]
                        rows = table[1:]
                        df = pd.DataFrame(rows, columns=headers)
                        all_tables.append(df)
                        logger.info(f"PDF page {page_num + 1}: extracted table with {len(df)} rows")

        os.unlink(tmp_path)

        if not all_tables:
            raise ValueError("No tables found in PDF")

        result = pd.concat(all_tables, ignore_index=True)
        logger.info(f"PDF parsed: {len(result)} total rows from {len(all_tables)} tables")
        return result
    except ImportError:
        raise
    except Exception as e:
        raise ValueError(f"PDF parsing failed: {e}")


def _parse_docx(data: bytes) -> pd.DataFrame:
    """Parse tables from Word document."""
    try:
        from docx import Document
    except ImportError:
        raise ValueError("DOCX parsing requires 'python-docx'. Install: pip install python-docx")

    try:
        doc = Document(io.BytesIO(data))
        all_tables = []

        for i, table in enumerate(doc.tables):
            rows = []
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells]
                rows.append(cells)

            if len(rows) > 1:
                headers = rows[0]
                data_rows = rows[1:]
                df = pd.DataFrame(data_rows, columns=headers)
                all_tables.append(df)
                logger.info(f"DOCX table {i + 1}: {len(df)} rows")

        if not all_tables:
            raise ValueError("No tables found in Word document")

        result = pd.concat(all_tables, ignore_index=True)
        logger.info(f"DOCX parsed: {len(result)} total rows")
        return result
    except ImportError:
        raise
    except Exception as e:
        raise ValueError(f"DOCX parsing failed: {e}")


def get_supported_formats() -> list[str]:
    """Return list of supported file extensions."""
    return [".csv", ".xlsx", ".xls", ".json", ".pdf", ".docx", ".tsv"]
