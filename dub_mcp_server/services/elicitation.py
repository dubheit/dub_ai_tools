# Copyright 2025 Dubhe Srls
# License LGPL-3

"""URL-mode elicitation helpers (MCP 2025-11-25).

A tool that needs an out-of-band value from the user creates a pending
elicitation and raises errors.UrlElicitationRequired; the controller turns it
into a JSON-RPC -32042 error carrying the URL. The user opens the URL (a web
page served by Odoo), the value is stored bound to their identity, and the
client retries the original tools/call.
"""


def create_url_elicitation(env, user_id, purpose, message):
    """Create a pending elicitation and return its url-mode descriptor dict."""
    elicitation = env["mcp.server.elicitation"].sudo().create_pending(
        user_id, purpose, message
    )
    base_url = env["ir.config_parameter"].sudo().get_param("web.base.url", "")
    return {
        "mode": "url",
        "elicitationId": elicitation.elicitation_id,
        "url": "%s/mcp/elicitation/%s" % (base_url, elicitation.elicitation_id),
        "message": message,
    }


def get_completed_value(env, user_id, purpose):
    """Return the value of the latest completed elicitation for user+purpose."""
    from odoo import fields
    rec = env["mcp.server.elicitation"].sudo().search([
        ("user_id", "=", user_id),
        ("purpose", "=", purpose),
        ("status", "=", "completed"),
    ], limit=1, order="create_date desc")
    if not rec:
        return None
    if rec.expiry and rec.expiry < fields.Datetime.now():
        return None
    return rec.value
