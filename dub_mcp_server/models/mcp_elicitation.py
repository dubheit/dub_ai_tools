# Copyright 2025 Dubhe Srls
# License LGPL-3

import secrets
from datetime import timedelta

from odoo import api, fields, models

DEFAULT_EXPIRY_MIN = 30


class McpServerElicitation(models.Model):
    """Pending URL-mode elicitation (MCP 2025-11-25).

    Tracks an out-of-band interaction the server asked the user to complete
    via a web page. Bound to the authenticated user (anti-phishing): only that
    user, logged into Odoo, may complete it.
    """
    _name = "mcp.server.elicitation"
    _description = "MCP Server Elicitation"
    _order = "create_date desc"

    elicitation_id = fields.Char(required=True, index=True, copy=False)
    user_id = fields.Many2one(
        "res.users", required=True, ondelete="cascade", index=True
    )
    purpose = fields.Char(
        required=True, index=True,
        help="Logical key of the value being collected (e.g. demo_secret)."
    )
    message = fields.Char()
    status = fields.Selection(
        [("pending", "Pending"),
         ("completed", "Completed"),
         ("cancelled", "Cancelled")],
        default="pending", required=True, index=True
    )
    value = fields.Char(help="Collected value, bound to the user.")
    expiry = fields.Datetime()
    url = fields.Char(compute="_compute_url", string="Completion URL")

    def _compute_url(self):
        base = self.env["ir.config_parameter"].sudo().get_param(
            "web.base.url", ""
        )
        for rec in self:
            rec.url = "%s/mcp/elicitation/%s" % (base, rec.elicitation_id)

    _sql_constraints = [
        ("elicitation_id_uniq", "unique(elicitation_id)",
         "Elicitation id must be unique"),
    ]

    @api.model
    def create_pending(self, user_id, purpose, message,
                       expiry_min=DEFAULT_EXPIRY_MIN):
        return self.sudo().create({
            "elicitation_id": secrets.token_urlsafe(24),
            "user_id": user_id,
            "purpose": purpose,
            "message": message,
            "status": "pending",
            "expiry": fields.Datetime.now() + timedelta(minutes=expiry_min),
        })
