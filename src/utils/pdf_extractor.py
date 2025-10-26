import ast
import json
import logging

import pdfplumber
from typing import List, Tuple, Dict, Any

logger = logging.getLogger("DocVision")

def extract_pdf_tables_to_tuples(pdf_path: str) -> list[tuple]:
    """
    Extracts all table-like data from a PDF file and returns as a list of tuples.
    Each inner tuple represents one row (cells in order).

    Args:
        pdf_path (str): Path to the PDF file.

    Returns:
        list[tuple]: A flat list of all rows from all detected tables.
    """
    all_rows = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    # Clean up each cell (strip whitespace, replace None)
                    cleaned_row = tuple((cell or "").strip() for cell in row)
                    all_rows.append(cleaned_row)

    return all_rows

def read_pdf_text(pdf_path: str) -> str:
    """
    Reads all text content from a PDF file and returns it as a single string.

    Args:
        pdf_path (str): Path to the PDF file.

    Returns:
        str: Combined text content of all pages.
    """
    full_text = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()
            if text:
                full_text.append(f"{text}\n")

    return "\n".join(full_text)

from typing import List, Tuple, Dict, Any

from typing import List, Tuple, Dict, Any

def map_ai_response_to_dicts(
    table_rows: List[Tuple[Any, ...]],
    ai_response: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Converts a list of tuples (table rows) and AI response mapping
    into a structured list of dictionaries using 0-based indexing.

    - Columns use 0-based positive indices only.
    - Irrelevant rows can use negative indices to remove from the end.

    Args:
        table_rows (List[Tuple]): Extracted table rows.
        ai_response (Dict): AI response with 'columns', 'irrelevant_rows', etc.

    Returns:
        List[Dict]: List of mapped row dictionaries.
    """
    result = []
    column_mapping = ai_response.get("columns", {})
    irrelevant_rows = ai_response.get("irrelevant_rows", [])

    # 🔹 Normalize irrelevant row indices (handle negative ones)
    normalized_irrelevant_rows = set()
    total_rows = len(table_rows)
    for r in irrelevant_rows:
        if r < 0:
            normalized_irrelevant_rows.add(total_rows + r)  # convert -1 → last index, etc.
        else:
            normalized_irrelevant_rows.add(r)

    for row_idx, row in enumerate(table_rows):
        # Skip irrelevant rows (after normalization)
        if row_idx in normalized_irrelevant_rows:
            continue

        item = {}
        for key, col_index in column_mapping.items():
            if 0 <= col_index < len(row):
                item[key] = row[col_index]
            else:
                item[key] = None

        # Add only if row has any non-empty value
        if any(item.values()):
            result.append(item)

    return result



def parse_string_to_list(string_data):
    """Convert string to list of dicts with multiple fallback methods"""
    try:
        # Try ast.literal_eval first (handles Python syntax)
        return ast.literal_eval(string_data)
    except (ValueError, SyntaxError):
        # Remove markdown code blocks
        cleaned_data = string_data.replace("```json", "").replace("```", "").strip()

        try:
            # Try JSON parsing
            return json.loads(cleaned_data)
        except json.JSONDecodeError:
            try:
                # Try after replacing single quotes
                return json.loads(cleaned_data.replace("'", '"'))
            except json.JSONDecodeError:
                logger.error("Failed to parse string")
                return []

