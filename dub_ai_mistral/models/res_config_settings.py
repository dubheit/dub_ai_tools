from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    dub_ai_mistral_api_key = fields.Char(
        related='company_id.dub_ai_mistral_api_key', readonly=False)
    dub_ai_mistral_model_id = fields.Many2one(
        related='company_id.dub_ai_mistral_model_id', readonly=False)
    dub_ai_mistral_temperature = fields.Float(
        related='company_id.dub_ai_mistral_temperature', readonly=False)

    def action_test_mistral(self):
        return self._action_test_provider('mistral')

    def action_sync_mistral(self):
        return self.env['dub.ai.model'].action_sync_mistral_models()
