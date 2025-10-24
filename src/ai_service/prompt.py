prompt_header_image = "Extract structured product-level JSON data from this receipt or table text."
prompt_header_pdf = "Extract structured product-level JSON data from this extracted text from pdf."
prompt_header_excel = "Extract structured product-level JSON data from this extracted text from excel."

prompt_common_rules = """
- Map product details to the following keys: name, unit_name, quantity, cost, barcodes, code and group_path.
- Barcode values can be found in the columns labeled "штрихкод" or "barcode", you should return it as string.
- If a value does not correspond to any of these keys, use the column name as the key.
- If the receipt does not include column names, assign appropriate keys yourself.
- Support multiple languages, including Russian, Uzbek, English, Chinese, and others.
- Convert all numbers to numeric form (e.g., 546,52 → 546.52).
- Ignore totals, discounts, headers, and footers.
- Treat the “price” column/value as cost, since the products are sold to us.
- If a name contains a package size (e.g., “156 g”, “2 L”, “10 pcs”, “25 шт”, “100 гр”, “5 л”), treat it as part of the name.
- Do not use package sizes as unit_name. The unit_name is only for true measurement units describing one selling unit (e.g., “bottle”, “pack”, “box”, “kg” if it’s explicitly used as a column or unit type).
- If it’s unclear whether a value is a unit or a size, assume it’s part of the name.
- Never separate or normalize the package size — keep it exactly as it appears in the name.
- If no products are found, return exactly ###false### as a string.
- If products are found, output only valid JSON (no extra text, no ```json code fences).
- Return all rows, even if some fields are uncertain. Do not skip low-confidence entries.
"""

image_example = """
        МИНИ МАРКЕТ
Дата и время: 24.08.2025 22:11
Тип:                   Продажа
Кассир:            Иванов Иван
Касса:                      №3
--------------------------------
1. Картошка Россия [кг]
            1,345 x 12000,00 = 16 140,00
                                 НДС 12%
2. Бонаква 0,5л [шт]
                 3 x 8000,00 = 24 000,00
                                 НДС 12%
Итого:                         40 140,00
Наличные:                      40 140,00
"""

image_json_example = """
[
    {
        "name": "Картошка Россия",
        "unit_name": "кг"
        "quantity": 1.345,
        "cost": 12000,
        "total_cost": 16140,
        "НДС": "12%" 
    },
    {
        "name": "Бонаква 0,5л",
        "unit_name": "шт"
        "quantity": 3,
        "cost": 8000,
        "total_cost": 24000,
        "НДС": "12%" 
    }
]
"""

pdf_prompt = """
Example with Russian invoice document (The data was extracted from a PDF, which makes it hard to see which value belongs to which column.):

JSON Output:

Here's the extracted text from the PDF:
"""

pdf_example = """
Приходная накладная № 2448
Получатель: GOODLIFE MARKET
Отправитель: САЛИМ БОЙФРЕНК
Код документа:2448
Примечание:
№ Код Номенклатура Артикул Ед. изм. Кол-во Стоим. Сумма
1 13045 ЧАККА 800г шт 125.000 8 500 1 062 500
2 13046 ЧАККА 400г шт 65.000 5 000 325 000
3 12066 ЯЙЦО КУРИНОЕ шт 900.000 1 216.67 1 095 003
2 482 503
Два миллиона четыреста восемьдесят две тысячи пятьсот три сум 00 тийин
Отправитель Получатель
"""

pdf_json_example = """
[
    {
        "№": 1,
        "Код": 13045,
        "name": "ЧАККА 800г",
        "Артикул": "",
        "unit_name": "шт",
        "quantity": 125,
        "cost": 8500,
        "Сумма": 1062500
    },
    {
        "№": 2,
        "Код": 13046,
        "name": "ЧАККА 400г",
        "Артикул": "",
        "unit_name": "шт",
        "quantity": 65,
        "cost": 5000,
        "Сумма": 325000
    },
    {
        "№": 3,
        "Код": 12066,
        "name": "ЯЙЦО КУРИНОЕ",
        "Артикул": "",
        "unit_name": "шт",
        "quantity": 900,
        "cost": 1 216.67,
        "Сумма": 1095003
    }
]
"""

excel_prompt = """


Example with Russian invoice document (Extracted data from Excel may contain non-table text. Please ignore it.):

JSON Output:

Here's the table data:

"""

