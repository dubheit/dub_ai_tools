# Copyright 2025 Dubhe Srls
# License OPL-1

from datetime import timedelta

from odoo import api, fields, models


class McpServerAudit(models.Model):
    _name = "mcp.server.audit"
    _description = "MCP Server Audit Log"
    _order = "create_date desc"

    timestamp = fields.Datetime(
        default=lambda self: fields.Datetime.now(), index=True
    )
    user_id = fields.Many2one("res.users", ondelete="set null")
    ip_address = fields.Char()
    transport = fields.Selection(
        [("stdio", "Stdio"), ("http", "HTTP")],
        default="http"
    )
    operation = fields.Selection(
        [
            ("discover", "Discover"),
            ("read", "Read"),
            ("search", "Search"),
            ("create", "Create"),
            ("write", "Write"),
            ("unlink", "Unlink"),
            ("execute", "Execute"),
            ("list_methods", "List Methods"),
        ],
        required=True
    )
    model_name = fields.Char(string="Model")
    record_ids = fields.Char()
    status = fields.Selection(
        [
            ("success", "Success"),
            ("fail", "Fail"),
            ("denied", "Denied"),
            ("timeout", "Timeout"),
            ("rate_limited", "Rate Limited"),
        ],
        required=True
    )
    request_excerpt = fields.Text()
    error_excerpt = fields.Text()

    @api.model
    def _cron_cleanup_old_logs(self):
        """Delete audit logs older than retention period."""
        configs = self.env["mcp.server.config"].search([
            ("enable_audit_log", "=", True),
            ("audit_retention_days", ">", 0),
        ])
        if not configs:
            return

        # Use minimum retention from all configs
        min_days = min(c.audit_retention_days for c in configs)
        cutoff = fields.Datetime.now() - timedelta(days=min_days)

        old_logs = self.search([("timestamp", "<", cutoff)])
        count = len(old_logs)
        if old_logs:
            old_logs.unlink()

        return count
