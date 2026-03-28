from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    dub_ai_provider = fields.Selection(
        selection_add=[('openai', 'OpenAI')],
        ondelete={'openai': 'set null'},
    )
    dub_ai_openai_api_key = fields.Char(string="OpenAI API Key")
    dub_ai_openai_model_id = fields.Many2one(
        'dub.ai.model', string="OpenAI Model",
        domain="[('provider', '=', 'openai'), ('active', '=', True)]",
    )
    dub_ai_openai_temperature = fields.Float(
        string="OpenAI Temperature", default=0.7,
    )
