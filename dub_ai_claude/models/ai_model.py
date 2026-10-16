import requests

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AiModel(models.Model):
    _inherit = 'dub.ai.model'

    provider = fields.Selection(
        selection_add=[('claude', 'Anthropic Claude')],
        ondelete={'claude': 'cascade'},
    )
    bedrock_model_id = fields.Char(
        string="Bedrock Model ID",
        help="Model identifier on the Amazon Bedrock route, e.g. "
             "anthropic.claude-opus-5-5. Required there: cross-region "
             "inference profile ids such as eu.anthropic.claude-opus-5-5 "
             "are not served by that endpoint.",
    )
    bedrock_invoke_model_id = fields.Char(
        string="Bedrock InvokeModel ID",
        help="Cross-region inference profile used on the Amazon Bedrock "
             "InvokeModel route, e.g. eu.anthropic.claude-sonnet-5-5. List "
             "the ones your account can invoke with: aws bedrock "
             "list-inference-profiles --region eu-central-1",
    )
    vertex_model_id = fields.Char(
        string="Google Model ID",
        help="Model identifier on the Google Cloud route. Leave empty when "
             "it matches the Model ID, which is the case for every model "
             "but the dated snapshots, e.g. claude-haiku-4-5@20251001.",
    )

    def _get_sync_providers(self):
        providers = super()._get_sync_providers()
        if self.env.company.dub_ai_claude_route == 'direct':
            providers.append(('claude', 'dub_ai_claude_api_key'))
        return providers

    @api.model
    def action_sync_claude_models(self):
        """Fetch available models from Anthropic API."""
        company = self.env.company
        if company.dub_ai_claude_route != 'direct':
            raise UserError(_(
                "Model sync uses the Anthropic Models API, which neither "
                "Amazon Bedrock nor Google Cloud serves. On those routes, "
                "maintain the model list manually."
            ))

        api_key = company.dub_ai_claude_api_key
        if not api_key:
            raise UserError(_("Claude API key is not configured."))

        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }
        response = requests.get(
            "https://api.anthropic.com/v1/models",
            headers=headers, timeout=30,
        )
        response.raise_for_status()

        created = 0
        for info in response.json().get('data', []):
            mid = info.get('id', '')
            dname = info.get('display_name', mid)
            if not self.search([
                ('name', '=', mid), ('provider', '=', 'claude')
            ], limit=1):
                self.create({
                    'name': mid, 'display_name': dname,
                    'provider': 'claude', 'sequence': 100,
                })
                created += 1

        return self._sync_notification("Claude", created)
