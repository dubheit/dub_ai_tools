# Copyright 2025 Dubhe Srls
# License OPL-1

"""
MCP tool execution service.
Contains business logic for MCP tools, separated from transport layer.
"""
import json
import logging

from odoo import models
from odoo.api import Environment

_logger = logging.getLogger(__name__)


def create_mcp_response(id, result=None, error=None) -> dict:
    """Create a JSON-RPC 2.0 response"""
    response = {"jsonrpc": "2.0", "id": id}
    if error:
        response["error"] = error
    else:
        response["result"] = result
    return response


def get_tools_list(env: Environment, config=None) -> list:
    """Get list of available MCP tools"""
    tools = [
        {
            "name": "list_models",
            "description": "List available Odoo models for MCP access",
            "inputSchema": {"type": "object", "properties": {}, "required": []}
        },
        {
            "name": "list_fields",
            "description": "List field definitions for an Odoo model",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "model": {
                        "type": "string",
                        "description": "Model name (e.g., res.partner)"
                    },
                    "attributes": {
                        "type": "array",
                        "description": "Field attributes to return (e.g., string, type, required, help)",
                        "default": ["string", "type", "required", "readonly", "help"]
                    }
                },
                "required": ["model"]
            }
        },
        {
            "name": "search",
            "description": "Search records in an Odoo model",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "model": {
                        "type": "string",
                        "description": "Model name (e.g., res.partner)"
                    },
                    "domain": {
                        "type": "array",
                        "description": "Search domain",
                        "default": []
                    },
                    "fields": {
                        "type": "array",
                        "description": "Fields to return",
                        "default": ["id", "display_name"]
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results",
                        "default": 10
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Records to skip",
                        "default": 0
                    },
                    "order": {
                        "type": "string",
                        "description": "Sort order",
                        "default": "id asc"
                    }
                },
                "required": ["model"]
            }
        },
        {
            "name": "read",
            "description": "Read specific records by ID",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "model": {"type": "string", "description": "Model name"},
                    "ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Record IDs"
                    },
                    "fields": {
                        "type": "array",
                        "description": "Fields to return",
                        "default": []
                    }
                },
                "required": ["model", "ids"]
            }
        },
        {
            "name": "create",
            "description": (
                "Create a new record. "
                "Some models require confirm=true for execution. "
                "Use context for special operations like "
                "{'check_move_validity': false} to skip account.move balance check."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "model": {"type": "string", "description": "Model name"},
                    "values": {"type": "object", "description": "Field values"},
                    "context": {
                        "type": "object",
                        "description": (
                            "Optional Odoo context. Useful keys: "
                            "check_move_validity (bool) - set false to skip balance check for account.move.line"
                        ),
                        "default": {}
                    },
                    "confirm": {
                        "type": "boolean",
                        "description": "Set to true to confirm operation on models that require confirmation",
                        "default": False
                    }
                },
                "required": ["model", "values"]
            }
        },
        {
            "name": "update",
            "description": (
                "Update existing records. "
                "Some models require confirm=true for execution. "
                "Use context for special operations like "
                "{'check_move_validity': false} to skip account.move balance check."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "model": {"type": "string", "description": "Model name"},
                    "ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Record IDs"
                    },
                    "values": {
                        "type": "object",
                        "description": "Field values to update"
                    },
                    "context": {
                        "type": "object",
                        "description": (
                            "Optional Odoo context. Useful keys: "
                            "check_move_validity (bool) - set false to skip balance check for account.move.line"
                        ),
                        "default": {}
                    },
                    "confirm": {
                        "type": "boolean",
                        "description": "Set to true to confirm operation on models that require confirmation",
                        "default": False
                    }
                },
                "required": ["model", "ids", "values"]
            }
        },
        {
            "name": "delete",
            "description": "Delete records. Some models require confirm=true for execution.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "model": {"type": "string", "description": "Model name"},
                    "ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Record IDs"
                    },
                    "confirm": {
                        "type": "boolean",
                        "description": "Set to true to confirm operation on models that require confirmation",
                        "default": False
                    }
                },
                "required": ["model", "ids"]
            }
        },
        {
            "name": "list_methods",
            "description": "List callable methods allowed on an Odoo model",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "model": {
                        "type": "string",
                        "description": "Model name (e.g., res.partner)"
                    }
                },
                "required": ["model"]
            }
        },
        {
            "name": "call_method",
            "description": "Call a method on Odoo model records",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "model": {
                        "type": "string",
                        "description": "Model name (e.g., res.partner)"
                    },
                    "method": {
                        "type": "string",
                        "description": "Method name to call"
                    },
                    "ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Record IDs to call method on (empty for model-level methods)",
                        "default": []
                    },
                    "args": {
                        "type": "array",
                        "description": "Positional arguments for the method",
                        "default": []
                    },
                    "kwargs": {
                        "type": "object",
                        "description": "Keyword arguments for the method",
                        "default": {}
                    }
                },
                "required": ["model", "method"]
            }
        }
    ]

    # Add get_logs tool if enabled in config
    if config and config.allow_logs_tool:
        tools.append({
            "name": "get_logs",
            "description": "Get recent Odoo server logs for debugging",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "level": {
                        "type": "string",
                        "description": "Filter by log level",
                        "enum": ["DEBUG", "INFO", "WARNING", "ERROR"]
                    },
                    "module": {
                        "type": "string",
                        "description": "Filter by module name (partial match)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max log entries to return",
                        "default": 50
                    },
                    "minutes": {
                        "type": "integer",
                        "description": "Only logs from last N minutes"
                    }
                },
                "required": []
            }
        })

    return tools


