from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    dub_ai_provider = fields.Selection(
        selection_add=[('mistral', 'Mistral AI')],
        ondelete={'mistral': 'set null'},
    )
    dub_ai_mistral_api_key = fields.Char(string="Mistral API Key")
    dub_ai_mistral_model_id = fields.Many2one(
        'dub.ai.model', string="Mistral Model",
        domain="[('provider', '=', 'mistral'), ('active', '=', True)]",
    )
    dub_ai_mistral_temperature = fields.Float(
        string="Mistral Temperature", default=0.7,
    )
