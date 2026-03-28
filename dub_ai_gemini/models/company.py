from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    dub_ai_provider = fields.Selection(
        selection_add=[('gemini', 'Google Gemini')],
        ondelete={'gemini': 'set null'},
    )
    dub_ai_gemini_api_key = fields.Char(string="Gemini API Key")
    dub_ai_gemini_model_id = fields.Many2one(
        'dub.ai.model', string="Gemini Model",
        domain="[('provider', '=', 'gemini'), ('active', '=', True)]",
    )
    dub_ai_gemini_temperature = fields.Float(
        string="Gemini Temperature", default=0.7,
    )