def _ensure_list(value, default=None):
    """Ensure a value is a list, deserializing from JSON string if needed."""
    if value is None:
        return default if default is not None else []
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, list):
        return [value]
    return value


def _ensure_int_list(value, default=None):
    """Ensure a value is a list of integers."""
    items = _ensure_list(value, default)
    return [int(x) for x in items]


def _ensure_dict(value, default=None):
    """Ensure a value is a dict, deserializing from JSON string if needed."""
    if value is None:
        return default if default is not None else {}
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, dict):
        return default if default is not None else {}
    return value


def _audit(
    env, config, user_id, operation: str, model: str = None,
    status: str = "success", record_ids: list = None,
    request_excerpt: dict = None, error_excerpt: str = None
):
    """Create audit log entry if enabled in config."""
    if not config or not config.enable_audit_log:
        return

    try:
        rec_ids = ""
        if record_ids:
            rec_ids = ",".join(map(str, record_ids))

        excerpt = ""
        if request_excerpt:
            try:
                excerpt = str(request_excerpt)[:1024]
            except Exception:
                excerpt = "<unserializable>"

        env["mcp.server.audit"].sudo().create({
            "user_id": user_id,
            "ip_address": "",
            "transport": "http",
            "operation": operation,
            "model_name": model or "",
            "record_ids": rec_ids,
            "status": status,
            "request_excerpt": excerpt,
            "error_excerpt": (error_excerpt or "")[:1024],
        })
    except Exception as e:
        _logger.warning("Failed to create audit log: %s", e)


def _get_model_rule(config, model_name: str):
    """Get the rule for a specific model from config"""
    if not config:
        return None
    for rule in config.rule_ids:
        if rule.model_name == model_name:
            return rule
    return None


def _check_permission(
    config, model_name: str, operation: str
) -> tuple[bool, str]:
    """
    Check if operation is allowed on model.
    Returns (allowed, error_message).
    """
    rule = _get_model_rule(config, model_name)
    if not rule:
        msg = f"Model '{model_name}' not configured for MCP"
        return False, msg

    permission_map = {
        "read": rule.allow_read,
        "search": rule.allow_read,
        "create": rule.allow_create,
        "update": rule.allow_write,
        "delete": rule.allow_unlink,
    }

    if not permission_map.get(operation, False):
        msg = f"'{operation}' not allowed on '{model_name}'"
        return False, msg

    return True, ""


def _filter_fields(rule, fields_list: list, record_data: dict) -> dict:
    """Filter out denied fields from record data"""
    if not rule or not rule.field_denylist:
        return record_data

    denied = {f.strip() for f in rule.field_denylist.split(",") if f.strip()}
    return {k: v for k, v in record_data.items() if k not in denied}


