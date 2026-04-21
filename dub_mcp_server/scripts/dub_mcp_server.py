#!/usr/bin/env python3
# Copyright 2025 Dubhe Srls
# License LGPL-3
"""
FastMCP Bridge for Odoo MCP Server.

This script provides a stdio interface for AI assistants (Claude, etc.)
to communicate with Odoo via the MCP protocol.

Usage:
    python dub_mcp_server.py

Environment variables:
    ODOO_URL: Base URL of your Odoo instance (default: http://localhost:8069)
    ODOO_CLIENT_ID: OAuth2 client ID (recommended)
    ODOO_CLIENT_SECRET: OAuth2 client secret (recommended)
    ODOO_API_KEY: API key for authentication (alternative)
    ODOO_TOKEN: Static OAuth2 access token (alternative)

Claude Desktop configuration (~/.config/claude/claude_desktop_config.json):
{
    "mcpServers": {
        "odoo": {
            "command": "python",
            "args": ["/path/to/dub_mcp_server.py"],
            "env": {
                "ODOO_URL": "https://your-odoo.example.com",
                "ODOO_CLIENT_ID": "your-client-id",
                "ODOO_CLIENT_SECRET": "your-client-secret"
            }
        }
    }
}
"""
import json
import os
import sys
import time
from typing import Any, Optional

import requests
from fastmcp import FastMCP

# Configuration from environment
ODOO_URL = os.environ.get("ODOO_URL", "http://localhost:8069")
ODOO_API_KEY = os.environ.get("ODOO_API_KEY", "")
ODOO_TOKEN = os.environ.get("ODOO_TOKEN", "")
ODOO_CLIENT_ID = os.environ.get("ODOO_CLIENT_ID", "")
ODOO_CLIENT_SECRET = os.environ.get("ODOO_CLIENT_SECRET", "")

# Token cache for OAuth2 client credentials flow
_oauth2_token_cache = {
    "access_token": None,
    "expires_at": 0,
}

# Create FastMCP server
mcp = FastMCP("Dubhe MCP Server")