excel_example = """
 Unnamed: 0                                             Приходная накладная № 2448 Unnamed: 2      Unnamed: 3  Unnamed: 4  Unnamed: 5  Unnamed: 6 Unnamed: 7 Unnamed: 8 Unnamed: 9 Unnamed: 10
        NaN                                                            Получатель:        NaN GOODLIFE MARKET         NaN         NaN         NaN        NaN        NaN        NaN         NaN
        NaN                                                           Отправитель:        NaN  САЛИМ БОЙФРЕНК         NaN         NaN         NaN        NaN        NaN        NaN         NaN
        NaN                                                                    NaN        NaN             NaN         NaN         NaN         NaN        NaN        NaN        NaN         NaN
        NaN                                                         Код документа:        NaN            2448         NaN         NaN         NaN        NaN        NaN        NaN         NaN
        NaN                                                            Примечание:        NaN             NaN         NaN         NaN         NaN        NaN        NaN        NaN         NaN
        NaN                                                                    NaN        NaN             NaN         NaN         NaN         NaN        NaN        NaN        NaN         NaN
        NaN                                                                    NaN        NaN             NaN         NaN         NaN         NaN        NaN        NaN        NaN         NaN
        NaN                                                                      №        Код    Номенклатура     Артикул         NaN         NaN   Ед. изм.     Кол-во     Стоим.       Сумма
        NaN                                                                      1      13045      ЧАККА 800г         NaN         NaN         NaN         шт        125      8 500   1 062 500
        NaN                                                                      2      13046      ЧАККА 400г         NaN         NaN         NaN         шт         65      5 000     325 000
        NaN                                                                      3      12066    ЯЙЦО КУРИНОЕ         NaN         NaN         NaN         шт        900   1 216.67   1 095 003
        NaN                                                                    NaN        NaN             NaN         NaN         NaN         NaN        NaN        NaN        NaN   2 482 503
        NaN Два миллиона четыреста восемьдесят две тысячи пятьсот три сум 00 тийин        NaN             NaN         NaN         NaN         NaN        NaN        NaN        NaN         NaN
        NaN                                                                    NaN        NaN             NaN Отправитель         NaN         NaN        NaN        NaN Получатель         NaN
"""

excel_json_example = """
[
    {
        "№": 1,
        "Код": 13045,
        "name": "ЧАККА 800г",
        "Артикул": "",
        "unit_name": "шт",
        "quantity": 125,
        "cost": 8500,
        "Сумма": 1062500
    },
    {
        "№": 2,
        "Код": 13046,
        "name": "ЧАККА 400г",
        "Артикул": "",
        "unit_name": "шт",
        "quantity": 65,
        "cost": 5000,
        "Сумма": 325000
    },
    {
        "№": 3,
        "Код": 12066,
        "name": "ЯЙЦО КУРИНОЕ",
        "Артикул": "",
        "unit_name": "шт",
        "quantity": 900,
        "cost": 1 216.67,
        "Сумма": 1095003
    }
]
"""

def create_prompt(prompt_type: str, extracted_data: str | None = None, user_request: str | None = None) -> str:
    """
    Build a formatted prompt for an LLM based on the input file type and user instructions.

    Args:
        prompt_type (str): Type of input document.
            - "excel" → Generates a prompt for Excel-based data.
            - "pdf" → Generates a prompt for PDF-based data.
            - Any other value → Generates a prompt for image-based data.
        extracted_data (str | None, optional): Raw extracted text from the file
            (Excel, PDF, or image). Defaults to None.
        user_request (str | None, optional): Additional user instruction to append
            to the prompt. Defaults to None.

    Returns:
        str: A fully constructed prompt string containing examples, JSON output
        templates, extracted data, and optional user instructions.

    Example:
        # >>> create_prompt("pdf", extracted_data="Invoice data ...", user_request="Add a price field to the JSON, set to 20% more than cost")
        "Prompt with PDF rules, examples, and extracted text, followed by 'Additional request: Add a price field to the JSON, set to 20% more than cost'"
    """
    if prompt_type == "excel":
        final_prompt = f"""{prompt_header_excel}{prompt_common_rules}
Example with Russian invoice document (Extracted data from Excel may contain non-table text. Please ignore it.):{excel_example}
JSON Output:{excel_json_example}
Here's the extracted text from the Excel document:
{extracted_data}
"""
    elif prompt_type == "pdf":
        final_prompt = f"""{prompt_header_pdf}{prompt_common_rules}
Example with Russian invoice document (The data was extracted from a PDF, which makes it hard to see which value belongs to which column.):{pdf_example}
JSON Output:{pdf_json_example}
Here's the extracted text from the PDF:
{extracted_data}
"""
    else:
        final_prompt = f"""{prompt_header_image}{prompt_common_rules}
Example with Russian receipt:{image_example}
JSON Output:{image_json_example}
"""

    if user_request is not None:
        final_prompt += f"""Additional request:
{user_request}"""

    return final_prompt

