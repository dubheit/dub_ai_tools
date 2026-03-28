from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    dub_ai_gemini_api_key = fields.Char(
        related='company_id.dub_ai_gemini_api_key', readonly=False)
    dub_ai_gemini_model_id = fields.Many2one(
        related='company_id.dub_ai_gemini_model_id', readonly=False)
    dub_ai_gemini_temperature = fields.Float(
        related='company_id.dub_ai_gemini_temperature', readonly=False)

    def action_test_gemini(self):
        return self._action_test_provider('gemini')

    def action_sync_gemini(self):
        return self.env['dub.ai.model'].action_sync_gemini_models()
