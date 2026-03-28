from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    dub_ai_ollama_base_url = fields.Char(
        related='company_id.dub_ai_ollama_base_url', readonly=False)
    dub_ai_ollama_api_key = fields.Char(
        related='company_id.dub_ai_ollama_api_key', readonly=False)
    dub_ai_ollama_model_id = fields.Many2one(
        related='company_id.dub_ai_ollama_model_id', readonly=False)
    dub_ai_ollama_temperature = fields.Float(
        related='company_id.dub_ai_ollama_temperature', readonly=False)

    def action_test_ollama(self):
        return self._action_test_provider('ollama')

    def action_sync_ollama(self):
        return self.env['dub.ai.model'].action_sync_ollama_models()
