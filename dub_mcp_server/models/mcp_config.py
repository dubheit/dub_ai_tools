# Copyright 2025 Dubhe Srls
# License LGPL-3

import inspect
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class McpServerConfig(models.Model):
    _name = "mcp.server.config"
    _description = "MCP Server Configuration"
    _rec_name = "name"

    name = fields.Char(
        default="Default MCP Server Config",
        required=True
    )
    active = fields.Boolean(default=True)

    # Link to OAuth2 client for per-client MCP permissions
    oauth2_client_id = fields.Many2one(
        "oauth2.client",
        string="OAuth2 Client",
        ondelete="cascade",
        help="Link to OAuth2 client. Users authenticating "
             "via this client will use these MCP rules."
    )

    # Link to specific users for per-user MCP permissions
    user_ids = fields.Many2many(
        "res.users",
        string="Allowed Users",
        help="If set, only these users will use this config. "
             "If empty, this config acts as a default fallback."
    )

    transport_stdio = fields.Boolean(default=False)
    transport_http = fields.Boolean(default=True)

    max_page_size = fields.Integer(default=200)
    default_page_size = fields.Integer(default=50)
    request_timeout_ms = fields.Integer(default=8000)
    request_body_max_kb = fields.Integer(default=128)

    rate_limit_window_s = fields.Integer(default=60)
    rate_limit_max_requests = fields.Integer(default=120)

    # Max duration of a single SSE connection before asking the client to
    # reconnect. Must stay below Odoo's limit_time_real (odoo.conf) to avoid
    # the worker killing the request mid-stream.
    sse_max_duration_s = fields.Integer(
        string="SSE Max Duration (s)",
        default=900,
        help="Maximum lifetime of an SSE connection in seconds. The client "
             "is asked to reconnect when reached. Keep it below the Odoo "
             "limit_time_real worker timeout."
    )

    # Audit logging
    enable_audit_log = fields.Boolean(
        string="Enable Audit Log",
        default=True,
        help="Log all MCP operations to mcp.server.audit for tracking."
    )
    audit_retention_days = fields.Integer(
        string="Audit Log Retention (days)",
        default=30,
        help="Number of days to keep audit logs. Set to 0 to keep forever."
    )

    # Advanced tools (security-sensitive)
    allow_logs_tool = fields.Boolean(
        string="Allow Logs Tool",
        default=False,
        help="Enable the get_logs tool to read Odoo server logs. "
             "Only enable for trusted admin clients."
    )

    rule_ids = fields.One2many(
        "mcp.server.model.rule",
        "config_id",
        string="Model Rules"
    )

    @api.model
    def get_by_user(self, user_id):
        """Get active config explicitly linked to a specific user."""
        if user_id:
            return self.search([
                ("user_ids", "in", [user_id]),
                ("active", "=", True)
            ], limit=1)
        return self.browse()

    @api.model
    def get_by_oauth2_client(self, client_id):
        """Get active config linked to specific OAuth2 client."""
        if client_id:
            return self.search([
                ("oauth2_client_id", "=", client_id),
                ("active", "=", True)
            ], limit=1)
        return self.browse()

    @api.model
    def get_by_access_token(self, token_string):
        """Get active config based on OAuth2 access token.

        Deny by default: only returns a config if the user or
        the OAuth2 client is explicitly linked to one.
        Priority: user-specific config > client-specific config.
        """
        try:
            AccessToken = self.env["oauth2.access_token"].sudo()
            token = AccessToken.find_by_token(token_string)
            if token and token.is_valid():
                user_config = self.get_by_user(token.user_id.id)
                if user_config:
                    return user_config
                return self.get_by_oauth2_client(token.client_id.id)
        except Exception:
            pass
        return self.browse()

    @api.model
    def get_singleton(self):
        """Backward compat — deny by default (empty recordset)."""
        return self.browse()

    get_default = get_singleton


class McpServerModelRule(models.Model):
    _name = "mcp.server.model.rule"
    _description = "MCP Model Rule"

    config_id = fields.Many2one(
        "mcp.server.config", required=True, ondelete="cascade"
    )
    model_id = fields.Many2one(
        "ir.model", string="Model", required=True, ondelete="cascade"
    )
    model_name = fields.Char(
        related="model_id.model",
        readonly=True,
        store=True,
        help="Technical model name, e.g., res.partner"
    )

    allow_read = fields.Boolean(default=False)
    allow_create = fields.Boolean(default=False)
    allow_write = fields.Boolean(default=False)
    allow_unlink = fields.Boolean(default=False)

    require_confirmation = fields.Boolean(
        string="Require Confirmation",
        default=False,
        help="If enabled, create/update/delete operations require explicit "
             "confirmation (confirm=true) before execution."
    )

    field_denylist = fields.Text(
        help="Comma-separated field names to hide/block."
    )
    domain_restriction = fields.Text(
        help="JSON domain to AND with client domain."
    )
    description = fields.Text()

    # PII masking
    pii_mask_field_ids = fields.Many2many(
        "ir.model.fields",
        string="PII Masked Fields",
        domain="[('model_id', '=', model_id)]",
        help="Fields whose values will be masked in MCP responses "
             "(e.g., email, phone, vat). Only the first and last "
             "characters are shown."
    )

    # Method permissions
    allowed_method_ids = fields.Many2many(
        "mcp.model.method",
        string="Allowed Methods",
        domain="[('model_id', '=', model_id)]",
        help="Methods that can be called via MCP on this model."
    )

    @api.onchange("model_id")
    def _onchange_model_id(self):
        """Clear methods when model changes."""
        self.allowed_method_ids = [(5, 0, 0)]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("model_id") and vals.get("model_name"):
                ir_model = self.env["ir.model"].sudo().search(
                    [("model", "=", vals["model_name"])], limit=1
                )
                if ir_model:
                    vals["model_id"] = ir_model.id
            vals.pop("model_name", None)
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("model_name") and not vals.get("model_id"):
            ir_model = self.env["ir.model"].sudo().search(
                [("model", "=", vals["model_name"])], limit=1
            )
            if ir_model:
                vals["model_id"] = ir_model.id
        vals.pop("model_name", None)
        return super().write(vals)

    def action_refresh_methods(self):
        """Discover and populate available methods for the model."""
        self.ensure_one()
        if not self.model_id:
            return

        McpMethod = self.env["mcp.model.method"]
        McpMethod.populate_for_model(self.model_id.id)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Methods Refreshed",
                "message": f"Available methods for {self.model_name} have been updated.",
                "type": "success",
            }
        }