AI_PROMPT_EXCEL_COLUMN_MAPPING = """
You are an AI model that extracts structured, table-like data from Excel files.
We send you only the top rows of the Excel sheet to detect and assign column names from the provided list below.
Column names in the Excel file usually appear in Russian or English.

Important detection rules:
- Always map "Номенклатура" (and any similar column like "Товар", "Наименование", "Product", "Item") to the key "name".
- The "name" column is the main column that represents the product title and is mandatory if it exists.
- Never skip or mark "Номенклатура" as irrelevant — it should always be included in "columns" with the key "name".
- If both "Код" and "Номенклатура" exist, "Код" is usually an internal ID, while "Номенклатура" is the actual product name.
- Always try to detect and map "Группа", "Группа товаров", "Категория", "Group", or "Category" columns to the key "group_path".
    This column represents the full category path of the product (e.g., “Еда/Фрукты/Бананы”).
    If found, it should be included in "columns" with the key "group_path", not marked as irrelevant.

  {
    "name": 3,
    "articul": 4,
    "unit_name": 5,
    "quantity": 6,
    "cost": 7
  }
- If a row contains column headers (for example, “Наименование”, “Артикул”, “Ед. изм.”, “Кол-во”, etc.), treat it as a header row and include its index in the irrelevant_rows list, since headers are not actual data rows.

Your task:
Return only JSON data containing:
- "columns": assigned column names with their column indexes,
- "irrelevant_columns": list of column indexes that are not in provided list below,
- "irrelevant_rows": list of row indexes that don't have enough content.

Column names to choose from:
name — Short product name or title. (Наименование, Номенклатура, Товар, Продукт)
fullname — Full or extended product name with details. (Полное наименование)
articul — Article number or internal product code. (Артикул, Код номенклатуры)
group_path — Full group/category path (e.g., 'Food/Beverages'). (Группа (структура/путь))
barcodes — One or more barcodes of the product. (Штрихкод, Штрихкоды)
color_name — Product color. (Цвет)
brand_name — Brand or trademark. (Бренд)
producer_name — Manufacturer or producer name. (Производитель)
size_name — Product size or dimension (e.g., '500ml', 'L'). (Размер)
unit_name — Unit of measurement (e.g., 'pcs', 'kg'). (Единица измерения)
department_name — Department or product section. (Отдел)
description — Product description or ingredients. (Описание)
vat_name — VAT (Value Added Tax) rate applied. (Ставка НДС)
icps — Product classification code. (ИКПУ)
labeled — Indicates if the product requires mandatory labeling. (Метка обязательной маркировки)
package_code — Packaging code (type or batch). (Код упаковки)
parent_code — Parent product code for variations. (Код родителя (для создания вариации))
quantity — Quantity of the product (number of units). (Кол-во, Количество)
cost — Purchase or cost price. (Себестоимость, Закупочная цена, Стоимость)
price — Selling price of the product. (Цена)

Output format (JSON only):
{
  "columns": {
    "name": 1,
    "barcodes": 2,
    "quantity": 4,
    "cost": 9
  },
  "irrelevant_columns": [3, 5, 7, 8],
  "irrelevant_rows": [1, 2, 3, 4, 5, 6, 7]
}

Notes for the AI:
- You missed name
- Ignore decorative headers, totals, or empty rows.
- Focus on identifying the most relevant columns that describe product data.
- If no relevant columns are found, return exactly ###false### as a string.
- Return only JSON — no extra text, comments, or code fences.
- To help you understand the table structure more accurately, each Excel row is wrapped between <ROW_START> and <ROW_END> tags, and every cell inside a row is enclosed in <CELL> and </CELL> tags. This ensures you can clearly detect where each row and cell begins and ends, even if some cell values contain spaces, commas, or line breaks.
"""

def create_gemini_prompt(prompt_type: str = "img"):
    header = prompt_header_pdf if prompt_type == "pdf" else prompt_header_image
    return f"""{header}{prompt_common_rules}"""