def _apply_domain_restriction(rule, domain: list) -> list:
    """Apply domain restriction from rule"""
    if not rule or not rule.domain_restriction:
        return domain

    try:
        restriction = json.loads(rule.domain_restriction)
        if restriction:
            return domain + restriction
    except (json.JSONDecodeError, TypeError):
        pass
    return domain


def _validate_model(env, model_name: str) -> tuple[bool, str]:
    """Validate that model exists and is accessible."""
    if not model_name or not isinstance(model_name, str):
        return False, "Invalid model name"

    # Check for malicious model names
    if not model_name.replace(".", "").replace("_", "").isalnum():
        return False, "Invalid model name format"

    # Check if model exists
    if model_name not in env:
        return False, f"Model '{model_name}' does not exist"

    return True, ""


def _validate_ids(ids) -> tuple[bool, str]:
    """Validate that ids is a list of positive integers."""
    if not isinstance(ids, list):
        return False, "ids must be a list"

    if not ids:
        return False, "ids list cannot be empty"

    for i in ids:
        if not isinstance(i, int) or i <= 0:
            return False, "ids must contain only positive integers"

    return True, ""


def _build_result(result_str: str, tracking_info: list, return_tracking: bool):
    """Build return value based on return_tracking_info flag."""
    if return_tracking:
        return result_str, tracking_info
    return result_str