class McpModelMethod(models.Model):
    _name = "mcp.model.method"
    _description = "MCP Model Method"
    _order = "model_id, name"
    _rec_name = "display_name"

    name = fields.Char(required=True, index=True)
    model_id = fields.Many2one(
        "ir.model",
        string="Model",
        required=True,
        ondelete="cascade",
        index=True
    )
    model_name = fields.Char(
        related="model_id.model",
        store=True,
        readonly=True
    )
    description = fields.Text(help="Method docstring")
    signature = fields.Char(help="Method signature")
    display_name = fields.Char(compute="_compute_display_name", store=True)

    _sql_constraints = [
        ("unique_method_per_model", "unique(model_id, name)",
         "Method name must be unique per model")
    ]

    @api.depends("name", "model_name")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"{rec.model_name}.{rec.name}" if rec.model_name else rec.name

    @api.model
    def discover_methods(self, model_name):
        """
        Discover callable methods on an Odoo model.
        Returns list of method info dicts.

        SECURITY: this is a *discovery* heuristic only (dir() + a blacklist
        of dangerous names) used to populate the admin UI. It does NOT gate
        execution. The real gate is the per-rule whitelist
        ``allowed_method_ids``: only methods explicitly enabled there can be
        invoked via MCP. Heuristic gaps here cannot widen what is callable.
        """
        if model_name not in self.env:
            return []

        model_obj = self.env[model_name]
        methods = []

        # Patterns for methods we want to expose
        safe_prefixes = ("action_", "button_", "do_", "process_", "compute_")

        # Get all public methods
        for attr_name in dir(model_obj):
            # Skip private/magic methods
            if attr_name.startswith("_"):
                continue

            # Skip common dangerous methods
            if attr_name in (
                "create", "write", "unlink", "read", "search", "browse",
                "sudo", "with_user", "with_context", "with_env", "with_company",
                "copy", "fields_get", "fields_view_get", "name_get",
                "name_search", "name_create", "default_get", "search_read",
                "search_count", "read_group", "export_data", "import_data",
                "load", "flush", "invalidate_cache", "invalidate_recordset",
                "check_access", "check_access_rights", "check_access_rule",
            ):
                continue

            try:
                attr = getattr(model_obj, attr_name)
                if not callable(attr):
                    continue

                # Check if it's a method (not a field or property)
                if not inspect.ismethod(attr) and not inspect.isfunction(attr):
                    continue

                # Get signature and docstring
                try:
                    sig = str(inspect.signature(attr))
                except (ValueError, TypeError):
                    sig = "()"

                docstring = inspect.getdoc(attr) or ""
                # Truncate long docstrings
                if len(docstring) > 500:
                    docstring = docstring[:500] + "..."

                methods.append({
                    "name": attr_name,
                    "signature": sig,
                    "description": docstring,
                    "has_safe_prefix": attr_name.startswith(safe_prefixes),
                })

            except Exception as e:
                _logger.debug("Error inspecting %s.%s: %s", model_name, attr_name, e)
                continue

        # Sort: safe prefixes first, then alphabetically
        methods.sort(key=lambda m: (not m["has_safe_prefix"], m["name"]))
        return methods

    @api.model
    def populate_for_model(self, model_id):
        """
        Populate available methods for a given ir.model record.
        Returns the created/updated method records.
        """
        ir_model = self.env["ir.model"].browse(model_id)
        if not ir_model.exists():
            return self.browse()

        model_name = ir_model.model
        discovered = self.discover_methods(model_name)

        existing = self.search([("model_id", "=", model_id)])
        existing_names = {m.name: m for m in existing}

        to_create = []
        for method in discovered:
            if method["name"] in existing_names:
                # Update existing
                existing_names[method["name"]].write({
                    "signature": method["signature"],
                    "description": method["description"],
                })
            else:
                to_create.append({
                    "name": method["name"],
                    "model_id": model_id,
                    "signature": method["signature"],
                    "description": method["description"],
                })

        created = self.create(to_create) if to_create else self.browse()
        return existing | created
