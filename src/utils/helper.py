import os
from datetime import datetime, timezone, timedelta
import json
import hashlib
import secrets
import re
from pathlib import Path
from string import Template
from typing import Optional, Any
from cryptography.fernet import Fernet
import logging
from pillow_heif import register_heif_opener
from PIL import Image
import io

from src.core.conf import ENCRYPTION_KEY

register_heif_opener()
logger = logging.getLogger("DocVision")
cipher_suite = Fernet(ENCRYPTION_KEY)

def configure_settings(data_dict, filename="config.json"):
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as json_file:
                data_dict = json.load(json_file)
            return data_dict
        except FileNotFoundError:
            logger.warning(f"Error: File '{filename}' not found")

        except json.JSONDecodeError:
            logger.warning(f"Error: File '{filename}' contains invalid JSON")
            os.remove(filename)

        except Exception as e:
            logger.warning(f"Error reading JSON file: {e}")
            os.remove(filename)


    try:
        with open(filename, 'w', encoding='utf-8', errors="replace") as json_file:
            json.dump(data_dict, json_file, indent=4, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error writing to JSON file: {e}")
    else:
        return data_dict

def hash_password(password: str) -> str:
    """Hash password with salt for security"""
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
    return f"{salt}:{pwd_hash.hex()}"


def validate_password(password) -> dict:
    """Validate password strength"""
    min_length = 8
    max_length = 128

    # Check minimum length
    if len(password) < min_length:
        return {"ok": False, "desc": f'Password must be at least {min_length} characters long'}

    # Check maximum length
    if len(password) > max_length:
        return {"ok": False, "desc": f'Password must be no more than {max_length} characters long'}


    # Check for at least one lowercase letter
    if not re.search(r'[a-z]', password):
        return {"ok": False, "desc": 'Password must contain at least one lowercase letter'}

    # Check for at least one digit
    if not re.search(r'\d', password):
        return {"ok": False, "desc": 'Password must contain at least one digit'}

    return {"ok": True, "desc": "Success"}

def verify_password(stored_password: str, input_password: str) -> bool:
    salt, hashed = stored_password.split(":")
    input_hash = hashlib.pbkdf2_hmac('sha256', input_password.encode(), salt.encode(), 100000).hex()
    return hashed == input_hash

def load_template_from_txt(template_file="email_verification_template.txt"):
    """Load template from text file"""
    default_template = """
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #4CAF50;">Email Verification</h2>
        <p>Salom,</p>
        <p>
            ${app_name} bilan ro'yxatdan o'tganingiz uchun tashakkur. 
            Ro'yxatdan o'tishni yakunlash uchun quyidagi tasdiqlash 
            kodidan foydalaning:
        </p>

        <div style="background-color: #f4f4f4; padding: 20px; text-align: center; margin: 20px 0; border-radius: 5px;">
            <h1 style="color: #4CAF50; font-size: 32px; margin: 0; letter-spacing: 5px;">${verification_code}</h1>
        </div>

        <p><strong>Muhim:</strong></p>
        <ul>
            <li>Ushbu kod 10 daqiqadan so'ng amal qilish muddati tugaydi</li>
            <li>Bu kodni hech kim bilan ulashmang</li>
            <li>Agar tasdiqlash kodi so'ramagan bo'lsangiz, iltimos, ushbu elektron pochta xabarini e'tiborsiz qoldiring</li>
        </ul>

        <p>Hurmat bilan,<br>${app_name} jamoasi</p>
    </div>
</body>
</html>"""

    try:
        with open(template_file, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        # Create default template file
        with open(template_file, 'w', encoding='utf-8') as f:
            f.write(default_template)
        return default_template

def format_message_from_template(template_content, **kwargs):
    """Format message using text template"""
    template = Template(template_content)
    return template.safe_substitute(**kwargs)

def unix_to_formatted_string(unix_timestamp, shift_hours: int = 0):
    date_obj = datetime.fromtimestamp(unix_timestamp)
    desired_timezone = timezone(timedelta(hours=shift_hours))
    changed_time = date_obj.astimezone(desired_timezone)
    return changed_time.strftime('%d.%m.%Y %H:%M:%S')

def convert_to_unix_timestamp(date_str, date_format="%d.%m.%Y %H:%M:%S"):
    utc_plus_5 = timezone(timedelta(hours=5))
    dt = datetime.strptime(date_str, date_format)
    dt = dt.replace(tzinfo=utc_plus_5)
    unix_timestamp = int(dt.timestamp())
    return unix_timestamp

def format_number(number: float) -> str:
    str_num = str(number)
    integer_part, *decimal_part = str_num.split('.')

    length = len(integer_part)
    groups = []
    for i in range(length, 0, -3):
        start = max(0, i - 3)
        groups.append(integer_part[start:i])
    formatted_integer = ' '.join(reversed(groups))

    if not decimal_part or decimal_part[0] == '0':
        return formatted_integer
    return f"{formatted_integer}.{decimal_part[0][:2]}"


def delete_all_files(path):
    """
    Delete all files in the specified directory that are older than 10 minutes.

    Args:
        path: Absolute or relative path to the directory

    Returns:
        dict: Summary with counts of deleted files, skipped files, and any errors
    """
    try:
        # Convert to Path object and resolve to absolute path
        directory = Path(path).resolve()

        # Check if directory exists
        if not directory.exists():
            return {"error": f"Path does not exist: {directory}"}

        # Check if it's a directory
        if not directory.is_dir():
            return {"error": f"Path is not a directory: {directory}"}

        deleted_count = 0
        skipped_count = 0
        errors = []

        # Calculate the cutoff time (10 minutes ago)
        cutoff_time = datetime.now() - timedelta(minutes=10)

        # Iterate through all items in the directory
        for item in directory.iterdir():
            try:
                if item.is_file():
                    # Get file creation time (or modification time as fallback)
                    file_ctime = datetime.fromtimestamp(item.stat().st_ctime)

                    # Delete only if file is older than 10 minutes
                    if file_ctime < cutoff_time:
                        item.unlink()  # Delete the file
                        deleted_count += 1
                    else:
                        skipped_count += 1

            except Exception as e:
                errors.append(f"Error processing {item.name}: {str(e)}")

        return {
            "deleted": deleted_count,
            "skipped": skipped_count,
            "errors": errors if errors else None,
            "path": str(directory),
            "cutoff_time": cutoff_time.strftime("%Y-%m-%d %H:%M:%S")
        }

    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}

def encrypt_token(api_key: str) -> str:
    """Encrypt API key"""
    return cipher_suite.encrypt(api_key.encode()).decode()

def decrypt_token(encrypted_key: str) -> str:
    """Decrypt API key"""
    return cipher_suite.decrypt(encrypted_key.encode()).decode()

def click_generate_sign_string(
    click_trans_id: str,
    service_id: str,
    secret_key: str,
    merchant_trans_id: str,
    merchant_prepare_id: str,
    amount: str,
    action: str,
    sign_time: str,
):
    """Generate MD5 signature according to Click API spec"""
    data = f"{click_trans_id}{service_id}{secret_key}{merchant_trans_id}{merchant_prepare_id}{amount}{action}{sign_time}"
    return hashlib.md5(data.encode("utf-8")).hexdigest()


def parse_json_from_response(response: str) -> Optional[dict | list]:
    """
    Extract and parse JSON from a string that may contain markdown code blocks.

    Handles formats like:
    - ```json\n{...}\n```
    - ```\n{...}\n```
    - Plain JSON: {...}

    Args:
        response: String potentially containing JSON in markdown code blocks

    Returns:
        Parsed dictionary or None if parsing fails
    """
    try:
        # Method 1: Try to find JSON in code blocks (```json or ```)
        json_pattern = r'```(?:json)?\s*\n?(.*?)\n?```'
        matches = re.findall(json_pattern, response, re.DOTALL)

        if matches:
            # Try each match (in case there are multiple code blocks)
            for match in matches:
                try:
                    return json.loads(match.strip())
                except json.JSONDecodeError:
                    continue

        # Method 2: Try to parse the entire response as JSON
        return json.loads(response.strip())

    except json.JSONDecodeError as e:
        print(f"JSON parsing error: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None


def parse_json_strict(response: str) -> dict:
    """
    Parse JSON strictly - raises exception if parsing fails.

    Args:
        response: String containing JSON

    Returns:
        Parsed dictionary

    Raises:
        ValueError: If JSON cannot be parsed
    """
    result = parse_json_from_response(response)
    if result is None:
        raise ValueError("Failed to parse JSON from response")
    return result


async def compress_file(content: bytes, extension: str) -> bytes:
    """Compress file content"""
    try:
        # Image formats that PIL can handle
        extension_lower = extension.lower()

        if extension_lower in ['.jpg', '.jpeg', '.png', '.webp', '.bmp']:
            img = Image.open(io.BytesIO(content))
            output = io.BytesIO()

            # Determine output format
            format_map = {
                '.jpg': 'JPEG',
                '.jpeg': 'JPEG',
                '.png': 'PNG',
                '.webp': 'WEBP'
            }

            save_format = format_map.get(extension.lower(), img.format)

            # Compress based on format
            if save_format == 'PNG':
                img.save(output, format='PNG', optimize=True)
            else:
                img.save(output, format=save_format, quality=85, optimize=True)

            return output.getvalue()

        elif extension_lower in ['.heic', '.heif']:
            # HEIC/HEIF - pass through or convert to JPEG if needed
            # Note: PIL might not support HEIC without pillow-heif plugin
            try:
                img = Image.open(io.BytesIO(content))
                output = io.BytesIO()
                img.save(output, format='JPEG', quality=85, optimize=True)
                return output.getvalue()
            except Exception as e:
                logger.error(f"Error compressing file: {e}")
                return content  # Return original if conversion fails

        elif extension_lower == '.pdf':
            return content  # PDF - no compression

        else:
            return content  # Pass through unknown types

    except Exception as e:
        logger.info(f"Compression error: {e}")
        return content


def write_json_file(
        data: Any,
        file_path: str = "test.json",
        indent: int = 4,
        ensure_ascii: bool = False,
        create_dirs: bool = True
) -> bool:
    """
    Write Python object to JSON file with error handling.

    Args:
        data: Python object to write (dict, list, etc.)
        file_path: Path to the output JSON file
        indent: Number of spaces for indentation (None for compact)
        ensure_ascii: If False, non-ASCII characters are preserved
        create_dirs: If True, create parent directories if they don't exist

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Convert to Path object for easier manipulation
        path = Path(file_path)

        # Create parent directories if needed
        if create_dirs and path.parent != Path('.'):
            path.parent.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created directory: {path.parent}")

        # Write to file with atomic operation (write to temp, then rename)
        temp_path = path.with_suffix('.tmp')

        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent, ensure_ascii=ensure_ascii)

        # Atomic rename (replaces existing file)
        temp_path.replace(path)

        logger.info(f"Successfully wrote JSON to: {file_path}")
        return True

    except TypeError as e:
        logger.error(f"Data is not JSON serializable: {e}")
        return False

    except PermissionError as e:
        logger.error(f"Permission denied writing to {file_path}: {e}")
        return False

    except OSError as e:
        logger.error(f"OS error writing to {file_path}: {e}")
        return False

    except Exception as e:
        logger.error(f"Unexpected error writing JSON to {file_path}: {e}")
        return False

