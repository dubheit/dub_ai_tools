from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    dub_ai_provider = fields.Selection(
        selection_add=[('claude', 'Anthropic Claude')],
        ondelete={'claude': 'set null'},
    )
    dub_ai_claude_api_key = fields.Char(string="Claude API Key")
    dub_ai_claude_model_id = fields.Many2one(
        'dub.ai.model', string="Claude Model",
        domain="[('provider', '=', 'claude'), ('active', '=', True)]",
    )
    dub_ai_claude_temperature = fields.Float(
        string="Claude Temperature", default=0.7,
    )