def execute_tool(
    env: Environment, tool_name: str, arguments: dict,
    config=None, user_id=None, return_tracking_info: bool = False
):
    """
    Execute an MCP tool and return the result as string.
    Uses user_id context if provided for proper access control.
    """
    _logger.info(
        "execute_tool called: tool=%s, user_id=%s, env.user=%s",
        tool_name, user_id, env.user.id
    )
    try:
        # Switch to authenticated user context if provided
        if user_id:
            user = env["res.users"].sudo().browse(user_id)
            # Set user context with their allowed companies
            company_ids = user.company_ids.ids or [user.company_id.id]
            ctx = dict(env.context or {}, allowed_company_ids=company_ids)
            # Create new environment with proper user for transaction flush
            env = Environment(env.cr, user_id, ctx)
            _logger.info(
                "Created new env with user_id=%s, env.user now=%s",
                user_id, env.user.id
            )
        else:
            _logger.warning(
                "No user_id provided, using env.user=%s", env.user.id
            )

        if not config:
            config = env["mcp.server.config"].sudo().get_singleton()

        # Check if we have an active configuration
        if not config:
            return _build_result(
                "Error: No active MCP configuration found. Please enable an MCP config in Odoo.",
                [], return_tracking_info
            )

        if tool_name == "list_models":
            models = []
            for rule in config.rule_ids:
                ops = []
                if rule.allow_read:
                    ops.append("read")
                if rule.allow_create:
                    ops.append("create")
                if rule.allow_write:
                    ops.append("write")
                if rule.allow_unlink:
                    ops.append("delete")
                models.append(f"- {rule.model_name}: {', '.join(ops)}")

            _audit(env, config, user_id, "discover", status="success")
            if models:
                return _build_result("Available models:\n" + "\n".join(models), [], return_tracking_info)
            return _build_result("No models configured", [], return_tracking_info)

        elif tool_name == "list_fields":
            model = arguments.get("model")
            if not model:
                return _build_result("Error: model parameter is required", [], return_tracking_info)

            # Validate model
            valid, err = _validate_model(env, model)
            if not valid:
                return _build_result(f"Error: {err}", [], return_tracking_info)

            # Check permission (need read access to list fields)
            allowed, error = _check_permission(config, model, "read")
            if not allowed:
                return _build_result(f"Access denied: {error}", [], return_tracking_info)

            # Get field definitions
            requested_attrs = _ensure_list(arguments.get("attributes"),
                ["string", "type", "required", "readonly", "help"]
            )

            fields_info = env[model].fields_get(attributes=requested_attrs)

            if not fields_info:
                return _build_result(f"No fields found for model {model}", [], return_tracking_info)

            # Filter out denied fields
            rule = _get_model_rule(config, model)
            if rule and rule.field_denylist:
                denied = {f.strip() for f in rule.field_denylist.split(",") if f.strip()}
                fields_info = {k: v for k, v in fields_info.items() if k not in denied}

            result = f"Fields for {model} ({len(fields_info)} fields):\n\n"
            for field_name, attrs in sorted(fields_info.items()):
                field_type = attrs.get("type", "unknown")
                field_label = attrs.get("string", field_name)
                required = attrs.get("required", False)
                readonly = attrs.get("readonly", False)

                flags = []
                if required:
                    flags.append("required")
                if readonly:
                    flags.append("readonly")
                flags_str = f" [{', '.join(flags)}]" if flags else ""

                result += f"- {field_name} ({field_type}): {field_label}{flags_str}\n"

                if attrs.get("help"):
                    result += f"    Help: {attrs['help']}\n"

            _audit(env, config, user_id, "list_fields", model=model, status="success")
            return _build_result(result, [], return_tracking_info)

        elif tool_name == "search":
            model = arguments.get("model")
            if not model:
                return _build_result("Error: model parameter is required", [], return_tracking_info)

            # Validate model
            valid, err = _validate_model(env, model)
            if not valid:
                return _build_result(f"Error: {err}", [], return_tracking_info)

            # Check permission
            allowed, error = _check_permission(config, model, "search")
            if not allowed:
                return _build_result(f"Access denied: {error}", [], return_tracking_info)

            rule = _get_model_rule(config, model)
            domain = _ensure_list(arguments.get("domain"), [])
            domain = _apply_domain_restriction(rule, domain)

            req_fields = _ensure_list(arguments.get("fields"), ["id", "display_name"])
            limit = min(int(arguments.get("limit", 10)), config.max_page_size)
            offset = int(arguments.get("offset", 0))
            order = arguments.get("order", "id asc")

            records = env[model].search_read(
                domain,
                fields=req_fields,
                limit=limit,
                offset=offset,
                order=order
            )

            if not records:
                return _build_result(f"No {model} records found", [], return_tracking_info)

            # Filter denied fields and collect tracking info
            result = f"Found {len(records)} {model} record(s):\n"
            tracking_ids = []
            tracking_names = []
            for r in records:
                r = _filter_fields(rule, req_fields, r)
                result += f"- ID {r.get('id')}: {r.get('display_name', r)}\n"
                tracking_ids.append(r.get("id"))
                tracking_names.append(str(r.get("display_name", f"ID {r.get('id')}")))

            _audit(
                env, config, user_id, "search", model=model,
                status="success", request_excerpt={"domain": domain}
            )

            tracking_info = [{
                "model": model,
                "ids": tracking_ids,
                "display_names": tracking_names,
                "operation": "search"
            }] if tracking_ids else []

            return _build_result(result, tracking_info, return_tracking_info)

        elif tool_name == "read":
            model = arguments.get("model")
            if not model:
                return _build_result("Error: model parameter is required", [], return_tracking_info)

            # Validate model
            valid, err = _validate_model(env, model)
            if not valid:
                return _build_result(f"Error: {err}", [], return_tracking_info)

            # Check permission
            allowed, error = _check_permission(config, model, "read")
            if not allowed:
                return _build_result(f"Access denied: {error}", [], return_tracking_info)

            ids = _ensure_int_list(arguments.get("ids"), [])
            # Validate IDs
            valid, err = _validate_ids(ids)
            if not valid:
                return _build_result(f"Error: {err}", [], return_tracking_info)

            rule = _get_model_rule(config, model)
            req_fields = _ensure_list(arguments.get("fields"), [])

            records = env[model].browse(ids).read(req_fields or [])

            if not records:
                return _build_result("No records found", [], return_tracking_info)

            # Collect tracking info
            tracking_ids = []
            tracking_names = []
            result = f"{model} record(s):\n"
            for r in records:
                r = _filter_fields(rule, req_fields, r)
                result += f"\nID {r.get('id')}:\n"
                tracking_ids.append(r.get("id"))
                tracking_names.append(str(r.get("display_name", f"ID {r.get('id')}")))
                for k, v in r.items():
                    if k != "id":
                        result += f"  {k}: {v}\n"

            _audit(
                env, config, user_id, "read", model=model,
                status="success", record_ids=ids
            )

            tracking_info = [{
                "model": model,
                "ids": tracking_ids,
                "display_names": tracking_names,
                "operation": "read"
            }] if tracking_ids else []

            return _build_result(result, tracking_info, return_tracking_info)

        elif tool_name == "create":
            model = arguments.get("model")
            if not model:
                return _build_result("Error: model parameter is required", [], return_tracking_info)

            # Validate model
            valid, err = _validate_model(env, model)
            if not valid:
                return _build_result(f"Error: {err}", [], return_tracking_info)

            # Check MCP permission
            allowed, error = _check_permission(config, model, "create")
            if not allowed:
                return _build_result(f"Access denied: {error}", [], return_tracking_info)

            # Check if confirmation is required
            rule = _get_model_rule(config, model)
            if rule and rule.require_confirmation:
                if not arguments.get("confirm"):
                    return _build_result(
                        f"STOP - USER CONFIRMATION REQUIRED: Creating {model} record is a sensitive operation. "
                        f"You MUST ask the user 'Do you want to proceed with creating this {model} record?' "
                        f"and wait for their explicit approval before calling this tool again with confirm=true.",
                        [], return_tracking_info
                    )

            # Check Odoo ACL permissions for the authenticated user
            try:
                env[model].browse().check_access('create')
            except Exception:
                return _build_result(f"Access denied: user cannot create {model} records", [], return_tracking_info)

            values = _ensure_dict(arguments.get("values"), {})
            if not isinstance(values, dict):
                return _build_result("Error: values must be a dictionary", [], return_tracking_info)

            # Get optional context from arguments
            extra_ctx = _ensure_dict(arguments.get("context"), {})
            if not isinstance(extra_ctx, dict):
                return _build_result("Error: context must be a dictionary", [], return_tracking_info)

            # Merge with default context
            ctx = {"mail_create_nosubscribe": True}
            ctx.update(extra_ctx)

            record = env[model].with_context(**ctx).create(values)
            # Flush in user context before request ends to avoid empty user issue
            env.flush_all()
            _audit(
                env, config, user_id, "create", model=model,
                status="success", record_ids=[record.id],
                request_excerpt={"values": values}
            )

            # Collect tracking info
            display_name = record.display_name if hasattr(record, "display_name") else f"ID {record.id}"
            tracking_info = [{
                "model": model,
                "ids": [record.id],
                "display_names": [str(display_name)],
                "operation": "create"
            }]

            return _build_result(f"Created {model} record with ID: {record.id}", tracking_info, return_tracking_info)

        elif tool_name == "update":
            model = arguments.get("model")
            if not model:
                return _build_result("Error: model parameter is required", [], return_tracking_info)

            # Validate model
            valid, err = _validate_model(env, model)
            if not valid:
                return _build_result(f"Error: {err}", [], return_tracking_info)

            # Check MCP permission
            allowed, error = _check_permission(config, model, "update")
            if not allowed:
                return _build_result(f"Access denied: {error}", [], return_tracking_info)

            # Check if confirmation is required
            rule = _get_model_rule(config, model)
            if rule and rule.require_confirmation:
                if not arguments.get("confirm"):
                    return _build_result(
                        f"STOP - USER CONFIRMATION REQUIRED: Updating {model} records is a sensitive operation. "
                        f"You MUST ask the user 'Do you want to proceed with updating these {model} records?' "
                        f"and wait for their explicit approval before calling this tool again with confirm=true.",
                        [], return_tracking_info
                    )

            ids = _ensure_int_list(arguments.get("ids"), [])
            # Validate IDs
            valid, err = _validate_ids(ids)
            if not valid:
                return _build_result(f"Error: {err}", [], return_tracking_info)

            values = _ensure_dict(arguments.get("values"), {})
            if not isinstance(values, dict):
                return _build_result("Error: values must be a dictionary", [], return_tracking_info)

            # Check Odoo ACL + record rules for the authenticated user
            try:
                records = env[model].browse(ids)
                records.check_access('write')
            except Exception:
                return _build_result(f"Access denied: user cannot write these {model} records", [], return_tracking_info)

            # Get optional context from arguments
            extra_ctx = _ensure_dict(arguments.get("context"), {})
            if not isinstance(extra_ctx, dict):
                return _build_result("Error: context must be a dictionary", [], return_tracking_info)

            if extra_ctx:
                records = records.with_context(**extra_ctx)

            # Get display names before update for tracking
            display_names = [str(r.display_name) if hasattr(r, "display_name") else f"ID {r.id}" for r in records]

            records.write(values)
            # Flush in user context before request ends to avoid empty user issue
            env.flush_all()
            _audit(
                env, config, user_id, "write", model=model,
                status="success", record_ids=ids,
                request_excerpt={"values": values}
            )

            # Collect tracking info
            tracking_info = [{
                "model": model,
                "ids": ids,
                "display_names": display_names,
                "operation": "update"
            }]

            return _build_result(f"Updated {len(ids)} {model} record(s)", tracking_info, return_tracking_info)

        elif tool_name == "delete":
            model = arguments.get("model")
            if not model:
                return _build_result("Error: model parameter is required", [], return_tracking_info)

            # Validate model
            valid, err = _validate_model(env, model)
            if not valid:
                return _build_result(f"Error: {err}", [], return_tracking_info)

            # Check MCP permission
            allowed, error = _check_permission(config, model, "delete")
            if not allowed:
                return _build_result(f"Access denied: {error}", [], return_tracking_info)

            # Check if confirmation is required
            rule = _get_model_rule(config, model)
            if rule and rule.require_confirmation:
                if not arguments.get("confirm"):
                    return _build_result(
                        f"STOP - USER CONFIRMATION REQUIRED: Deleting {model} records is a sensitive operation. "
                        f"You MUST ask the user 'Do you want to proceed with deleting these {model} records?' "
                        f"and wait for their explicit approval before calling this tool again with confirm=true.",
                        [], return_tracking_info
                    )

            ids = _ensure_int_list(arguments.get("ids"), [])
            # Validate IDs
            valid, err = _validate_ids(ids)
            if not valid:
                return _build_result(f"Error: {err}", [], return_tracking_info)

            # Check Odoo ACL + record rules for the authenticated user
            try:
                records = env[model].browse(ids)
                records.check_access('unlink')
            except Exception:
                return _build_result(f"Access denied: user cannot delete these {model} records", [], return_tracking_info)

            # Get display names before delete for tracking
            display_names = [str(r.display_name) if hasattr(r, "display_name") else f"ID {r.id}" for r in records]

            records.unlink()
            # Flush in user context before request ends to avoid empty user issue
            env.flush_all()
            _audit(
                env, config, user_id, "unlink", model=model,
                status="success", record_ids=ids
            )

            # Collect tracking info
            tracking_info = [{
                "model": model,
                "ids": ids,
                "display_names": display_names,
                "operation": "delete"
            }]

            return _build_result(f"Deleted {len(ids)} {model} record(s)", tracking_info, return_tracking_info)

        elif tool_name == "list_methods":
            model = arguments.get("model")
            if not model:
                return _build_result("Error: model parameter is required", [], return_tracking_info)

            # Validate model
            valid, err = _validate_model(env, model)
            if not valid:
                return _build_result(f"Error: {err}", [], return_tracking_info)

            # Check MCP permission (need read access)
            allowed, error = _check_permission(config, model, "read")
            if not allowed:
                return _build_result(f"Access denied: {error}", [], return_tracking_info)

            # Get allowed methods from config
            rule = _get_model_rule(config, model)
            if not rule or not rule.allowed_method_ids:
                return _build_result(f"No methods configured for {model}", [], return_tracking_info)

            result = f"Available methods for {model}:\n\n"
            for method in rule.allowed_method_ids:
                sig = method.signature or "()"
                result += f"- {method.name}{sig}\n"
                if method.description:
                    # Show first line of description
                    desc_line = method.description.split("\n")[0][:100]
                    result += f"    {desc_line}\n"

            _audit(env, config, user_id, "list_methods", model=model, status="success")
            return _build_result(result, [], return_tracking_info)

        elif tool_name == "call_method":
            model = arguments.get("model")
            if not model:
                return _build_result("Error: model parameter is required", [], return_tracking_info)

            method_name = arguments.get("method")
            if not method_name:
                return _build_result("Error: method parameter is required", [], return_tracking_info)

            # Validate model
            valid, err = _validate_model(env, model)
            if not valid:
                return _build_result(f"Error: {err}", [], return_tracking_info)

            # Check MCP permission (need read access at minimum)
            allowed, error = _check_permission(config, model, "read")
            if not allowed:
                return _build_result(f"Access denied: {error}", [], return_tracking_info)

            # Check if method is in allowed list
            rule = _get_model_rule(config, model)
            if not rule:
                return _build_result(f"Access denied: Model '{model}' not configured for MCP", [], return_tracking_info)

            allowed_methods = rule.allowed_method_ids.mapped("name")
            if method_name not in allowed_methods:
                return _build_result(f"Access denied: Method '{method_name}' not allowed on {model}", [], return_tracking_info)

            # Get arguments
            ids = _ensure_int_list(arguments.get("ids"), [])
            args = _ensure_list(arguments.get("args"), [])
            kwargs = _ensure_dict(arguments.get("kwargs"), {})

            # Validate IDs if provided
            if ids:
                valid, err = _validate_ids(ids)
                if not valid:
                    return _build_result(f"Error: {err}", [], return_tracking_info)

            try:
                # Get recordset
                if ids:
                    records = env[model].browse(ids)
                    # Check access
                    records.check_access("read")
                else:
                    records = env[model]

                # Get display names for tracking (if we have ids)
                display_names = []
                if ids and records:
                    display_names = [str(r.display_name) if hasattr(r, "display_name") else f"ID {r.id}" for r in records]

                # Get the method
                method = getattr(records, method_name, None)
                if not method or not callable(method):
                    return _build_result(f"Error: Method '{method_name}' not found on {model}", [], return_tracking_info)

                # Call the method
                result = method(*args, **kwargs)

                # Flush changes
                env.flush_all()

                # Format result
                if result is None:
                    result_str = "Method executed successfully (no return value)"
                elif isinstance(result, models.Model):
                    # Recordset result
                    if result:
                        result_str = f"Returned {len(result)} {result._name} record(s): {result.ids}"
                    else:
                        result_str = f"Returned empty {result._name} recordset"
                elif isinstance(result, (dict, list)):
                    result_str = json.dumps(result, default=str, indent=2)
                else:
                    result_str = str(result)

                _audit(
                    env, config, user_id, "call_method", model=model,
                    status="success", record_ids=ids or None,
                    request_excerpt={"method": method_name, "args": args, "kwargs": kwargs}
                )

                # Collect tracking info
                tracking_info = [{
                    "model": model,
                    "ids": ids,
                    "display_names": display_names,
                    "operation": f"call_method:{method_name}"
                }] if ids else []

                return _build_result(f"Method {method_name} result:\n{result_str}", tracking_info, return_tracking_info)

            except Exception as e:
                _logger.exception("Error calling method %s on %s", method_name, model)
                _audit(
                    env, config, user_id, "call_method", model=model,
                    status="fail", record_ids=ids or None,
                    request_excerpt={"method": method_name},
                    error_excerpt=str(e)
                )
                return _build_result(f"Error calling method: {e}", [], return_tracking_info)

        elif tool_name == "get_logs":
            # Check if logs tool is enabled for this config
            if not config or not config.allow_logs_tool:
                return _build_result("Access denied: get_logs tool is not enabled", [], return_tracking_info)

            from .log_buffer import get_log_buffer

            level = arguments.get("level")
            module = arguments.get("module")
            limit = min(int(arguments.get("limit", 50)), 200)  # Cap at 200
            minutes = arguments.get("minutes")

            buffer = get_log_buffer()
            logs = buffer.get_logs(
                level=level,
                module=module,
                limit=limit,
                minutes=minutes,
            )

            if not logs:
                return _build_result("No log entries found matching the criteria", [], return_tracking_info)

            result = f"Found {len(logs)} log entries:\n\n"
            for entry in logs:
                result += (
                    f"[{entry['timestamp']}] "
                    f"{entry['level']} "
                    f"{entry['module']}: "
                    f"{entry['message']}\n"
                )
            return _build_result(result, [], return_tracking_info)

        else:
            return _build_result(f"Unknown tool: {tool_name}", [], return_tracking_info)

    except Exception as e:
        # Log the full error internally, return sanitized message
        _logger.exception("MCP tool execution error")
        return _build_result("Error: An internal error occurred. Please try again.", [], return_tracking_info)
