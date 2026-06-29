# Copyright 2025 Dubhe Srls
# License LGPL-3

"""
Shared security helpers for the MCP server.

Centralizes the field denylist so that every transport (native SSE /
Streamable HTTP and REST/FastAPI) enforces the same protection, instead
of each code path parsing ``field_denylist`` on its own.
"""

# Fields that are ALWAYS hidden from MCP responses, regardless of the
# per-rule field_denylist. Kept here as the single source of truth.
DENYLIST_ALWAYS = frozenset({"password", "api_key", "token", "secret"})


def denied_fields(rule) -> set:
    """Return the full set of denied field names for a rule.

    Always includes DENYLIST_ALWAYS, plus the comma-separated
    ``field_denylist`` configured on the rule (if any).
    """
    deny = set(DENYLIST_ALWAYS)
    if rule and rule.field_denylist:
        deny |= {f.strip() for f in rule.field_denylist.split(",") if f.strip()}
    return deny


def filter_denied(rule, record_data: dict) -> dict:
    """Drop denied keys from a record dict (always-denylist + per-rule)."""
    deny = denied_fields(rule)
    return {k: v for k, v in record_data.items() if k not in deny}
