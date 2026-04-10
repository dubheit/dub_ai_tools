import json
import logging
import re

from odoo.api import Environment

_logger = logging.getLogger(__name__)


def get_resources_list(env, config=None):
    """Return static MCP resources."""
    resources = [
        {
            "uri": "odoo://modules/installed",
            "name": "Installed Modules",
            "description": "List of installed Odoo modules with versions",
            "mimeType": "application/json",
        },
    ]

    if config and config.model_ids:
        for model_access in config.model_ids:
            model_name = model_access.model_id.model
            resources.append({
                "uri": "odoo://model/%s/schema" % model_name,
                "name": "%s Schema" % model_access.model_id.name,
                "description": "Field definitions for %s" % model_name,
                "mimeType": "application/json",
            })

    return resources


def get_resource_templates_list(env, config=None):
    """Return dynamic MCP resource templates."""
    return [
        {
            "uriTemplate": "odoo://model/{model}/schema",
            "name": "Model Schema",
            "description": "Field definitions for any Odoo model",
            "mimeType": "application/json",
        },
        {
            "uriTemplate": "odoo://model/{model}/{id}",
            "name": "Record Data",
            "description": "Read a specific record by ID",
            "mimeType": "application/json",
        },
        {
            "uriTemplate": "odoo://model/{model}?domain={domain}&limit={limit}",
            "name": "Search Records",
            "description": "Search records with a domain filter",
            "mimeType": "application/json",
        },
    ]


def read_resource(env, uri, config=None, user_id=None):
    """Read a resource by URI. Returns (content, mimeType)."""
    if user_id:
        env = env(user=user_id)

    # odoo://modules/installed
    if uri == "odoo://modules/installed":
        return _read_installed_modules(env)

    # odoo://model/{model}/schema
    match = re.match(r"^odoo://model/([^/]+)/schema$", uri)
    if match:
        model_name = match.group(1)
        return _read_model_schema(env, model_name, config)

    # odoo://model/{model}/{id}
    match = re.match(r"^odoo://model/([^/]+)/(\d+)$", uri)
    if match:
        model_name = match.group(1)
        record_id = int(match.group(2))
        return _read_record(env, model_name, record_id, config)

    # odoo://model/{model}?domain=...&limit=...
    match = re.match(r"^odoo://model/([^?]+)\?(.+)$", uri)
    if match:
        model_name = match.group(1)
        query_string = match.group(2)
        return _read_search(env, model_name, query_string, config)

    return json.dumps({"error": "Unknown resource URI: %s" % uri}), "application/json"


def _check_model_access(env, model_name, config):
    """Check if model is accessible via MCP config."""
    if model_name not in env:
        return "Model '%s' not found" % model_name
    if config and config.model_ids:
        allowed = [m.model_id.model for m in config.model_ids]
        if model_name not in allowed:
            return "Model '%s' not allowed by MCP configuration" % model_name
    return None


def _read_installed_modules(env):
    """List installed modules."""
    modules = env["ir.module.module"].sudo().search([
        ("state", "=", "installed"),
    ], order="name")
    data = [
        {
            "name": m.name,
            "version": m.installed_version or "",
            "summary": m.summary or "",
        }
        for m in modules
    ]
    return json.dumps(data, indent=2), "application/json"


def _read_model_schema(env, model_name, config):
    """Read field definitions for a model."""
    error = _check_model_access(env, model_name, config)
    if error:
        return json.dumps({"error": error}), "application/json"

    Model = env[model_name]
    fields_info = Model.fields_get(
        attributes=["string", "type", "required", "readonly",
                     "help", "selection", "relation"]
    )
    return json.dumps(fields_info, indent=2), "application/json"


def _get_fields_spec(env, model_name):
    """Get the fields spec for web_read, using the default form view."""
    Model = env[model_name]
    try:
        view = Model.get_view(False, 'form')
        return Model._get_fields_spec(view)
    except Exception:
        return {}


def _read_record(env, model_name, record_id, config):
    """Read a specific record using Odoo's web_read (same as /json/ route)."""
    error = _check_model_access(env, model_name, config)
    if error:
        return json.dumps({"error": error}), "application/json"

    record = env[model_name].browse(record_id)
    if not record.exists():
        return json.dumps(
            {"error": "Record %s/%d not found" % (model_name, record_id)}
        ), "application/json"

    spec = _get_fields_spec(env, model_name)
    if spec:
        data = record.web_read(spec)[0]
    else:
        data = record.read()[0]

    return json.dumps(data, indent=2, default=str), "application/json"


def _read_search(env, model_name, query_string, config):
    """Search records using Odoo's web_search_read (same as /json/ route)."""
    error = _check_model_access(env, model_name, config)
    if error:
        return json.dumps({"error": error}), "application/json"

    import ast
    import urllib.parse
    params = urllib.parse.parse_qs(query_string)
    domain_str = params.get("domain", ["[]"])[0]
    limit = int(params.get("limit", ["80"])[0])
    limit = min(limit, 200)
    offset = int(params.get("offset", ["0"])[0])

    try:
        domain = ast.literal_eval(domain_str)
    except (ValueError, SyntaxError):
        return json.dumps(
            {"error": "Invalid domain: %s" % domain_str}
        ), "application/json"

    Model = env[model_name]
    spec = _get_fields_spec(env, model_name)
    if spec:
        data = Model.web_search_read(
            domain, spec, limit=limit, offset=offset,
        )
    else:
        records = Model.search(domain, limit=limit, offset=offset)
        data = {"records": records.read(), "length": len(records)}

    return json.dumps(data, indent=2, default=str), "application/json"
