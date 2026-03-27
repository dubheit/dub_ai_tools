# Copyright 2025 Dubhe Srls
# License OPL-1

from typing import Any, Dict

from . import errors


def _require(obj: dict, key: str, typ):
    if key not in obj:
        raise errors.InvalidValues(f"Missing required key: {key}")
    if not isinstance(obj[key], typ):
        raise errors.InvalidValues(f"Key '{key}' must be {typ.__name__}")
    return obj[key]


def parse_search_read(payload: Dict[str, Any]) -> Dict[str, Any]:
    model = _require(payload, "model", str)
    domain = payload.get("domain") or []
    if not isinstance(domain, list):
        raise errors.InvalidDomain("Domain must be a JSON list")
    fields = payload.get("fields") or []
    if fields and not isinstance(fields, list):
        raise errors.InvalidValues("fields must be a list of strings")
    limit = int(payload.get("limit") or 0)
    offset = int(payload.get("offset") or 0)
    order = payload.get("order") or None
    return {
        "model": model, "domain": domain, "fields": fields,
        "limit": limit, "offset": offset, "order": order
    }


def parse_read(payload: Dict[str, Any]) -> Dict[str, Any]:
    model = _require(payload, "model", str)
    ids = _require(payload, "ids", list)
    fields = payload.get("fields") or []
    return {"model": model, "ids": ids, "fields": fields}


def parse_create(payload: Dict[str, Any]) -> Dict[str, Any]:
    model = _require(payload, "model", str)
    values = _require(payload, "values", dict)
    return {"model": model, "values": values}


def parse_write(payload: Dict[str, Any]) -> Dict[str, Any]:
    model = _require(payload, "model", str)
    ids = _require(payload, "ids", list)
    values = _require(payload, "values", dict)
    return {"model": model, "ids": ids, "values": values}


def parse_unlink(payload: Dict[str, Any]) -> Dict[str, Any]:
    model = _require(payload, "model", str)
    ids = _require(payload, "ids", list)
    return {"model": model, "ids": ids}
