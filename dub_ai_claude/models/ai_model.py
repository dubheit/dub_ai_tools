import requests

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AiModel(models.Model):
    _inherit = 'dub.ai.model'

    provider = fields.Selection(
        selection_add=[('claude', 'Anthropic Claude')],
        ondelete={'claude': 'cascade'},
    )

    def _get_sync_providers(self):
        providers = super()._get_sync_providers()
        providers.append(('claude', 'dub_ai_claude_api_key'))
        return providers

    @api.model
    def action_sync_claude_models(self):
        """Fetch available models from Anthropic API."""
        api_key = self.env.company.dub_ai_claude_api_key
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