def _get_oauth2_token() -> Optional[str]:
    """Get OAuth2 access token using client credentials flow."""
    global _oauth2_token_cache

    # Check if cached token is still valid (with 60s buffer)
    if (_oauth2_token_cache["access_token"] and
            _oauth2_token_cache["expires_at"] > time.time() + 60):
        return _oauth2_token_cache["access_token"]

    # Request new token
    try:
        response = requests.post(
            f"{ODOO_URL}/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": ODOO_CLIENT_ID,
                "client_secret": ODOO_CLIENT_SECRET,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()

        if "access_token" in data:
            _oauth2_token_cache["access_token"] = data["access_token"]
            expires_in = data.get("expires_in", 3600)
            _oauth2_token_cache["expires_at"] = time.time() + expires_in
            return data["access_token"]
        else:
            print(f"OAuth2 token error: {data}", file=sys.stderr)
            return None
    except Exception as e:
        print(f"OAuth2 token request failed: {e}", file=sys.stderr)
        return None


def _get_headers() -> dict:
    """Get authentication headers for Odoo API calls."""
    headers = {"Content-Type": "application/json"}

    # Priority: OAuth2 client credentials > static token > API key
    if ODOO_CLIENT_ID and ODOO_CLIENT_SECRET:
        token = _get_oauth2_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"
    elif ODOO_TOKEN:
        headers["Authorization"] = f"Bearer {ODOO_TOKEN}"
    elif ODOO_API_KEY:
        headers["Authorization"] = f"Bearer {ODOO_API_KEY}"

    return headers


def _call_odoo(endpoint: str, data: dict = None) -> dict:
    """Make a POST request to Odoo MCP endpoint."""
    url = f"{ODOO_URL}/mcp/{endpoint}"
    headers = _get_headers()

    try:
        response = requests.post(
            url,
            json=data or {},
            headers=headers,
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"ok": False, "error": {"message": "Request to Odoo failed"}}


def _format_result(response: dict) -> str:
    """Format API response for display."""
    if not response.get("ok"):
        error = response.get("error", {})
        return f"Error: {error.get('message', 'Unknown error')}"

    result = response.get("result")
    if isinstance(result, str):
        return result
    if isinstance(result, (dict, list)):
        return json.dumps(result, indent=2, default=str)
    return str(result)


@mcp.tool
def list_models() -> str:
    """List available Odoo models configured for MCP access."""
    response = _call_odoo("models")
    if response.get("ok"):
        result = response.get("result", {})
        if isinstance(result, dict):
            models = result.get("models", [])
        else:
            models = result
        if not models:
            return "No models configured for MCP access"
        lines = ["Available models:"]
        for m in models:
            name = m.get("model", "unknown")
            ops = m.get("operations", [])
            lines.append(f"  - {name}: {', '.join(ops)}")
        return "\n".join(lines)
    return _format_result(response)


@mcp.tool
def search(
    model: str,
    domain: Optional[list] = None,
    fields: Optional[list] = None,
    limit: int = 10,
    offset: int = 0,
    order: Optional[str] = None
) -> str:
    """
    Search records in an Odoo model.

    Args:
        model: Model name (e.g., 'res.partner', 'sale.order')
        domain: Search domain as list of tuples
            (e.g., [['is_company', '=', True]])
        fields: List of field names to return
        limit: Maximum number of records (default: 10)
        offset: Number of records to skip (default: 0)
        order: Sort order (e.g., 'name asc', 'create_date desc')

    Returns:
        Formatted search results
    """
    data = {
        "model": model,
        "domain": domain or [],
        "fields": fields,
        "limit": limit,
        "offset": offset,
    }
    if order:
        data["order"] = order

    response = _call_odoo("search_read", data)
    if response.get("ok"):
        records = response.get("result", [])
        meta = response.get("meta", {})
        if not records:
            return f"No {model} records found"

        lines = [f"Found {len(records)} {model} record(s):"]
        for r in records:
            rec_id = r.get("id", "?")
            name = r.get("display_name") or r.get("name") or str(r)
            lines.append(f"  - ID {rec_id}: {name}")

        if meta.get("total"):
            lines.append(f"\nTotal: {meta['total']} records")
        return "\n".join(lines)
    return _format_result(response)


@mcp.tool
def read(
    model: str,
    ids: list[int],
    fields: Optional[list] = None
) -> str:
    """
    Read specific records by ID.

    Args:
        model: Model name (e.g., 'res.partner')
        ids: List of record IDs to read
        fields: List of field names to return (empty = all fields)

    Returns:
        Formatted record data
    """
    data = {
        "model": model,
        "ids": ids,
        "fields": fields,
    }
    response = _call_odoo("read", data)
    if response.get("ok"):
        records = response.get("result", [])
        if not records:
            return f"No records found with IDs {ids}"

        lines = [f"{model} record(s):"]
        for r in records:
            lines.append(f"\nID {r.get('id', '?')}:")
            for k, v in r.items():
                if k != "id":
                    lines.append(f"  {k}: {v}")
        return "\n".join(lines)
    return _format_result(response)


@mcp.tool
def create(model: str, values: dict) -> str:
    """
    Create a new record.

    Args:
        model: Model name (e.g., 'res.partner')
        values: Dictionary of field values

    Returns:
        ID of created record
    """
    data = {"model": model, "values": values}
    response = _call_odoo("create", data)
    if response.get("ok"):
        result = response.get("result", {})
        rec_id = result.get("id")
        return f"Created {model} record with ID: {rec_id}"
    return _format_result(response)


@mcp.tool
def update(model: str, ids: list[int], values: dict) -> str:
    """
    Update existing records.

    Args:
        model: Model name (e.g., 'res.partner')
        ids: List of record IDs to update
        values: Dictionary of field values to update

    Returns:
        Confirmation message
    """
    data = {"model": model, "ids": ids, "values": values}
    response = _call_odoo("write", data)
    if response.get("ok"):
        result = response.get("result", {})
        count = result.get("updated", len(ids))
        return f"Updated {count} {model} record(s)"
    return _format_result(response)


@mcp.tool
def delete(model: str, ids: list[int]) -> str:
    """
    Delete records.

    Args:
        model: Model name (e.g., 'res.partner')
        ids: List of record IDs to delete

    Returns:
        Confirmation message
    """
    data = {"model": model, "ids": ids}
    response = _call_odoo("unlink", data)
    if response.get("ok"):
        result = response.get("result", {})
        count = result.get("deleted", len(ids))
        return f"Deleted {count} {model} record(s)"
    return _format_result(response)


@mcp.tool
def list_methods(
    model: str,
    categories: Optional[list] = None,
    search_term: Optional[str] = None
) -> str:
    """
    List available methods for a model.

    Args:
        model: Model name (e.g., 'sale.order')
        categories: Filter by categories (e.g., ['action', 'button'])
        search_term: Search in method names/descriptions

    Returns:
        List of available methods
    """
    data = {"model": model}
    if categories:
        data["categories"] = categories
    if search_term:
        data["search"] = search_term

    response = _call_odoo("methods", data)
    if response.get("ok"):
        result = response.get("result", {})
        methods = result.get("methods", [])
        if not methods:
            return f"No methods found for {model}"

        lines = [f"Methods for {model} ({len(methods)} found):"]
        for m in methods:
            name = m.get("name", "?")
            desc = m.get("description", "")
            cat = m.get("category", "")
            line = f"  - {name}"
            if cat:
                line += f" [{cat}]"
            if desc:
                line += f": {desc[:60]}..."
            lines.append(line)
        return "\n".join(lines)
    return _format_result(response)


@mcp.tool
def execute(
    model: str,
    method: str,
    ids: list[int],
    args: Optional[list] = None,
    kwargs: Optional[dict] = None
) -> str:
    """
    Execute a method on records.

    Args:
        model: Model name (e.g., 'sale.order')
        method: Method name (must start with action_, button_, etc.)
        ids: List of record IDs
        args: Positional arguments for the method
        kwargs: Keyword arguments for the method

    Returns:
        Method execution result
    """
    data = {
        "model": model,
        "method": method,
        "ids": ids,
        "args": args or [],
        "kwargs": kwargs or {},
    }
    response = _call_odoo("execute", data)
    if response.get("ok"):
        result = response.get("result", {})
        if result.get("success"):
            res = result.get('result')
            return f"Method {method} executed successfully: {res}"
        return f"Method {method} returned: {result}"
    return _format_result(response)


if __name__ == "__main__":
    # Validate configuration
    has_oauth2 = ODOO_CLIENT_ID and ODOO_CLIENT_SECRET
    has_token = ODOO_API_KEY or ODOO_TOKEN

    if not has_oauth2 and not has_token:
        print(
            "Warning: No authentication configured. "
            "Set ODOO_CLIENT_ID + ODOO_CLIENT_SECRET for OAuth2, "
            "or ODOO_API_KEY/ODOO_TOKEN for static token auth.",
            file=sys.stderr
        )

    # Run the MCP server in stdio mode
    mcp.run()
