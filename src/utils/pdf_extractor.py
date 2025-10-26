import pdfplumber

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
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            pages.append(page)
            tables = page.extract_tables()



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
                full_text.append(f"--- Page {page_number} ---\n{text}\n")

    return "\n".join(full_text)

# Example usage:
if __name__ == "__main__":
    pdf_path = "check.pdf"
    content = read_pdf_text(pdf_path)
    print(content)