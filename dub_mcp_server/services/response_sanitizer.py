# Copyright 2025 Dubhe Srls
# License OPL-1

"""
Response sanitization service for MCP SSE.
Prevents large responses from causing asyncio.LimitOverrunError by truncating
oversized fields and excluding binary data.
"""
import json
import logging
from typing import Any

_logger = logging.getLogger(__name__)

# Maximum size for truncatable text fields (50KB)
MAX_FIELD_SIZE = 50 * 1024

# Fields that can be safely truncated (common large text fields in Odoo)
TRUNCATABLE_FIELDS = {
    "body", "body_html", "content", "description", "note", "notes",
    "comment", "internal_notes", "message", "arch", "arch_base",
    "arch_db", "arch_fs", "arch_original", "help", "terms",
    "html_content", "raw", "raw_text", "xml_id_list", "traceback"
}

# Binary fields that should be completely excluded
BINARY_FIELDS = {
    "datas", "data", "image", "image_1920", "image_1024", "image_512",
    "image_256", "image_128", "image_64", "image_medium", "image_small",
    "avatar", "avatar_128", "avatar_256", "avatar_512", "avatar_1024",
    "avatar_1920", "thumbnail", "preview", "attachment_data", "binary_data",
    "raw_data", "file_data", "pdf_data", "report_data", "signature"
}


def sanitize_value(key: str, value: Any) -> Any:
    """
    Sanitize a single field value.

    Args:
        key: Field name
        value: Field value

    Returns:
        Sanitized value (truncated string, placeholder for binary, or original)
    """
    key_lower = key.lower()

    # Check for binary fields - replace with placeholder
    if key_lower in BINARY_FIELDS or key_lower.startswith(("image_", "avatar_")):
        if value:
            return f"[BINARY DATA - field '{key}' excluded]"
        return value

    # Check for truncatable text fields
    if isinstance(value, str):
        # Check if this is a large truncatable field
        if key_lower in TRUNCATABLE_FIELDS and len(value) > MAX_FIELD_SIZE:
            truncated = value[:MAX_FIELD_SIZE]
            original_size = len(value)
            return (
                f"{truncated}\n\n"
                f"[... TRUNCATED - original size: {original_size:,} bytes, "
                f"showing first {MAX_FIELD_SIZE:,} bytes]"
            )
        # Also truncate any unknown very large string field
        if len(value) > MAX_FIELD_SIZE * 2:  # 100KB threshold for unknown fields
            truncated = value[:MAX_FIELD_SIZE]
            original_size = len(value)
            return (
                f"{truncated}\n\n"
                f"[... TRUNCATED - field '{key}' too large: {original_size:,} bytes, "
                f"showing first {MAX_FIELD_SIZE:,} bytes]"
            )

    return value


def sanitize_record(record: dict) -> dict:
    """
    Sanitize all fields in a record dictionary.

    Args:
        record: Dictionary of field names to values

    Returns:
        Sanitized record dictionary
    """
    if not isinstance(record, dict):
        return record

    return {k: sanitize_value(k, v) for k, v in record.items()}


def sanitize_response(response: Any) -> Any:
    """
    Recursively sanitize an MCP response to prevent oversized SSE messages.

    This function handles the MCP JSON-RPC response structure and sanitizes
    content that could cause asyncio.LimitOverrunError (>64KB).

    Args:
        response: The MCP response (typically a dict)

    Returns:
        Sanitized response with large fields truncated
    """
    if not isinstance(response, dict):
        return response

    # Deep copy to avoid mutating original
    result = {}

    for key, value in response.items():
        if isinstance(value, dict):
            # Recursively sanitize nested dicts
            result[key] = sanitize_response(value)
        elif isinstance(value, list):
            # Sanitize lists (e.g., content arrays, record lists)
            sanitized_list = []
            for item in value:
                if isinstance(item, dict):
                    # Could be an MCP content block or record data
                    if "text" in item and isinstance(item.get("text"), str):
                        # MCP text content block - sanitize the text
                        item_copy = dict(item)
                        text = item_copy["text"]
                        if len(text) > MAX_FIELD_SIZE:
                            item_copy["text"] = (
                                f"{text[:MAX_FIELD_SIZE]}\n\n"
                                f"[... TRUNCATED - response too large: "
                                f"{len(text):,} bytes]"
                            )
                        sanitized_list.append(item_copy)
                    else:
                        # Regular dict in list - sanitize recursively
                        sanitized_list.append(sanitize_response(item))
                else:
                    sanitized_list.append(item)
            result[key] = sanitized_list
        elif isinstance(value, str):
            # Direct string value
            result[key] = sanitize_value(key, value)
        else:
            result[key] = value

    return result


def estimate_response_size(response: Any) -> int:
    """
    Estimate the JSON-serialized size of a response.

    Args:
        response: The response object

    Returns:
        Estimated size in bytes
    """
    try:
        return len(json.dumps(response, default=str))
    except Exception:
        return 0


def is_response_too_large(response: Any, max_size: int = 64 * 1024) -> bool:
    """
    Check if a response would exceed the maximum allowed size.

    Args:
        response: The response object
        max_size: Maximum size in bytes (default 64KB for SSE)

    Returns:
        True if response exceeds max_size
    """
    return estimate_response_size(response) > max_size
