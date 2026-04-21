# Copyright 2025 Dubhe Srls
# License LGPL-3

from dataclasses import dataclass
from typing import Any, List, Optional

from . import errors

DENYLIST_ALWAYS = {"password", "token", "secret"}


@dataclass
class AuthContext:
    """Authentication context for MCP requests."""
    user_id: int
    login: str
    ip: str


def _get_config(env):
    """Get MCP server configuration."""
    return env["mcp.server.config"].sudo().get_singleton()


def ensure_enabled(ctx: AuthContext, env):
    """Check if MCP Server is enabled."""
    cfg = _get_config(env)
    if not cfg:
        raise errors.AuthzDenied(
            "No MCP configuration found for this user."
        )
    if not cfg.active:
        raise errors.AuthzDenied(
            "MCP Server is disabled by configuration."
        )


def check_operation(ctx: AuthContext, model: str, op: str, env):
    """Check if operation is allowed on model."""
    cfg = _get_config(env)
    if not cfg:
        raise errors.AuthzDenied(
            "No MCP configuration found for this user."
        )
    domain = [("config_id", "=", cfg.id), ("model_name", "=", model)]
    rule = env["mcp.server.model.rule"].sudo().search(domain, limit=1)
    if not rule:
        raise errors.AuthzDenied(f"Model not enabled: {model}")
    allowed = {
        "read": rule.allow_read,
        "search": rule.allow_read,
        "create": rule.allow_create,
        "write": rule.allow_write,
        "unlink": rule.allow_unlink,
    }.get(op, False)
    if not allowed:
        raise errors.AuthzDenied(
            f"{op.title()} not allowed for model {model}"
        )
    return rule


def apply_field_denylist(fields: List[str], rule) -> List[str]:
    """Filter out denied fields from field list."""
    deny = {
        f.strip()
        for f in (rule.field_denylist or "").split(",")
        if f.strip()
    }
    deny |= DENYLIST_ALWAYS
    if not fields:
        return fields
    return [f for f in fields if f not in deny]


def audit(
    ctx: AuthContext,
    operation: str,
    model: Optional[str],
    status: str,
    env,
    request_excerpt: Any = None,
    record_ids: Optional[List[int]] = None,
    error_excerpt: Optional[str] = None
):
    """Create audit log entry."""
    excerpt = request_excerpt
    if isinstance(excerpt, dict):
        try:
            excerpt = str(excerpt)[:1024]
        except Exception:
            excerpt = "<unserializable>"

    rec_ids = ""
    if record_ids:
        rec_ids = ",".join(map(str, record_ids))

    env["mcp.server.audit"].sudo().create({
        "user_id": ctx.user_id,
        "ip_address": ctx.ip,
        "transport": "http",
        "operation": operation,
        "model_name": model or "",
        "record_ids": rec_ids,
        "status": status,
        "request_excerpt": excerpt or "",
        "error_excerpt": (error_excerpt or "")[:1024],
    })
