# Copyright 2025 Dubhe Srls
# License OPL-1

import json
from typing import Any, Dict, List, Tuple

from . import authz, errors, introspect


def _cfg(env):
    return env["mcp.server.config"].sudo().get_singleton()


def _normalize_fields(fields: List[str]) -> List[str]:
    if not fields:
        return ["id", "display_name"]
    return list(dict.fromkeys(fields))


def _sanitize_order(order: str, model: str) -> str:
    if not order:
        return ""
    for ch in order:
        if not (ch.isalnum() or ch in " _.,"):
            raise errors.InvalidValues(
                "Invalid characters in 'order' parameter"
            )
    return order


def list_models(ctx, env) -> Dict[str, Any]:
    cfg = _cfg(env)
    domain = [("config_id", "=", cfg.id)]
    rules = env["mcp.server.model.rule"].sudo().search(domain)
    out = {"models": []}
    for r in rules:
        flds = introspect.fields_meta(r.model_name, env)
        ops = []
        if r.allow_read:
            ops.extend(["read", "search"])
        if r.allow_create:
            ops.append("create")
        if r.allow_write:
            ops.append("write")
        if r.allow_unlink:
            ops.append("unlink")
        out["models"].append({
            "model": r.model_name,
            "label": introspect.model_label(r.model_name, env),
            "operations": ops,
            "fields": flds,
        })
    return out


def _merge_domain(restriction: str, client_domain: List) -> List:
    try:
        base = json.loads(restriction) if restriction else []
    except Exception:
        raise errors.InvalidDomain(
            "domain_restriction must be valid JSON"
        )
    if not isinstance(base, list):
        raise errors.InvalidDomain(
            "domain_restriction must be a JSON list"
        )
    if not client_domain:
        return base
    if not base:
        return client_domain
    return ["&", base, client_domain]


def search_read(
    ctx, data: Dict[str, Any], env
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    model = data["model"]
    rule = authz.check_operation(ctx, model, "search", env)
    envu = env(user=ctx.user_id)
    raw_fields = data.get("fields") or []
    filtered = authz.apply_field_denylist(raw_fields, rule)
    fields = _normalize_fields(filtered)
    limit = data.get("limit") or _cfg(env).default_page_size
    max_ps = _cfg(env).max_page_size or 200
    limit_cap = min(max(1, limit), max_ps)
    offset = max(0, int(data.get("offset") or 0))
    order = _sanitize_order(data.get("order") or "", model)
    restriction = rule.domain_restriction or ""
    client_dom = data.get("domain") or []
    domain = _merge_domain(restriction, client_dom)
    records = envu[model].search(
        domain, limit=limit_cap, offset=offset, order=order
    )
    result = records.read(fields)
    total = envu[model].search_count(domain)
    meta = {"limit": limit_cap, "offset": offset, "count": total}
    return result, meta


def read(ctx, data: Dict[str, Any], env) -> List[Dict[str, Any]]:
    model = data["model"]
    rule = authz.check_operation(ctx, model, "read", env)
    envu = env(user=ctx.user_id)
    raw_fields = data.get("fields") or []
    filtered = authz.apply_field_denylist(raw_fields, rule)
    fields = _normalize_fields(filtered)
    ids = data["ids"]
    records = envu[model].browse(ids).exists()
    if not records:
        raise errors.RecordNotFound(
            "No records found for given IDs"
        )
    return records.read(fields)


def create(ctx, data: Dict[str, Any], env) -> int:
    model = data["model"]
    authz.check_operation(ctx, model, "create", env)
    envu = env(user=ctx.user_id)
    values = data["values"]
    rec = envu[model].create(values)
    return rec.id


def write(ctx, data: Dict[str, Any], env) -> int:
    model = data["model"]
    authz.check_operation(ctx, model, "write", env)
    envu = env(user=ctx.user_id)
    ids = data["ids"]
    values = data["values"]
    records = envu[model].browse(ids).exists()
    if not records:
        raise errors.RecordNotFound(
            "No records found for given IDs"
        )
    records.write(values)
    return len(records)


def unlink(ctx, data: Dict[str, Any], env) -> int:
    model = data["model"]
    authz.check_operation(ctx, model, "unlink", env)
    envu = env(user=ctx.user_id)
    ids = data["ids"]
    records = envu[model].browse(ids).exists()
    if not records:
        raise errors.RecordNotFound(
            "No records found for given IDs"
        )
    count = len(records)
    records.unlink()
    return count
