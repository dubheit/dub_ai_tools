from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    dub_ai_claude_api_key = fields.Char(
        related='company_id.dub_ai_claude_api_key', readonly=False)
    dub_ai_claude_model_id = fields.Many2one(
        related='company_id.dub_ai_claude_model_id', readonly=False)
    dub_ai_claude_temperature = fields.Float(
        related='company_id.dub_ai_claude_temperature', readonly=False)

    def action_test_claude(self):
        return self._action_test_provider('claude')

    def action_sync_claude(self):
        return self.env['dub.ai.model'].action_sync_claude_models()
