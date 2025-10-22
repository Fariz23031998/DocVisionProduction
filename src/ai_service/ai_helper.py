import pdfplumber
import pandas as pd
import fitz
import os
import logging

logger = logging.getLogger("DocVision")


def extract_text_from_pdf(file_path):
    text = ""
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            lines = page.extract_text().split("\n")  # split text into lines
            for line in lines:
                for word in line.split(" "):
                    text += word + " "
                text += "\n"
    return text


def save_pdf_as_images(pdf_path, output_dir=None):
    """Convert PDF to images and save them (testing purposes only)"""
    try:
        if not output_dir:
            base_name = os.path.splitext(os.path.basename(pdf_path))[0]
            output_dir = f"{base_name}_images"
        
        os.makedirs(output_dir, exist_ok=True)
        
        doc = fitz.open(pdf_path)
        saved_files = []
        
        for page_num in range(len(doc)):  # Process all pages
            page = doc[page_num]
            # High quality conversion
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x scaling
            output_path = os.path.join(output_dir, f"page_{page_num + 1}.png")
            pix.save(output_path)
            saved_files.append(output_path)
            logger.info(f"Saved: {output_path}")
        
        doc.close()
        logger.info(f"Converted {len(saved_files)} pages to {output_dir}/")
        return saved_files
        
    except Exception as e:
        logger.error(f"Error: {e}")
        return []

def get_file_type(file_name):
    """Determine file type based on extension"""
    extension = file_name.lower().split('.')[-1]
    
    image_types = ['jpg', 'jpeg', 'png', 'gif', 'webp']
    pdf_types = ['pdf']
    excel_types = ['xlsx', 'xls', 'csv']
    
    if extension in image_types:
        return 'image', f'image/{extension if extension != "jpg" else "jpeg"}'
    elif extension in pdf_types:
        return 'pdf', None
    elif extension in excel_types:
        return 'excel', None
    else:
        return 'unknown', None

def extract_text_from_excel(file_path):
    """Extract text from Excel/CSV files"""
    try:
        extension = file_path.lower().split('.')[-1]
        
        if extension == 'csv':
            df = pd.read_csv(file_path)
        else:  # xlsx, xls
            df = pd.read_excel(file_path)
        
        # Convert dataframe to readable text format
        text = ""

        text += df.to_string(index=False, max_rows=50)  # Limit rows to avoid token limits
        
        if len(df) > 100:
            text += f"\n\n... (showing first 100 rows out of {len(df)} total rows)"
            
        return text
    except Exception as e:
        logger.error(f"Error extracting Excel/CSV text: {e}")
        return None