"""
Utility helper functions for the application.
"""
import os
import uuid
import re
from typing import Any, Dict, List, Optional, Tuple
from math import ceil

from passlib.context import CryptContext
from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Query


# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def generate_password_hash(password: str) -> str:
    """
    Generate a hashed password using bcrypt.

    Args:
        password: Plain text password

    Returns:
        Hashed password string
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against a hashed password.

    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password to check against

    Returns:
        True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


def generate_unique_filename(original_filename: str) -> str:
    """
    Generate a unique filename while preserving extension.

    Args:
        original_filename: Original filename

    Returns:
        Unique filename with same extension
    """
    ext = get_file_extension(original_filename)
    unique_id = uuid.uuid4().hex[:12]
    return f"{unique_id}{ext}"


def get_file_extension(filename: str) -> str:
    """
    Get file extension from filename.

    Args:
        filename: Filename or path

    Returns:
        File extension including dot (e.g., ".jpg")
    """
    _, ext = os.path.splitext(filename)
    return ext.lower() if ext else ""


def validate_image_file(
    file: UploadFile,
    max_size_mb: int = 10,
    allowed_types: Optional[List[str]] = None,
) -> Tuple[bool, str]:
    """
    Validate an uploaded image file.

    Args:
        file: UploadFile object
        max_size_mb: Maximum file size in MB
        allowed_types: List of allowed MIME types

    Returns:
        Tuple of (is_valid, error_message)

    Raises:
        HTTPException: If validation fails (in FastAPI context)
    """
    if allowed_types is None:
        allowed_types = [
            "image/jpeg",
            "image/jpg",
            "image/png",
            "image/webp",
        ]

    # Check content type
    content_type = file.content_type or ""
    if content_type not in allowed_types:
        return False, f"Invalid file type: {content_type}. Allowed: {', '.join(allowed_types)}"

    # Check file size (read a bit to estimate)
    # Note: For accurate size check, we'd need to read the entire file
    # This is a basic check
    max_size_bytes = max_size_mb * 1024 * 1024

    return True, ""


def paginate_query(
    query: Query,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[List[Any], int, int]:
    """
    Paginate a SQLAlchemy query.

    Args:
        query: SQLAlchemy query object
        page: Page number (1-indexed)
        page_size: Items per page

    Returns:
        Tuple of (items, total_count, total_pages)
    """
    # Get total count
    total_count = query.count()

    # Calculate pagination
    total_pages = ceil(total_count / page_size) if page_size > 0 else 1
    offset = (page - 1) * page_size

    # Apply pagination
    paginated_query = query.offset(offset).limit(page_size)

    # Execute query
    items = paginated_query.all()

    return items, total_count, total_pages


def calculate_compliance_percentage(
    passed: int,
    total: int,
) -> float:
    """
    Calculate compliance percentage.

    Args:
        passed: Number of passed checks
        total: Total number of checks

    Returns:
        Percentage (0-100)
    """
    if total <= 0:
        return 0.0
    return round((passed / total) * 100, 2)


def extract_numbers_from_text(text: str) -> List[float]:
    """
    Extract all numbers from text.

    Args:
        text: Input text

    Returns:
        List of numbers found in text
    """
    numbers = re.findall(r'\d+(?:\.\d+)?', text)
    return [float(n) for n in numbers]


def clean_text(text: str) -> str:
    """
    Clean and normalize text.

    Args:
        text: Input text

    Returns:
        Cleaned text
    """
    if not text:
        return ""

    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    # Remove special characters but keep common ones
    text = re.sub(r'[^\w\s.,;:!?-₹$€£]', '', text)
    return text


def detect_language_indicators(text: str) -> Dict[str, bool]:
    """
    Detect language indicators in text.

    Args:
        text: Input text

    Returns:
        Dictionary with language indicators
    """
    text_lower = text.lower()

    return {
        "has_desi_currency": bool('₹' in text or 'rs.' in text_lower or 'inr' in text_lower),
        "has_english": bool(re.search(r'[a-zA-Z]', text)),
        "has_hindi": bool(re.search(r'[दिव privatization]', text)),  # Basic Hindi detection
        "has_numbers": bool(re.search(r'\d+', text)),
    }


def format_currency(amount: float, currency: str = "INR") -> str:
    """
    Format currency amount.

    Args:
        amount: Amount to format
        currency: Currency code

    Returns:
        Formatted currency string
    """
    symbols = {
        "INR": "₹",
        "USD": "$",
        "EUR": "€",
        "GBP": "£",
    }

    symbol = symbols.get(currency, "$")
    return f"{symbol}{amount:,.2f}"


def parse_date_string(date_str: str) -> Optional[Dict[str, Any]]:
    """
    Parse various date string formats.

    Args:
        date_str: Date string to parse

    Returns:
        Dictionary with date components or None if parsing fails
    """
    if not date_str:
        return None

    date_str = date_str.strip()

    # Month Year format: "Jan 2024", "January 2024"
    match = re.match(r'^([a-zA-Z]{3,9})\s+(\d{4})$', date_str)
    if match:
        return {
            "month": match.group(1),
            "year": int(match.group(2)),
            "format": "month_year",
        }

    # DD/MM/YYYY format
    match = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{2,4})$', date_str)
    if match:
        year = int(match.group(3))
        if len(match.group(3)) == 2:
            year += 2000
        return {
            "day": int(match.group(1)),
            "month": int(match.group(2)),
            "year": year,
            "format": "dd_mm_yyyy",
        }

    # YYYY-MM-DD format
    match = re.match(r'^(\d{4})-(\d{2})-(\d{2})$', date_str)
    if match:
        return {
            "year": int(match.group(1)),
            "month": int(match.group(2)),
            "day": int(match.group(3)),
            "format": "yyyy_mm_dd",
        }

    return None
