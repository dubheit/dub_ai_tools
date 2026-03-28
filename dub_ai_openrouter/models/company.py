from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    dub_ai_provider = fields.Selection(
        selection_add=[('openrouter', 'OpenRouter')],
        ondelete={'openrouter': 'set null'},
    )
    dub_ai_openrouter_api_key = fields.Char(string="OpenRouter API Key")
    dub_ai_openrouter_model_id = fields.Many2one(
        'dub.ai.model', string="OpenRouter Model",
        domain="[('provider', '=', 'openrouter'), ('active', '=', True)]",
    )
    dub_ai_openrouter_temperature = fields.Float(
        string="OpenRouter Temperature", default=0.7,
    )
