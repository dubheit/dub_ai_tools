from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    dub_ai_claude_route = fields.Selection(
        related='company_id.dub_ai_claude_route', readonly=False)
    dub_ai_claude_api_key = fields.Char(
        related='company_id.dub_ai_claude_api_key', readonly=False)
    dub_ai_claude_model_id = fields.Many2one(
        related='company_id.dub_ai_claude_model_id', readonly=False)
    dub_ai_claude_aws_region = fields.Selection(
        related='company_id.dub_ai_claude_aws_region', readonly=False)
    dub_ai_claude_aws_access_key_id = fields.Char(
        related='company_id.dub_ai_claude_aws_access_key_id', readonly=False)
    dub_ai_claude_aws_secret_access_key = fields.Char(
        related='company_id.dub_ai_claude_aws_secret_access_key',
        readonly=False)
    dub_ai_claude_bedrock_api_key = fields.Char(
        related='company_id.dub_ai_claude_bedrock_api_key', readonly=False)
    dub_ai_claude_gcp_project_id = fields.Char(
        related='company_id.dub_ai_claude_gcp_project_id', readonly=False)
    dub_ai_claude_gcp_region = fields.Selection(
        related='company_id.dub_ai_claude_gcp_region', readonly=False)
    dub_ai_claude_gcp_credentials = fields.Text(
        related='company_id.dub_ai_claude_gcp_credentials', readonly=False)

    def action_test_claude(self):
        return self._action_test_provider('claude')

    def action_sync_claude(self):
        return self.env['dub.ai.model'].action_sync_claude_models()
